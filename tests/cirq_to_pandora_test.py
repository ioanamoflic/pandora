import benchmarking.cirq_util
from pandora.connection_util import *

from qualtran.bloqs.arithmetic.addition import Add
from qualtran.bloqs.data_loading import QROM
from qualtran import QUInt

from pandora.pandora_util import pandora_to_circuit
from pandora.qualtran_to_pandora_util import get_cirq_circuit_for_bloq, assert_circuit_is_pandora_ingestible


def get_adder_as_cirq_circuit(n_bits) -> cirq.Circuit:
    """
    Used of testing.
    """
    bloq = Add(QUInt(n_bits))
    clifford_t_circuit = get_cirq_circuit_for_bloq(bloq)
    assert_circuit_is_pandora_ingestible(clifford_t_circuit)
    return clifford_t_circuit


def get_qrom_as_cirq_circuit(data) -> cirq.Circuit:
    """
    Used of testing.
    """
    bloq = QROM.build_from_data(data)
    qrom_circuit = get_cirq_circuit_for_bloq(bloq)
    return qrom_circuit


def test_random_reconstruction(n_circuits=100):
    templates = ['add_two_hadamards', 'add_two_cnots', 'add_base_change', 'add_t_t_dag', 'add_t_cx', 'add_cx_t']
    for i in range(n_circuits):
        print(f'Random test {i}')
        start_time = time.time()
        initial_circuit = benchmarking.cirq_util.create_random_circuit(n_qubits=3,
                                                                       n_templates=3,
                                                                       templates=templates, add_margins=True)

        print(f'Time for create_random_circuit: {time.time() - start_time}')

        start_time = time.time()
        db_tuples, last_id = cirq_to_pandora(cirq_circuit=initial_circuit, last_id=0, label='t', add_margins=False)
        print(f'Time for cirq_to_db: {time.time() - start_time}')

        start_time = time.time()
        reconstructed_circuit = pandora_to_circuit(pandora_gates=db_tuples)
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

    cirq_gate_set_test = cirq.Gateset(
        cirq.Rz, cirq.Rx, cirq.Ry,
        cirq.MeasurementGate, cirq.ResetChannel,
        cirq.ZPowGate, cirq.XPowGate, cirq.YPowGate, cirq.HPowGate,
        cirq.CZPowGate, cirq.CXPowGate,
        cirq.X, cirq.Y, cirq.Z)

    for n_bits in range(2, 30):
        print(f'Adder test {n_bits}')

        drop_and_replace_tables(connection=connection, clean=True)
        refresh_all_stored_procedures(connection=connection)
        reset_database_id(connection, table_name='linked_circuit_test', large_buffer_value=100000)

        full_adder_circuit = get_adder_as_cirq_circuit(n_bits=n_bits)

        adder_batches = windowed_cirq_to_pandora(circuit=full_adder_circuit,
                                                 window_size=2,
                                                 is_test=True)

        qubit_dict = dict((str(qubit), i) for i, qubit in enumerate(sorted(full_adder_circuit.all_qubits(),
                                                                           key=lambda q: str(q))))
        for i, (batch, _) in enumerate(adder_batches):
            insert_single_batch(connection=connection,
                                batch=batch,
                                is_test=True,
                                table_name='linked_circuit_test')

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

        full_qrom_circuit = get_qrom_as_cirq_circuit(data=data)
        qrom_batches = windowed_cirq_to_pandora(circuit=full_qrom_circuit,
                                                window_size=2,
                                                is_test=True)

        qubit_dict = dict((str(qubit), i) for i, qubit in enumerate(sorted(full_qrom_circuit.all_qubits(),
                                                                           key=lambda q: str(q))))
        for i, (batch, _) in enumerate(qrom_batches):
            insert_single_batch(connection=connection,
                                is_test=True,
                                batch=batch,
                                table_name='linked_circuit_test')

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
