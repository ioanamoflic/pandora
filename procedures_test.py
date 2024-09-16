import random

import psycopg2

from benchmarking import benchmark_cirq
from cirq2db import *
from _connection import *
from main import db_multi_threaded
from qualtran2db import *
import numpy as np

connection = psycopg2.connect(
    database="postgres",
    # user="postgres",
    host="localhost",
    port=5432,
    password="1234")

cursor = connection.cursor()
connection.set_session(autocommit=True)

if connection:
    print("Connection to the PostgreSQL established successfully.")
else:
    print("Connection to the PostgreSQL encountered and error.")


def test_cancel_single_qubit():
    create_linked_table(conn=connection, table='linked_circuit_qubit', file='sql_generate_table_qubit.sql', clean=True)
    refresh_all_stored_procedures(conn=connection)

    qubit = cirq.NamedQubit('q')
    initial_circuit = cirq.Circuit([cirq.H.on(qubit), cirq.H.on(qubit)])

    db_tuples, _ = cirq_to_db(cirq_circuit=initial_circuit, last_id=0, add_margins=True, label='test_csq')
    insert_in_batches(db_tuples=db_tuples, table='linked_circuit_qubit', conn=connection)
    cursor.execute(f"call cancel_single_qubit('HPowGate', 'HPowGate', 10, 1)")
    extracted_circuit = extract_cirq_circuit(conn=connection,
                                             table='linked_circuit_qubit',
                                             circuit_label='test_csq',
                                             remove_io_gates=True)

    assert len(extracted_circuit) == 0
    print('Test cancel_single_qubit passed!')


def test_cancel_two_qubit():
    create_linked_table(conn=connection, table='linked_circuit_qubit', file='sql_generate_table_qubit.sql', clean=True)
    refresh_all_stored_procedures(conn=connection)

    q1, q2 = cirq.NamedQubit('q1'), cirq.NamedQubit('q2')
    initial_circuit = cirq.Circuit([cirq.CX.on(q1, q2), cirq.CX.on(q1, q2)])

    db_tuples, _ = cirq_to_db(cirq_circuit=initial_circuit, last_id=0, add_margins=True, label='test_ctq')
    insert_in_batches(db_tuples=db_tuples, table='linked_circuit_qubit', conn=connection)
    cursor.execute(f"call cancel_two_qubit('CXPowGate', 'CXPowGate', 10, 1)")
    extracted_circuit = extract_cirq_circuit(conn=connection,
                                             table='linked_circuit_qubit',
                                             circuit_label='test_ctq',
                                             remove_io_gates=True)

    assert len(extracted_circuit) == 0
    print('Test cancel_two_qubit passed!')


def test_commute_single_control_right():
    create_linked_table(conn=connection, table='linked_circuit_qubit', file='sql_generate_table_qubit.sql', clean=True)
    refresh_all_stored_procedures(conn=connection)

    q1, q2 = cirq.NamedQubit('q1'), cirq.NamedQubit('q2')
    initial_circuit = cirq.Circuit([cirq.CX.on(q1, q2), cirq.T.on(q1)])
    final_circuit = cirq.Circuit([cirq.T.on(q1), cirq.CX.on(q1, q2)])

    db_tuples, _ = cirq_to_db(cirq_circuit=initial_circuit, last_id=0, add_margins=True, label='test_cscr')
    insert_in_batches(db_tuples=db_tuples, table='linked_circuit_qubit', conn=connection)
    cursor.execute(f"call commute_single_control_right('ZPowGate**0.25', 10, 1)")
    extracted_circuit = extract_cirq_circuit(conn=connection,
                                             circuit_label='test_cscr',
                                             table='linked_circuit_qubit',
                                             remove_io_gates=True)

    qubit_map = dict(
        zip(
            sorted(final_circuit.all_qubits()),
            sorted(extracted_circuit.all_qubits())
        )
    )
    final_circuit = final_circuit.transform_qubits(qubit_map=qubit_map)
    print(extracted_circuit)
    print(final_circuit)
    assert str(final_circuit) == str(extracted_circuit)
    print('Test commute_single_control_right passed!')


