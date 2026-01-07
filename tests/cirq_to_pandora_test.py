from pandora.connection_util import *

from qualtran.bloqs.arithmetic.addition import Add
from qualtran.bloqs.data_loading import QROM
from qualtran import QUInt

from pandora.gates import pandora_to_cirq_circuit, annotate_pandora_gates
from pandora.qualtran_to_pandora_util import get_cirq_circuit_for_bloq, assert_circuit_is_pandora_ingestible

from pandora.cirq_util import create_random_circuit


def test_random_reconstruction(n_circuits=100):
    templates = ['add_two_hadamards', 'add_two_cnots', 'add_base_change', 'add_t_t_dag', 'add_t_cx', 'add_cx_t']
    for i in range(n_circuits):
        print(f'Random test {i}')
        start_time = time.time()
        initial_circuit = create_random_circuit(n_qubits=3, n_templates=3, templates=templates)

        print(f'Time for create_random_circuit: {time.time() - start_time}')

        start_time = time.time()
        pandora_gates, last_id = cirq_to_pandora(cirq_circuit=initial_circuit, last_id=0, label='t', add_margins=False)

        print(f'Time for cirq_to_db: {time.time() - start_time}')

        start_time = time.time()
        wrapped_gates, n_qubits = annotate_pandora_gates(gates=pandora_gates)

        reconstructed_circuit = pandora_to_cirq_circuit(gates=wrapped_gates, n_qubits=n_qubits)

        print(f'Time for db_to_cirq: {time.time() - start_time}')

        qubit_map = dict(
            zip(
                sorted(initial_circuit.all_qubits()),
                sorted(reconstructed_circuit.all_qubits())
            )
        )
        initial_circuit = initial_circuit.transform_qubits(qubit_map=qubit_map)

        start_time = time.time()

        print(reconstructed_circuit)
        print(initial_circuit)

        assert str(reconstructed_circuit) == str(initial_circuit)
        print(f'Time for assertion: {time.time() - start_time}')
        print('Test passed!')


def test_reconstruction(connection, full_circuit):
    assert_circuit_is_pandora_ingestible(full_circuit)

    drop_and_replace_tables(connection=connection, clean=True)
    refresh_all_stored_procedures(connection=connection)
    reset_database_id(connection, table_name='linked_circuit_test', large_buffer_value=100000)

    circuit_batches = windowed_cirq_to_pandora(circuit=full_circuit, window_size=2)
    qubit_dict = dict((str(qubit), i) for i, qubit in enumerate(sorted(full_circuit.all_qubits(),
                                                                       key=lambda q: str(q))))
    for (batch, _) in circuit_batches:
        insert_single_batch(connection=connection,
                            batch=batch,
                            is_test=True,
                            table_name='linked_circuit_test')

    extracted_circuit = extract_cirq_circuit(connection=connection,
                                             circuit_label='x',
                                             remove_io_gates=True,
                                             table_name='linked_circuit_test',
                                             original_qubits_test=qubit_dict,
                                             just_count=False)

    init_circuit = remove_measurements(remove_classically_controlled_ops(full_circuit))
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

    for (op_1, op_2) in zip(init_ops, final_ops):
        assert op_1.gate.__class__.__name__ == op_2.gate.__class__.__name__

def test_qualtran_adder_reconstruction(connection):
    for n_bits in range(2, 30):
        print(f'Adder test {n_bits}')
        bloq = Add(QUInt(n_bits))
        full_circuit = get_cirq_circuit_for_bloq(bloq)

        test_reconstruction(connection=connection, full_circuit=full_circuit)
        print(f'Passed adder({n_bits})!')


def test_qualtran_qrom_reconstruction(connection):
    times = []
    for i in range(3, 30):
        print(f'QROM test {i}')
        data = [*range(1, i)]
        bloq = QROM.build_from_data(data)
        full_circuit = get_cirq_circuit_for_bloq(bloq)

        test_reconstruction(connection=connection, full_circuit=full_circuit)
        print(f'Passed qrom({i})!')

    return times


if __name__ == "__main__":
    conn = get_connection()

    test_random_reconstruction(n_circuits=10)
    # test_qualtran_adder_reconstruction(connection=conn)
    test_qualtran_qrom_reconstruction(connection=conn)

    conn.close()
