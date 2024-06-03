import time

import psycopg2

from qualtran2db import *
from cirq2db import *
import benchmarking.benchmark_cirq
from _connection import *

connection = psycopg2.connect(
    database="postgres",
    # user="postgres",
    host="localhost",
    port=5432,
    password="1234")


def test_random_reconstruction(n_circuits=100):
    templates = ['add_two_hadamards', 'add_two_cnots', 'add_base_change', 'add_t_t_dag', 'add_t_cx', 'add_cx_t']
    for i in range(n_circuits):
        print(f'Random test {i}')
        start_time = time.time()
        initial_circuit = benchmarking.benchmark_cirq.create_random_circuit(n_qubits=3,
                                                                            n_templates=3,
                                                                            templates=templates, add_margins=True)

        print(f'Time for create_random_circuit: {time.time() - start_time}')

        start_time = time.time()
        db_tuples, _ = cirq_to_db(cirq_circuit=initial_circuit, last_id=0, label='test', add_margins=False)
        print(f'Time for cirq_to_db: {time.time() - start_time}')

        start_time = time.time()
        reconstructed_circuit = db_to_cirq(db_tuples=db_tuples, with_tags=False)
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
    for n_bits in range(2, 50):
        print(f'Adder test {n_bits}')
        bloq = Add(QUInt(n_bits))
        initial_circuit = get_clifford_plus_t_cirq_circuit_for_bloq(bloq)
        assert_circuit_in_clifford_plus_t(initial_circuit)

        db_tuples, _ = cirq_to_db(cirq_circuit=initial_circuit, last_id=0, label='adder', add_margins=True)
        reconstructed_circuit = db_to_cirq(db_tuples=db_tuples, with_tags=False)

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
        print(cl_ctrl_free_initial)
        print(io_free_reconstructed)
        assert str(cl_ctrl_free_initial) == str(io_free_reconstructed)
        print('Test passed!')


def test_qualtran_qrom_reconstruction():
    for i in range(2, 100):
        print(f'QROM test {i}')
        data = [*range(1, i)]
        bloq = QROM.build(data)
        initial_circuit = get_clifford_plus_t_cirq_circuit_for_bloq(bloq)

        db_tuples, _ = cirq_to_db(cirq_circuit=initial_circuit, last_id=0, label='qrom', add_margins=True)
        reconstructed_circuit = db_to_cirq(db_tuples=db_tuples, with_tags=False)

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


def test_qualtran_qpe_reconstruction():
    num_sites: int = 2
    eps: float = 1e-2
    m_bits: int = 2

    circuit = cirq.Circuit(phase_estimation(get_walk_operator_for_1d_ising_model(num_sites, eps), m=m_bits))
    context = cirq.DecompositionContext(qubit_manager=cirq.SimpleQubitManager())
    circuit = cirq.Circuit(cirq.decompose(circuit, keep=keep, context=context))

    final_ops = []
    for op in circuit.all_operations():
        if isinstance(op.gate, cirq.GlobalPhaseGate):
            continue
        if isinstance(op.gate, qualtran.cirq_interop.BloqAsCirqGate):
            if isinstance(op.gate.bloq, qualtran.bloqs.basic_gates.swap.TwoBitCSwap):
                ctrl, x, y = op.qubits
                context = cirq.DecompositionContext(qubit_manager=cirq.SimpleQubitManager())
                ops = op.gate.bloq.decompose_from_registers(ctrl=[ctrl], x=[x], y=[y], context=context)
                for o in ops:
                    for x in o:
                        final_ops.append(x)
            elif isinstance(op.gate.bloq, qualtran.bloqs.basic_gates.cnot.CNOT):
                ctrl, tgt = op.qubits
                cx = op.gate.bloq.as_cirq_op(qubit_manager=cirq.SimpleQubitManager(),
                                             ctrl=[ctrl],
                                             target=[tgt]
                                             )
                final_ops.append(cx[0])
        else:
            final_ops.append(op)

    initial_circuit = cirq.Circuit(final_ops)

    start_time = time.time()
    db_tuples, _ = cirq_to_db(cirq_circuit=initial_circuit, last_id=0, label='qpe', add_margins=True)
    print(f'Time for cirq_to_db: {time.time() - start_time}')

    start_time = time.time()
    reconstructed_circuit = db_to_cirq(db_tuples=db_tuples, with_tags=False)
    print(f'Time for db_to_cirq: {time.time() - start_time}')

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
    start_time = time.time()
    io_free_reconstructed = io_free_reconstructed.transform_qubits(qubit_map=qubit_map)
    print(f'Time for transform_qubits: {time.time() - start_time}')

    assert str(cl_ctrl_free_initial) == str(io_free_reconstructed)
    print('Test passed!')


if __name__ == "__main__":
    # circuit = benchmarking.benchmark_cirq.create_random_circuit(n_qubits=5, n_templates=10)
    # test_random_reconstruction(n_circuits=100)
    # test_qualtran_adder_reconstruction()
    # test_qualtran_qrom_reconstruction()
    test_qualtran_qpe_reconstruction()