def test_commute_single_control_left():
    create_linked_table(conn=connection, table='linked_circuit_qubit', file='sql_generate_table_qubit.sql', clean=True)
    refresh_all_stored_procedures(conn=connection)

    q1, q2 = cirq.NamedQubit('q1'), cirq.NamedQubit('q2')
    final_circuit = cirq.Circuit([cirq.CX.on(q1, q2), cirq.T.on(q1)])
    initial_circuit = cirq.Circuit([cirq.T.on(q1), cirq.CX.on(q1, q2)])

    db_tuples, _ = cirq_to_db(cirq_circuit=initial_circuit, last_id=0, add_margins=True, label='test_cscl')
    insert_in_batches(db_tuples=db_tuples, table='linked_circuit_qubit', conn=connection)
    cursor.execute(f"call commute_single_control_left('ZPowGate**0.25', 10, 1)")
    extracted_circuit = extract_cirq_circuit(conn=connection,
                                             table='linked_circuit_qubit',
                                             circuit_label='test_cscl',
                                             remove_io_gates=True)

    qubit_map = dict(
        zip(
            sorted(final_circuit.all_qubits()),
            sorted(extracted_circuit.all_qubits())
        )
    )
    final_circuit = final_circuit.transform_qubits(qubit_map=qubit_map)

    assert str(final_circuit) == str(extracted_circuit)
    print('Test commute_single_control_right passed!')


def test_cx_to_hhcxhh_a():
    create_linked_table(conn=connection, table='linked_circuit_qubit', file='sql_generate_table_qubit.sql', clean=True)
    refresh_all_stored_procedures(conn=connection)

    q1, q2 = cirq.NamedQubit('q1'), cirq.NamedQubit('q2')
    initial_circuit = cirq.Circuit([cirq.CX.on(q1, q2)])
    final_circuit = cirq.Circuit([cirq.H.on(q1), cirq.H.on(q2), cirq.CX.on(q2, q1), cirq.H.on(q1), cirq.H.on(q2)])

    db_tuples, _ = cirq_to_db(cirq_circuit=initial_circuit, last_id=0, add_margins=True, label='test_cscl')
    insert_in_batches(db_tuples=db_tuples, table='linked_circuit_qubit', conn=connection)
    cursor.execute("ALTER SEQUENCE linked_circuit_qubit_id_seq RESTART WITH 1000")
    cursor.execute(f"call linked_cx_to_hhcxhh(10, 1)")
    extracted_circuit = extract_cirq_circuit(conn=connection,
                                             table='linked_circuit_qubit',
                                             circuit_label='test_cscl',
                                             remove_io_gates=True)

    qubit_map = dict(
        zip(
            sorted(final_circuit.all_qubits()),
            sorted(extracted_circuit.all_qubits())
        )
    )
    final_circuit = final_circuit.transform_qubits(qubit_map=qubit_map)
    print(final_circuit)
    print(extracted_circuit)
    assert str(final_circuit) == str(extracted_circuit)
    print('Test cx_to_hhcxhh passed!')


def test_cx_to_hhcxhh_b():
    create_linked_table(conn=connection, table='linked_circuit_qubit', file='sql_generate_table_qubit.sql', clean=True)
    refresh_all_stored_procedures(conn=connection)

    q1, q2 = cirq.NamedQubit('q1'), cirq.NamedQubit('q2')
    initial_circuit = cirq.Circuit([cirq.CX.on(q2, q1)])
    final_circuit = cirq.Circuit([cirq.H.on(q1), cirq.H.on(q2), cirq.CX.on(q1, q2), cirq.H.on(q1), cirq.H.on(q2)])

    db_tuples, _ = cirq_to_db(cirq_circuit=initial_circuit, last_id=0, add_margins=True, label='test_cscl')
    insert_in_batches(db_tuples=db_tuples, table='linked_circuit_qubit', conn=connection)
    cursor.execute("ALTER SEQUENCE linked_circuit_qubit_id_seq RESTART WITH 1000")
    cursor.execute(f"call linked_cx_to_hhcxhh(10, 1)")
    extracted_circuit = extract_cirq_circuit(conn=connection,
                                             table='linked_circuit_qubit',
                                             circuit_label='test_cscl',
                                             remove_io_gates=True)

    qubit_map = dict(
        zip(
            sorted(final_circuit.all_qubits()),
            sorted(extracted_circuit.all_qubits())
        )
    )
    final_circuit = final_circuit.transform_qubits(qubit_map=qubit_map)

    assert str(final_circuit) == str(extracted_circuit)
    print('Test cx_to_hhcxhh passed!')


