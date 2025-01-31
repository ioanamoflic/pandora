from pandora.connection_util import *
from pandora.cirq_to_pandora_util import *


def test_ancillify_measure_and_reset():
    return NotImplementedError()


def test_cnotify_XX(connection):
    """
      Testing circuit:

      q1: ──────XX─────
                │
      q2: ──────XX─────

      Should reduce to

    0: ───In────X───Out─────────
                │
    1: ───In────┼───X─────Out───
                │   │
    2: ───|+>───@───@─────Mx────

      """
    cursor = connection.cursor()
    drop_and_replace_tables(connection=connection, clean=True)
    refresh_all_stored_procedures(connection=connection)

    q1, q2 = cirq.NamedQubit('q1'), cirq.NamedQubit('q2')
    initial_circuit = cirq.Circuit([cirq.XX.on(q1, q2)])
    print(initial_circuit)
    db_tuples, _ = cirq_to_pandora(cirq_circuit=initial_circuit,
                                   last_id=0,
                                   add_margins=True,
                                   label='t')

    insert_in_batches(pandora_gates_it=db_tuples, connection=connection, reset_id=True, table_name='linked_circuit')
    cursor.execute(f"call cnotify_XX(100, 1)")

    extracted_circuit = extract_cirq_circuit(connection=connection,
                                             circuit_label='t',
                                             remove_io_gates=False,
                                             is_test=False)
    print(extracted_circuit)
    assert len(extracted_circuit) == 4
    print('Test cnotify_XX passed!')


def test_cnotify_ZZ(connection):
    """
      Testing circuit:

      q1: ──────ZZ─────
                │
      q2: ──────ZZ─────

      Should reduce to

    0: ───In────@───Out─────────
                │
    1: ───In────┼───@─────Out───
                │   │
    2: ───|0>───X───X─────Mz────

      """
    cursor = connection.cursor()
    drop_and_replace_tables(connection=connection, clean=True)
    refresh_all_stored_procedures(connection=connection)

    q1, q2 = cirq.NamedQubit('q1'), cirq.NamedQubit('q2')
    initial_circuit = cirq.Circuit([cirq.ZZ.on(q1, q2)])
    print(initial_circuit)
    db_tuples, _ = cirq_to_pandora(cirq_circuit=initial_circuit,
                                   last_id=0,
                                   add_margins=True,
                                   label='t')

    insert_in_batches(pandora_gates_it=db_tuples, connection=connection, reset_id=True, table_name='linked_table')
    cursor.execute(f"call cnotify_ZZ(100, 1)")

    extracted_circuit = extract_cirq_circuit(connection=connection,
                                             circuit_label='t',
                                             remove_io_gates=False,
                                             is_test=False)
    print(extracted_circuit)
    assert len(extracted_circuit) == 4
    print('Test cnotify_ZZ passed!')


def test_cxor0xora():
    return NotImplementedError()


def test_decompose_n22_weight_stabilizer():
    return NotImplementedError()


def test_lscx_down_a():
    return NotImplementedError()


def test_lscx_down_b():
    return NotImplementedError()


def test_lscx_up_a():
    return NotImplementedError()


def test_lscx_up_b():
    return NotImplementedError()


def test_simplify_erasure_error(connection):
    """
      Testing circuit:

      q1: ──────XX────── XX───
                │        │
      q2: ──────XX───Z───XX───

      Should reduce to

      q1: ──────XX──────
                │
      q2: ──────XX──────

      """
    cursor = connection.cursor()
    drop_and_replace_tables(connection=connection, clean=True)
    refresh_all_stored_procedures(connection=connection)

    q1, q2 = cirq.NamedQubit('q1'), cirq.NamedQubit('q2')
    initial_circuit = cirq.Circuit([cirq.XX.on(q1, q2),
                                    cirq.Z.on(q2),
                                    cirq.XX.on(q1, q2)])
    print(initial_circuit)
    db_tuples, _ = cirq_to_pandora(cirq_circuit=initial_circuit,
                                   last_id=0,
                                   add_margins=True,
                                   label='t')

    insert_in_batches(pandora_gates_it=db_tuples, connection=connection, table_name='linked_circuit')
    cursor.execute(f"call simplify_erasure_error('XXPowGate', '_PauliZ', 100, 1)")

    extracted_circuit = extract_cirq_circuit(connection=connection,
                                             circuit_label='t',
                                             remove_io_gates=True,
                                             is_test=False)
    print(extracted_circuit)
    assert len(extracted_circuit) == 1
    print('Test simplify_erasure_error passed!')


def test_simplify_two_parity_check(connection):
    """
    Testing circuit:

    q1: ──────XX──────XX───
              │       │
    q2: ──────XX──────XX───

    Should reduce to

    q1: ──────XX──────
              │
    q2: ──────XX──────

    """

    drop_and_replace_tables(connection=connection, clean=True)
    refresh_all_stored_procedures(connection=connection)

    q1, q2 = cirq.NamedQubit('q1'), cirq.NamedQubit('q2')
    initial_circuit = cirq.Circuit([cirq.XX.on(q1, q2),
                                    cirq.XX.on(q1, q2)])
    print(initial_circuit)
    db_tuples, _ = cirq_to_pandora(cirq_circuit=initial_circuit,
                                   last_id=0,
                                   add_margins=True,
                                   label='t')

    insert_in_batches(pandora_gates_it=db_tuples, connection=connection, reset_id=True, table_name='linked_circuit')
    cursor = connection.cursor()
    cursor.execute(f"call simplify_two_parity_check('XXPowGate', 'XXPowGate', 100, 1)")

    extracted_circuit = extract_cirq_circuit(connection=connection,
                                             circuit_label='t',
                                             remove_io_gates=True,
                                             is_test=False)
    print(extracted_circuit)
    assert len(extracted_circuit) == 1
    print('Test simplify_two_parity_check passed!')


def test_useless_cx_ancilla_zero_X():
    return NotImplementedError()


def test_useless_cx_ancilla_plus_Z():
    return NotImplementedError()


def test_useless_cx_ctrl_zero():
    return NotImplementedError()


def test_useless_cx_plusplus():
    return NotImplementedError()


def test_useless_cx_plus_Z():
    return NotImplementedError()


def test_useless_cx_zero_X():
    return NotImplementedError()


if __name__ == "__main__":
    conn = get_connection()
    test_simplify_two_parity_check(conn)
    test_simplify_erasure_error(conn)
    test_cnotify_XX(conn)
    test_cnotify_ZZ(conn)
    conn.close()
