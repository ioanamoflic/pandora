import time

import numpy as np
import cirq

from qualtran.bloqs.mod_arithmetic import ModAddK
from qualtran.bloqs.basic_gates import TwoBitCSwap
from qualtran.cirq_interop import BloqAsCirqGate
from qualtran._infra.adjoint import Adjoint
from qualtran.bloqs.chemistry.hubbard_model.qubitization import get_walk_operator_for_hubbard_model

import benchmarking.benchmark_cirq
from pandora.cirq_to_pandora_util import cirq_to_pandora, pandora_to_cirq
from pandora.gate_translator import In, Out
from pandora.qualtran_to_pandora_util import get_adder, get_qrom, get_qpe_of_1d_ising_model, phase_estimation, keep, \
    decompose_qualtran_bloq_gate, decompose_fredkin


def test_random_reconstruction(n_circuits=100):
    templates = ['add_two_hadamards', 'add_two_cnots', 'add_base_change', 'add_t_t_dag', 'add_t_cx', 'add_cx_t']
    for i in range(n_circuits):
        print(f'Random test {i}')
        start_time = time.time()
        initial_circuit = benchmarking.benchmark_cirq.create_random_circuit(n_qubits=3,
                                                                            n_templates=3,
                                                                            templates=templates, add_margins=True)
        print(initial_circuit)

        print(f'Time for create_random_circuit: {time.time() - start_time}')

        start_time = time.time()
        db_tuples, last_id = cirq_to_pandora(cirq_circuit=initial_circuit, last_id=0, label='test', add_margins=False)
        print(f'Time for cirq_to_db: {time.time() - start_time}')

        start_time = time.time()
        reconstructed_circuit = pandora_to_cirq(pandora_gates=db_tuples)
        print(f'Time for db_to_cirq: {time.time() - start_time}')

        qubit_map = dict(
            zip(
                sorted(initial_circuit.all_qubits()),
                sorted(reconstructed_circuit.all_qubits())
            )
        )
        initial_circuit = initial_circuit.transform_qubits(qubit_map=qubit_map)

        start_time = time.time()
        assert str(reconstructed_circuit) == str(initial_circuit)
        print(f'Time for assertion: {time.time() - start_time}')
        print('Test passed!')


def test_qualtran_adder_reconstruction():
    # append i, op_count, time for cirq_to_db and time for db_to_cirq
    times = []
    for n_bits in range(2, 30):
        print(f'Adder test {n_bits}')
        initial_circuit = get_adder(n_bits=n_bits)

        start_cirq_to_db = time.time()
        db_tuples, _ = cirq_to_pandora(cirq_circuit=initial_circuit, last_id=0, label='adder', add_margins=True)
        time_cirq_to_db = time.time() - start_cirq_to_db

        start_db_to_cirq = time.time()
        reconstructed_circuit = pandora_to_cirq(pandora_gates=db_tuples)
        time_db_to_cirq = time.time() - start_db_to_cirq

        times.append((n_bits, len(db_tuples), time_cirq_to_db, time_db_to_cirq))

        # remove classical controls
        cl_ctrl_free_initial = cirq.Circuit()
        for op in initial_circuit.all_operations():
            cl_ctrl_free_initial.append(op.without_classical_controls())

        # remove In/Out gates from reconstruction
        io_free_reconstructed = cirq.Circuit()
        for op in reconstructed_circuit.all_operations():
            if not isinstance(op.gate, In) and not isinstance(op.gate, Out):
                io_free_reconstructed.append(op)

        # use the same qubits for both circuits
        qubit_map = dict(
            zip(
                sorted(io_free_reconstructed.all_qubits()),
                sorted(cl_ctrl_free_initial.all_qubits())
            )
        )

        io_free_reconstructed = io_free_reconstructed.transform_qubits(qubit_map=qubit_map)
        assert str(cl_ctrl_free_initial) == str(io_free_reconstructed)
        print('Test passed!')

    return times


def test_qualtran_qrom_reconstruction():
    # append i, time for cirq_to_db and time for db_to_cirq
    times = []
    for i in range(2, 30):
        print(f'QROM test {i}')
        data = [*range(1, i)]
        initial_circuit = get_qrom(data=data)

        start_cirq_to_db = time.time()
        db_tuples, _ = cirq_to_pandora(cirq_circuit=initial_circuit, last_id=0, label='qrom', add_margins=True)
        time_cirq_to_db = time.time() - start_cirq_to_db

        start_db_to_cirq = time.time()
        reconstructed_circuit = pandora_to_cirq(pandora_gates=db_tuples)
        time_db_to_cirq = time.time() - start_db_to_cirq

        times.append((i, len(db_tuples), time_cirq_to_db, time_db_to_cirq))

        # remove classical controls
        cl_ctrl_free_initial = cirq.Circuit()
        for op in initial_circuit.all_operations():
            cl_ctrl_free_initial.append(op.without_classical_controls())

        # remove In/Out gates from reconstruction
        io_free_reconstructed = cirq.Circuit()
        for op in reconstructed_circuit.all_operations():
            if not isinstance(op.gate, In) and not isinstance(op.gate, Out):
                io_free_reconstructed.append(op)

        # use the same qubits for both circuits
        qubit_map = dict(
            zip(
                sorted(io_free_reconstructed.all_qubits()),
                sorted(cl_ctrl_free_initial.all_qubits())
            )
        )
        io_free_reconstructed = io_free_reconstructed.transform_qubits(qubit_map=qubit_map)
        assert str(cl_ctrl_free_initial) == str(io_free_reconstructed)
        print('Test passed!')

    return times