def test_hhcxhh_to_cx_a():
    create_linked_table(conn=connection, table='linked_circuit_qubit', file='sql_generate_table_qubit.sql', clean=True)
    refresh_all_stored_procedures(conn=connection)

    q1, q2 = cirq.NamedQubit('q1'), cirq.NamedQubit('q2')
    initial_circuit = cirq.Circuit([cirq.H.on(q1), cirq.H.on(q2), cirq.CX.on(q1, q2), cirq.H.on(q1), cirq.H.on(q2)])
    final_circuit = cirq.Circuit([cirq.CX.on(q2, q1)])

    db_tuples, _ = cirq_to_db(cirq_circuit=initial_circuit, last_id=0, add_margins=True, label='test_cscl')
    insert_in_batches(db_tuples=db_tuples, table='linked_circuit_qubit', conn=connection)
    cursor.execute(f"call linked_hhcxhh_to_cx(10, 1)")
    extracted_circuit = extract_cirq_circuit(conn=connection,
                                             table='linked_circuit_qubit',
                                             circuit_label='test_cscl',
                                             remove_io_gates=True)

    qubit_map = dict(
        zip(
            sorted(final_circuit.all_qubits()),
            sorted(extracted_circuit.all_qubits())
        )
    )
    final_circuit = final_circuit.transform_qubits(qubit_map=qubit_map)

    assert str(final_circuit) == str(extracted_circuit)
    print('Test hhcxhh_to_cx passed!')


def test_hhcxhh_to_cx_b():
    create_linked_table(conn=connection, file='sql_generate_table_qubit.sql', table='linked_circuit_qubit', clean=True)
    refresh_all_stored_procedures(conn=connection)

    q1, q2 = cirq.NamedQubit('q1'), cirq.NamedQubit('q2')
    initial_circuit = cirq.Circuit([cirq.H.on(q1), cirq.H.on(q2), cirq.CX.on(q2, q1), cirq.H.on(q1), cirq.H.on(q2)])
    final_circuit = cirq.Circuit([cirq.CX.on(q1, q2)])

    db_tuples, _ = cirq_to_db(cirq_circuit=initial_circuit, last_id=0, add_margins=True, label='test_cscl')
    insert_in_batches(db_tuples=db_tuples, table='linked_circuit_qubit', conn=connection)
    cursor.execute(f"call linked_hhcxhh_to_cx(10, 1)")
    extracted_circuit = extract_cirq_circuit(conn=connection,
                                             circuit_label='test_cscl',
                                             table='linked_circuit_qubit',
                                             remove_io_gates=True)

    qubit_map = dict(
        zip(
            sorted(final_circuit.all_qubits()),
            sorted(extracted_circuit.all_qubits())
        )
    )
    final_circuit = final_circuit.transform_qubits(qubit_map=qubit_map)

    assert str(final_circuit) == str(extracted_circuit)
    print('Test hhcxhh_to_cx passed!')


def test_replace_two_sq_with_one():
    create_linked_table(conn=connection, file='sql_generate_table_qubit.sql', clean=True,
                        table='linked_circuit_qubit', )
    refresh_all_stored_procedures(conn=connection)

    q = cirq.NamedQubit('q')
    initial_circuit = cirq.Circuit([cirq.T.on(q), cirq.T.on(q)])
    final_circuit = cirq.Circuit([cirq.T.on(q)])

    db_tuples, _ = cirq_to_db(cirq_circuit=initial_circuit, last_id=0, add_margins=True, label='test_rtswo')
    insert_in_batches(db_tuples=db_tuples, table='linked_circuit_qubit', conn=connection)
    cursor.execute(f"call replace_two_qubit('ZPowGate**0.25', 'ZPowGate**0.25', 'ZPowGate**0.5', 10, 1)")
    extracted_circuit = extract_cirq_circuit(conn=connection,
                                             table='linked_circuit_qubit',
                                             circuit_label='test_rtswo',
                                             remove_io_gates=True)

    qubit_map = dict(
        zip(
            sorted(final_circuit.all_qubits()),
            sorted(extracted_circuit.all_qubits())
        )
    )
    final_circuit = final_circuit.transform_qubits(qubit_map=qubit_map)

    assert str(final_circuit) == str(extracted_circuit)
    print('Test replace_two_sq_with_one passed!')


