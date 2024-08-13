import random

import cirq
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


def test_ancillify_measure_and_reset():
    return NotImplementedError()


def test_cnotify_XX():
    return NotImplementedError()


def test_cnotify_ZZ():
    return NotImplementedError()


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


def test_simplify_erasure_error():
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
    create_linked_table(conn=connection, clean=True)
    refresh_all_stored_procedures(conn=connection)

    q1, q2 = cirq.NamedQubit('q1'), cirq.NamedQubit('q2')
    initial_circuit = cirq.Circuit([cirq.XX.on(q1, q2),
                                    cirq.Z.on(q2),
                                    cirq.XX.on(q1, q2)])
    print(initial_circuit)
    db_tuples, _ = cirq_to_db(cirq_circuit=initial_circuit,
                              last_id=0,
                              add_margins=True,
                              label='see')

    insert_in_batches(db_tuples=db_tuples, conn=connection)
    cursor.execute(f"call simplify_erasure_error('XXPowGate', '_PauliZ', 100, 1)")

    extracted_circuit = extract_cirq_circuit(conn=connection,
                                             circuit_label='see',
                                             remove_io_gates=True)
    print(extracted_circuit)
    assert len(extracted_circuit) == 1
    print('Test simplify_erasure_error passed!')


def test_simplify_two_parity_check():
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
    create_linked_table(conn=connection, clean=True)
    refresh_all_stored_procedures(conn=connection)

    q1, q2 = cirq.NamedQubit('q1'), cirq.NamedQubit('q2')
    initial_circuit = cirq.Circuit([cirq.XX.on(q1, q2),
                                    cirq.XX.on(q1, q2)])
    print(initial_circuit)
    db_tuples, _ = cirq_to_db(cirq_circuit=initial_circuit,
                              last_id=0,
                              add_margins=True,
                              label='stpc')

    insert_in_batches(db_tuples=db_tuples, conn=connection)
    cursor.execute(f"call simplify_two_parity_check('XXPowGate', 'XXPowGate', 100, 1)")

    extracted_circuit = extract_cirq_circuit(conn=connection,
                                             circuit_label='stpc',
                                             remove_io_gates=True)
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
    test_simplify_two_parity_check()
    test_simplify_erasure_error()
