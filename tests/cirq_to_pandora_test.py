import csv
import time

import benchmarking.benchmark_cirq
from pandora.qualtran_to_pandora_util import get_adder, get_qrom, get_qpe_of_1d_ising_model
from pandora.connection_util import *
from pandora.plot_utils import plot3dsurface


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
        db_tuples, last_id = cirq_to_pandora(cirq_circuit=initial_circuit, last_id=0, label='t', add_margins=False)
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
        db_tuples, _ = cirq_to_pandora(cirq_circuit=initial_circuit, last_id=0, label='a', add_margins=True)
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
        db_tuples, _ = cirq_to_pandora(cirq_circuit=initial_circuit, last_id=0, label='r', add_margins=True)
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
    n_sites = [1, 2, 3]
    m_bits = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]

    n_tup = []
    times = []
    all_sites = []
    all_bits = []
    for n_s in n_sites:
        for bits in m_bits:
            print(f'Reached {n_s} and {bits}')
            start_global = time.time()
            qpe_circuit = get_qpe_of_1d_ising_model(num_sites=n_s, m_bits=bits)
            db_tuples, _ = cirq_to_pandora(cirq_circuit=qpe_circuit, last_id=0, label='q', add_margins=True)

            connection = get_connection()
            drop_and_replace_tables(connection=connection, clean=True)
            refresh_all_stored_procedures(connection=connection)
            reset_database_id(connection, table_name='linked_circuit', large_buffer_value=1000)
            insert_in_batches(pandora_gates=db_tuples,
                              connection=connection,
                              batch_size=1000000,
                              table_name='linked_circuit')

            n_tup.append(len(db_tuples))
            all_sites.append(n_s)
            all_bits.append(bits)
            times.append(time.time() - start_global)

    rows = zip(all_sites, all_bits, n_tup, times)
    with open('qpe_bench.csv', 'w') as f:
        writer = csv.writer(f)
        writer.writerow(['n_sites', 'n_bits', 'gate_count', 'time'])
        for row in rows:
            writer.writerow(row)

    # start_db_to_cirq = time.time()
    # reconstructed_circuit = pandora_to_cirq(pandora_gates=db_tuples)
    # print(f'Pandora to cirq: {time.time() - start_db_to_cirq}')
    #
    # # remove classical controls
    # cl_ctrl_free_initial = cirq.Circuit()
    # for op in qpe_circuit.all_operations():
    #     cl_ctrl_free_initial.append(op.without_classical_controls())
    #
    # # remove In/Out gates from reconstruction
    # io_free_reconstructed = cirq.Circuit()
    # for op in reconstructed_circuit.all_operations():
    #     if not isinstance(op.gate, In) and not isinstance(op.gate, Out):
    #         io_free_reconstructed.append(op)
    #
    # # use the same qubits for both circuits
    # qubit_map = dict(
    #     zip(
    #         sorted(io_free_reconstructed.all_qubits()),
    #         sorted(cl_ctrl_free_initial.all_qubits())
    #     )
    # )
    # io_free_reconstructed = io_free_reconstructed.transform_qubits(qubit_map=qubit_map)
    #
    # cl_free_ops = cl_ctrl_free_initial.all_operations()
    # io_free_ops = io_free_reconstructed.all_operations()
    # assert len(list(cl_free_ops)) == len(list(io_free_ops))
    # for op_1, op_2 in zip(cl_free_ops, io_free_ops):
    #     assert type(op_1) == type(op_2)
    # print('Test passed!')


if __name__ == "__main__":
    circuit = benchmarking.benchmark_cirq.create_random_circuit(n_qubits=5, n_templates=10)
    test_random_reconstruction(n_circuits=10)
    test_qualtran_adder_reconstruction()
    test_qualtran_qrom_reconstruction()
    test_qualtran_qpe_reconstruction()
    plot3dsurface()