def test_commute_cx_ctrl():
    return NotImplementedError()


def test_commute_cx_target():
    return NotImplementedError()


def test_commute_cx_ctrl_target():
    return NotImplementedError()


def test_case_1():
    """
    Testing circuit

    q1: ───T───@───T^-1───@───
               │          │
    q2: ───────X──────────X───

    Should reduce to empty.
    """
    create_linked_table(conn=connection, file='sql_generate_table_qubit.sql', clean=True,
                        table='linked_circuit_qubit', )
    refresh_all_stored_procedures(conn=connection)

    q1, q2 = cirq.NamedQubit('q1'), cirq.NamedQubit('q2')
    initial_circuit = cirq.Circuit([cirq.T.on(q1), cirq.CX.on(q1, q2), cirq.T.on(q1) ** -1, cirq.CX.on(q1, q2)])
    print(initial_circuit)
    db_tuples, _ = cirq_to_db(cirq_circuit=initial_circuit, last_id=0, add_margins=True, label='test_case_1')
    insert_in_batches(db_tuples=db_tuples, table='linked_circuit_qubit', conn=connection)
    cursor.execute(f"call commute_single_control_right('ZPowGate**-0.25', 5, 1)")
    cursor.execute(f"call cancel_single_qubit('ZPowGate**0.25', 'ZPowGate**-0.25', 5, 1)")
    cursor.execute(f"call cancel_two_qubit('CXPowGate', 'CXPowGate', 5, 1)")
    extracted_circuit = extract_cirq_circuit(conn=connection,
                                             table='linked_circuit_qubit',
                                             circuit_label='test_case_1',
                                             remove_io_gates=True)

    assert len(extracted_circuit) == 0
    print('Test case 1 passed!')


def test_case_1_repeated(n):
    """
    Testing circuit

    q1: ───T───@───T^-1───@───
               │          │
    q2: ───────X──────────X───

    repeating n times.

    Should reduce to empty.
    """
    create_linked_table(conn=connection, file='sql_generate_table_qubit.sql', clean=True,
                        table='linked_circuit_qubit', )
    refresh_all_stored_procedures(conn=connection)

    def template(tup):
        q1, q2 = tup
        yield cirq.T.on(q1)
        yield cirq.CX.on(q1, q2)
        yield cirq.T.on(q1) ** -1
        yield cirq.CX.on(q1, q2)

    qubits = [cirq.NamedQubit(f'q{i}') for i in range(10)]
    initial_circuit = cirq.Circuit([template(random.sample(qubits, 2)) for _ in range(n)])

    db_tuples, _ = cirq_to_db(cirq_circuit=initial_circuit,
                              last_id=0,
                              add_margins=True,
                              label='test_case_1_r')
    insert_in_batches(db_tuples=db_tuples,
                      table='linked_circuit_qubit',
                      conn=connection)
    cursor.execute(f"call commute_single_control_right('ZPowGate**-0.25', 5, {n})")
    cursor.execute(f"call cancel_single_qubit('ZPowGate**0.25', 'ZPowGate**-0.25', 5, {n})")
    cursor.execute(f"call cancel_two_qubit('CXPowGate', 'CXPowGate', 5, {n})")
    extracted_circuit = extract_cirq_circuit(conn=connection,
                                             table='linked_circuit_qubit',
                                             circuit_label='test_case_1_r',
                                             remove_io_gates=True)

    assert len(extracted_circuit) == 0
    print('Test case 1 repeated passed!')