def test_qualtran_qpe_reconstruction():
    qpe_circuit = get_qpe_of_1d_ising_model(num_sites=2, m_bits=2)

    start_cirq_to_db = time.time()
    db_tuples, _ = cirq_to_pandora(cirq_circuit=qpe_circuit, last_id=0, label='qpe', add_margins=True)

    print(f'Cirq to pandora: {time.time() - start_cirq_to_db}')

    start_db_to_cirq = time.time()
    reconstructed_circuit = pandora_to_cirq(pandora_gates=db_tuples)
    print(f'Pandora to cirq: {time.time() - start_db_to_cirq}')

    # remove classical controls
    cl_ctrl_free_initial = cirq.Circuit()
    for op in qpe_circuit.all_operations():
        cl_ctrl_free_initial.append(op.without_classical_controls())

    # remove In/Out gates from reconstruction
    io_free_reconstructed = cirq.Circuit()
    for op in reconstructed_circuit.all_operations():
        if not isinstance(op.gate, In) and not isinstance(op.gate, Out):
            io_free_reconstructed.append(op)

    # use the same qubits for both circuits
    qubit_map = dict(
        zip(
            sorted(io_free_reconstructed.all_qubits()),
            sorted(cl_ctrl_free_initial.all_qubits())
        )
    )
    io_free_reconstructed = io_free_reconstructed.transform_qubits(qubit_map=qubit_map)

    assert len(list(cl_ctrl_free_initial.all_operations())) == len(list(io_free_reconstructed.all_operations()))
    for op_1, op_2 in zip(cl_ctrl_free_initial.all_operations(), io_free_reconstructed.all_operations()):
        assert type(op_1) == type(op_2)
    print('Test passed!')


def test_qualtran_hubbard_reconstruction():
    # TODO fix this
    x_dim, y_dim = 2, 2
    t = 1
    mu = 4 * t
    N = x_dim * y_dim * 2
    qlambda = 2 * N * t + (N * mu) // 2
    delta_E = t / 100
    m_bits = int(np.ceil(np.log2(qlambda * np.pi * np.sqrt(2) / delta_E)))
    walk = get_walk_operator_for_hubbard_model(x_dim, y_dim, t, mu)
    circuit = cirq.Circuit(phase_estimation(walk, m=m_bits))
    context = cirq.DecompositionContext(qubit_manager=cirq.SimpleQubitManager())
    hubbard_circuit = cirq.Circuit(cirq.decompose(circuit, keep=keep, context=context))

    final_ops = []
    for op in hubbard_circuit.all_operations():
        if isinstance(op.gate, Adjoint):
            sub_bloq = op.gate.subbloq
            my_ops = list(decompose_qualtran_bloq_gate(sub_bloq))
            final_ops = final_ops + my_ops
        if isinstance(op.gate, ModAddK):
            # TODO
            pass
        if isinstance(op.gate, BloqAsCirqGate):
            if isinstance(op.gate.bloq, TwoBitCSwap):
                final_ops = final_ops + decompose_fredkin(op)
            else:
                my_ops = list(decompose_qualtran_bloq_gate(op.gate.bloq))
                final_ops = final_ops + my_ops
        else:
            final_ops.append(op)

    print(f'Number of ops: {len(final_ops)}')

    start_create = time.time()
    hubbard_circuit = cirq.Circuit(final_ops)
    print(f'Time to create: {time.time() - start_create}')

    start_cirq_to_pandora = time.time()
    db_tuples, _ = cirq_to_pandora(cirq_circuit=hubbard_circuit, last_id=0, label='qrom', add_margins=True)
    print(f'Time to cirq_to_pandora: {time.time() - start_cirq_to_pandora}')


if __name__ == "__main__":
    circuit = benchmarking.benchmark_cirq.create_random_circuit(n_qubits=5, n_templates=10)
    test_random_reconstruction(n_circuits=10)
    test_qualtran_adder_reconstruction()
    test_qualtran_qrom_reconstruction()
    test_qualtran_qpe_reconstruction()
    # test_qualtran_hubbard_reconstruction()
