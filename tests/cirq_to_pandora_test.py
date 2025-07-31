import benchmarking.benchmark_cirq
from pandora.connection_util import *

from qualtran.bloqs.arithmetic.addition import Add
from qualtran.bloqs.data_loading import QROM
from qualtran import QUInt

from pandora.qualtran_to_pandora_util import get_cirq_circuit_for_bloq, assert_circuit_is_pandora_ingestible

class TimeoutException(Exception):
    pass


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

def handler(signum, frame):
    raise TimeoutException("Extraction took too long (possible infinite loop).")

def test_toffoli_cnot_transformation(connection):
    """
    Test the transformation of Toffoli followed by CNOT to CNOT followed by Toffoli.
    """
    cursor = connection.cursor()

    # Reset the database
    cursor.execute("TRUNCATE TABLE linked_circuit;")
    connection.commit()

    drop_and_replace_tables(connection=connection, clean=True)
    refresh_all_stored_procedures(connection=connection)
    reset_database_id(connection, table_name='linked_circuit', large_buffer_value=100000)

    # Use LineQubit and .on() for consistency
    q = [cirq.LineQubit(i) for i in range(5)]
    initial_circuit = cirq.Circuit([
        cirq.TOFFOLI.on(q[1], q[2], q[3]),  # Toffoli
        cirq.CNOT.on(q[3], q[2])            # CNOT
    ])

    # Expected circuit (A2) using the same qubits
    expected_circuit = cirq.Circuit([
        cirq.CNOT.on(q[3], q[2]),
        cirq.TOFFOLI.on(q[1], q[2], q[3]),
        cirq.TOFFOLI.on(q[1], q[2], q[4]),
        cirq.CNOT.on(q[3], q[4]),
        cirq.CNOT.on(q[3], q[0]),
        cirq.CNOT.on(q[2], q[0]),
        cirq.TOFFOLI.on(q[2], q[1], q[0]),
        cirq.TOFFOLI.on(q[1], q[4], q[3]),
        cirq.TOFFOLI.on(q[0], q[1], q[2]),
        cirq.CNOT.on(q[2], q[4]),
        cirq.TOFFOLI.on(q[0], q[1], q[4]),
        cirq.CNOT.on(q[0], q[4]),
        cirq.CNOT.on(q[2], q[0]),
        cirq.CNOT.on(q[3], q[0])
    ])

    print("Initial circuit (A1):")
    print(initial_circuit)
    print("Expected circuit (A2):")
    print(expected_circuit)

    # Convert to Pandora format
    pandora_gates, _ = cirq_to_pandora(cirq_circuit=initial_circuit,
                                       last_id=0,
                                       add_margins=True,
                                       label='toffoli_cnot_test')

    insert_in_batches(pandora_gates=pandora_gates,
                      connection=connection,
                      table_name='linked_circuit')

    # Set a timeout for extraction (e.g., 5 seconds)
    import signal
    signal.signal(signal.SIGALRM, handler)
    signal.alarm(2)
    try:
        extracted_circuit = extract_cirq_circuit(connection=connection,
                                             circuit_label='toffoli_cnot_test',
                                             remove_io_gates=True,
                                             table_name='linked_circuit',is_test=False)
        print("Extracted circuit:")
        print(extracted_circuit)
    except TimeoutException as e:
        print(e)
    finally:
        signal.alarm(0)  # Disable the alarm

    # Call the Toffoli decomposition/transformation procedure
    cursor = connection.cursor()
    cursor.execute("CALL linked_toffoli_cnot_transform();")
    connection.commit()

     # Set a timeout for extraction (e.g., 5 seconds)
    signal.signal(signal.SIGALRM, handler)
    signal.alarm(2)
    try:
        extracted_circuit_after = extract_cirq_circuit(connection=connection,
                                                       circuit_label='toffoli_cnot_test',
                                                       remove_io_gates=True,
                                                       table_name='linked_circuit', is_test=False)
        print("Extracted circuit AFTER transformation:")
        print(extracted_circuit_after)
    except TimeoutException as e:
        print(e)
    finally:
        signal.alarm(0)  # Disable the alarm
    
    
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
    conn = get_connection(config_file_path=sys.argv[1])
    #test_random_reconstruction(n_circuits=10)
    #test_qualtran_adder_reconstruction(connection=conn)
    #test_qualtran_qrom_reconstruction(connection=conn)
    test_toffoli_cnot_transformation(connection=conn)
    conn.close()