def test_case_2():
    """
    Testing circuit
    q1: ───T───@───T^-1───H───X───H───
               │              │
    q2: ───────X───H──────────@───H───
    Should reduce to empty.
    """
    create_linked_table(conn=connection, file='sql_generate_table_qubit.sql', clean=True,
                        table='linked_circuit_qubit', )
    refresh_all_stored_procedures(conn=connection)
    cursor.execute("ALTER SEQUENCE linked_circuit_qubit_id_seq RESTART WITH 1000")

    q1, q2 = cirq.NamedQubit('q1'), cirq.NamedQubit('q2')
    initial_circuit = cirq.Circuit([cirq.T.on(q1), cirq.CX.on(q1, q2), cirq.T.on(q1) ** -1,
                                    cirq.H.on(q1), cirq.H.on(q2), cirq.CX.on(q2, q1), cirq.H.on(q1), cirq.H.on(q2),
                                    cirq.H.on(q1), cirq.H.on(q1)])
    print(initial_circuit)
    db_tuples, _ = cirq_to_db(cirq_circuit=initial_circuit,
                              last_id=0,
                              add_margins=True,
                              label='test_case_2')
    insert_in_batches(db_tuples=db_tuples,
                      table='linked_circuit_qubit',
                      conn=connection)
    extracted_circuit = extract_cirq_circuit(conn=connection,
                                             circuit_label='test_case_2',
                                             table='linked_circuit_qubit',
                                             remove_io_gates=False,
                                             with_tags=True)
    print(extracted_circuit)
    cursor.execute(f"call commute_single_control_right('ZPowGate**-0.25', 100, 1)")
    cursor.execute(f"call cancel_single_qubit('ZPowGate**0.25', 'ZPowGate**-0.25', 100, 1)")
    extracted_circuit = extract_cirq_circuit(conn=connection,
                                             circuit_label='test_case_2',
                                             table='linked_circuit_qubit',
                                             remove_io_gates=False,
                                             with_tags=True)
    print(extracted_circuit)
    cursor.execute(f"call linked_hhcxhh_to_cx(10, 1)")
    cursor.execute(f"call cancel_two_qubit('CXPowGate', 'CXPowGate', 100, 1)")
    cursor.execute(f"call cancel_single_qubit('HPowGate', 'HPowGate', 100, 1)")
    extracted_circuit = extract_cirq_circuit(conn=connection,
                                             circuit_label='test_case_2',
                                             table='linked_circuit_qubit',
                                             remove_io_gates=True)

    assert len(extracted_circuit) == 0
    print('Test case 2 passed!')


def test_case_2_repeated(n):
    """
    Testing circuit

    q1: ───T───@───T^-1───H───X───H───
               │              │
    q2: ───────X───H──────────@───H───

    repeating n times.

    Should reduce to empty.
    """
    create_linked_table(conn=connection, file='sql_generate_table_qubit.sql', clean=True,
                        table='linked_circuit_qubit', )
    refresh_all_stored_procedures(conn=connection)
    cursor.execute("ALTER SEQUENCE linked_circuit_id_seq RESTART WITH 1000000")

    def template(tup):
        q1, q2 = tup
        yield cirq.T.on(q1)
        yield cirq.CX.on(q1, q2)
        yield cirq.T.on(q1) ** -1
        yield cirq.H.on(q1)
        yield cirq.H.on(q2)
        yield cirq.CX.on(q2, q1)
        yield cirq.H.on(q1)
        yield cirq.H.on(q2)

    qubits = [cirq.NamedQubit(f'q{i}') for i in range(10)]
    initial_circuit = cirq.Circuit([template(random.sample(qubits, 2)) for _ in range(n)])

    db_tuples, _ = cirq_to_db(cirq_circuit=initial_circuit,
                              last_id=0,
                              add_margins=True,
                              label='test_case_2_r')
    insert_in_batches(db_tuples=db_tuples,
                      conn=connection,
                      table='linked_circuit_qubit')
    cursor.execute(f"call linked_hhcxhh_to_cx(5, {n})")
    cursor.execute(f"call commute_single_control_right('ZPowGate**-0.25', 5, {n})")
    cursor.execute(f"call cancel_single_qubit('ZPowGate**0.25', 'ZPowGate**-0.25', 5, {n})")
    cursor.execute(f"call cancel_two_qubit('CXPowGate', 'CXPowGate', 5, {n})")
    extracted_circuit = extract_cirq_circuit(conn=connection,
                                             table='linked_circuit_qubit',
                                             circuit_label='test_case_2_r',
                                             remove_io_gates=True)

    assert len(extracted_circuit) == 0
    print('Test case 2 repeated passed!')


