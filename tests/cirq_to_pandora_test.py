import csv
import time

import benchmarking.benchmark_cirq
from pandora.qualtran_to_pandora_util import get_adder, get_qrom, get_qpe_of_1d_ising_model, get_adder_as_cirq_circuit, \
    get_qrom_as_cirq_circuit
from pandora.connection_util import *


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


def test_qualtran_adder_reconstruction(connection):
    # append i, op_count, time for cirq_to_db and time for db_to_cirq
    for n_bits in range(2, 30):
        print(f'Adder test {n_bits}')

        drop_and_replace_tables(connection=connection, clean=True)
        refresh_all_stored_procedures(connection=connection)
        reset_database_id(connection, table_name='linked_circuit_test', large_buffer_value=100000)

        adder_batches = get_adder(n_bits, window_size=2, is_test=True)
        full_adder_circuit = get_adder_as_cirq_circuit(n_bits=n_bits)

        qubit_dict = dict((str(qubit), i) for i, qubit in enumerate(sorted(full_adder_circuit.all_qubits(),
                                                                           key=lambda q: str(q))))
        for i, batch in enumerate(adder_batches):
            insert_single_batch(connection=connection, batch=batch, is_test=True)

        extracted_circuit: cirq.Circuit = extract_cirq_circuit(connection=connection,
                                                               circuit_label='x',
                                                               remove_io_gates=True,
                                                               table_name='linked_circuit_test',
                                                               original_qubits_test=qubit_dict)

        init_circuit = remove_measurements(remove_classically_controlled_ops(full_adder_circuit))
        extracted_circuit = remove_measurements(remove_classically_controlled_ops(extracted_circuit))

        # use the same qubits for both circuits
        qubit_map = dict(
            zip(
                sorted(init_circuit.all_qubits()),
                sorted(extracted_circuit.all_qubits())
            )
        )
        init_circuit = init_circuit.transform_qubits(qubit_map=qubit_map)

        init_ops = list(init_circuit.all_operations())
        final_ops = list(extracted_circuit.all_operations())
        assert len(init_ops) == len(final_ops)

        for i, (op_1, op_2) in enumerate(zip(init_ops, final_ops)):
            assert op_1.gate.__class__.__name__ == op_2.gate.__class__.__name__

        print(f'Passed adder({n_bits})!')


def test_qualtran_qrom_reconstruction(connection):
    # append i, time for cirq_to_db and time for db_to_cirq
    times = []
    for i in range(2, 30):
        print(f'QROM test {i}')
        data = [*range(1, i)]

        drop_and_replace_tables(connection=connection, clean=True)
        refresh_all_stored_procedures(connection=connection)
        reset_database_id(connection, table_name='linked_circuit_test', large_buffer_value=100000)

        qrom_batches = get_qrom(data=data, window_size=2, is_test=True)
        full_qrom_circuit = get_qrom_as_cirq_circuit(data=data)

        qubit_dict = dict((str(qubit), i) for i, qubit in enumerate(sorted(full_qrom_circuit.all_qubits(),
                                                                           key=lambda q: str(q))))
        for i, batch in enumerate(qrom_batches):
            insert_single_batch(connection=connection, batch=batch, is_test=True)

        extracted_circuit: cirq.Circuit = extract_cirq_circuit(connection=connection,
                                                               circuit_label='x',
                                                               remove_io_gates=True,
                                                               table_name='linked_circuit_test',
                                                               original_qubits_test=qubit_dict)

        init_circuit = remove_measurements(remove_classically_controlled_ops(full_qrom_circuit))
        extracted_circuit = remove_measurements(remove_classically_controlled_ops(extracted_circuit))

        # use the same qubits for both circuits
        qubit_map = dict(
            zip(
                sorted(init_circuit.all_qubits()),
                sorted(extracted_circuit.all_qubits())
            )
        )
        init_circuit = init_circuit.transform_qubits(qubit_map=qubit_map)

        init_ops = list(init_circuit.all_operations())
        final_ops = list(extracted_circuit.all_operations())
        assert len(init_ops) == len(final_ops)

        for i, (op_1, op_2) in enumerate(zip(init_ops, final_ops)):
            assert op_1.gate.__class__.__name__ == op_2.gate.__class__.__name__

        print(f'Passed qrom({i})!')

    return times


if __name__ == "__main__":
    conn = get_connection()
    test_random_reconstruction(n_circuits=10)
    test_qualtran_adder_reconstruction(connection=conn)
    test_qualtran_qrom_reconstruction(connection=conn)
    conn.close()