def test_qualtran_adder_opt_reconstruction(stop_after=15):
    """
    This method tries to optimize a qualtran adder for stop_after seconds and then reconstruct it.
    In case of errors, the reconstruction will most probably not work. This is used mainly for testing the correctness
    of procedures on this type of circuit.
    Args:
        stop_after: the time (in seconds) the optimizing procedures run for
    """
    for bit_size in range(4, 10):
        create_linked_table(conn=connection,
                            file='sql_generate_table_qubit.sql',
                            clean=True,
                            table='linked_circuit_qubit')
        refresh_all_stored_procedures(conn=connection)

        bloq = Add(QUInt(bit_size))
        circuit = get_clifford_plus_t_cirq_circuit_for_bloq(bloq)
        assert_circuit_in_clifford_plus_t(circuit)

        db_tuples, _ = cirq2db.cirq_to_db(cirq_circuit=circuit,
                                          last_id=0,
                                          label=f'Adder{bit_size}',
                                          add_margins=True)
        insert_in_batches(db_tuples=db_tuples,
                          conn=connection,
                          table='linked_circuit_qubit',
                          batch_size=100000)

        cursor.execute("ALTER SEQUENCE linked_circuit_qubit_id_seq RESTART WITH 1000000")

        thread_procedures = [
            (1, f"CALL cancel_single_qubit('HPowGate', 'HPowGate', 10, 10000000)"),
            (1, f"CALL cancel_single_qubit('ZPowGate**0.25', 'ZPowGate**-0.25', 10, 10000000)"),
            (1, f"CALL cancel_single_qubit('_PauliX', '_PauliX', 10, 10000000)"),
            (1, f"CALL cancel_two_qubit('CXPowGate', 'CXPowGate', 10, 10000000)"),
            (1, f"CALL replace_two_qubit('ZPowGate**0.25', 'ZPowGate**0.25', 'ZPowGate**0.5', 10, 10000000)"),
            (1, f"CALL replace_two_qubit('ZPowGate**-0.25', 'ZPowGate**-0.25', 'ZPowGate**-0.5', 10, 10000000)"),
            (1, f"CALL commute_single_control_left('ZPowGate**0.25', 10, 10000000)"),
            (1, f"CALL commute_single_control_left('ZPowGate**-0.25', 10, 10000000)"),
            (1, f"CALL commute_single_control_left('ZPowGate**0.5', 10, 10000000)"),
            (1, f"CALL commute_single_control_left('ZPowGate**-0.5', 10, 10000000)"),
            (1, f"CALL linked_hhcxhh_to_cx(10, 10000000);"),
            (1, f"CALL linked_cx_to_hhcxhh(10, 10000000);"),
            (1, f"CALL stopper({stop_after});")

        ]
        db_multi_threaded(thread_proc=thread_procedures)
        cursor.execute("update stop_condition set stop=False")
        extracted_circuit = extract_cirq_circuit(conn=connection,
                                                 circuit_label=f'Adder{bit_size}',
                                                 remove_io_gates=True,
                                                 table='linked_circuit_qubit', )
        print(extracted_circuit)
        assert np.allclose(circuit.unitary(), extracted_circuit.unitary())


def check_logical_correctness_random(stop_after: int):
    for n_qubits in range(2, 11):
        for n_templates in range(1, 50):
            create_linked_table(conn=connection, file='sql_generate_table_qubit.sql', clean=True,
                                table='linked_circuit_qubit')
            refresh_all_stored_procedures(conn=connection)

            initial_circuit = benchmark_cirq.create_random_circuit(n_qubits=n_qubits, n_templates=n_templates,
                                                                   templates=['add_two_hadamards',
                                                                              'add_two_cnots',
                                                                              'add_base_change',
                                                                              'add_t_t_dag',
                                                                              'add_t_cx',
                                                                              'add_cx_t'],
                                                                   add_margins=False)
            db_tuples, _ = cirq2db.cirq_to_db(cirq_circuit=initial_circuit,
                                              last_id=0,
                                              label=f'Test {n_qubits}',
                                              add_margins=True)
            insert_in_batches(db_tuples=db_tuples,
                              conn=connection,
                              batch_size=100000,
                              table='linked_circuit_qubit')

            cursor.execute("ALTER SEQUENCE linked_circuit_qubit_id_seq RESTART WITH 1000000")

            thread_procedures = [
                (1, f"CALL cancel_single_qubit('HPowGate', 'HPowGate', 10, 10000000)"),
                (1, f"CALL cancel_single_qubit('_PauliZ', '_PauliZ', 10, 10000000)"),
                (1, f"CALL cancel_single_qubit('ZPowGate**0.25', 'ZPowGate**-0.25', 10, 10000000)"),
                (1, f"CALL cancel_single_qubit('_PauliX', '_PauliX', 10, 10000000)"),
                (1, f"CALL cancel_two_qubit('CXPowGate', 'CXPowGate', 10, 10000000)"),
                (1, f"CALL replace_two_qubit('ZPowGate**0.25', 'ZPowGate**0.25', 'ZPowGate**0.5', 10, 10000000)"),
                (1, f"CALL replace_two_qubit('ZPowGate**0.5', 'ZPowGate**0.5', '_PauliZ', 10, 10000000)"),
                (1, f"CALL replace_two_qubit('ZPowGate**-0.25', 'ZPowGate**-0.25', 'ZPowGate**-0.5', 10, 10000000)"),
                (1, f"CALL commute_single_control_left('ZPowGate**0.25', 10, 10000000)"),
                (1, f"CALL commute_single_control_left('ZPowGate**-0.25', 10, 10000000)"),
                (1, f"CALL commute_single_control_left('ZPowGate**0.5', 10, 10000000)"),
                (1, f"CALL commute_single_control_left('ZPowGate**-0.5', 10, 10000000)"),
                (1, f"CALL linked_hhcxhh_to_cx(10, 10000000);"),
                (1, f"CALL linked_cx_to_hhcxhh(10, 10000000);"),
                (1, f"CALL stopper({stop_after});")
            ]

            db_multi_threaded(thread_proc=thread_procedures)
            cursor.execute("update stop_condition set stop=False")
            extracted_circuit = extract_cirq_circuit(conn=connection,
                                                     circuit_label=f'Test {n_qubits}',
                                                     remove_io_gates=False,
                                                     table='linked_circuit_qubit', )
            print('----------------------------------------------')
            print('Initial:')
            print(initial_circuit)
            print('Final:')
            print(extracted_circuit)
            assert np.allclose(initial_circuit.unitary(), extracted_circuit.unitary())


def test_BVZ_optimization(stop_after):
    for n_bits in range(2, 11):
        for secret in range(2 ** n_bits):
            secret_bin = '{0:b}'.format(secret)
            create_linked_table(conn=connection,
                                file='sql_generate_table_qubit.sql',
                                clean=True,
                                table='linked_circuit_qubit')
            refresh_all_stored_procedures(conn=connection)

            initial_circuit = benchmark_cirq.bernstein_vazirani(nr_bits=n_bits, secret=secret_bin)
            db_tuples, _ = cirq2db.cirq_to_db(cirq_circuit=initial_circuit,
                                              last_id=0,
                                              label=f'Test {n_bits}',
                                              add_margins=True)
            insert_in_batches(db_tuples=db_tuples,
                              conn=connection,
                              table='linked_circuit_qubit',
                              batch_size=100000)

            cursor.execute("ALTER SEQUENCE linked_circuit_qubit_id_seq RESTART WITH 1000000")

            thread_procedures = [
                (3, f"CALL cancel_single_qubit('HPowGate', 'HPowGate', 10, 10000000)"),
                (1, f"CALL linked_hhcxhh_to_cx(10, 10000000);"),
                (1, f"CALL linked_cx_to_hhcxhh(10, 10000000);"),
                (1, f"CALL stopper({stop_after});")
            ]

            db_multi_threaded(thread_proc=thread_procedures)
            cursor.execute("update stop_condition set stop=False")
            extracted_circuit = extract_cirq_circuit(conn=connection,
                                                     circuit_label=f'Test {n_bits}',
                                                     remove_io_gates=False,
                                                     table='linked_circuit_qubit')
            print('----------------------------------------------')
            print('Initial:')
            print(initial_circuit)
            print('Final:')
            print(extracted_circuit)
            assert np.allclose(initial_circuit.unitary(), extracted_circuit.unitary())


if __name__ == "__main__":
    test_cancel_single_qubit()
    test_cancel_two_qubit()
    test_commute_single_control_right()
    test_commute_single_control_left()
    test_cx_to_hhcxhh_a()
    test_cx_to_hhcxhh_b()
    test_hhcxhh_to_cx_a()
    test_hhcxhh_to_cx_b()
    test_replace_two_sq_with_one()
    # test_case_1()
    # test_case_2()
    # test_case_1_repeated(n=100)
    # test_case_2_repeated(n=100)
    # check_logical_correctness_random(stop_after=15)
    # test_qualtran_adder_opt_reconstruction(stop_after=60)
    # test_BVZ_optimization(stop_after=15)
