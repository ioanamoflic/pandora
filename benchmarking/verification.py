import copy

import psycopg2
from _connection import *
from cirq2db import cirq_to_db
from benchmarking.benchmark_db import generate_random_CX_circuit
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


def concatenate(initial_circuit):
    create_linked_table(conn=connection, clean=True)
    refresh_all_stored_procedures(conn=connection)

    db_tuples, _ = cirq_to_db(cirq_circuit=initial_circuit, last_id=0, add_margins=True, label='verification')
    insert_in_batches(db_tuples=db_tuples, conn=connection)
    cursor.execute("ALTER SEQUENCE linked_circuit_id_seq RESTART WITH 10000000")

    thread_procedures = [
        (1, f"call linked_cx_to_hhcxhh(100, 3)"),
        (1, f"CALL stopper({5});")
    ]

    db_multi_threaded(thread_proc=thread_procedures)
    extracted_circuit = extract_cirq_circuit(conn=connection,
                                             circuit_label=f'verification',
                                             remove_io_gates=True)

    extracted_circuit_reversed = extracted_circuit[::-1]
    qubit_map = dict(
        zip(
            sorted(initial_circuit.all_qubits()),
            sorted(extracted_circuit_reversed.all_qubits())
        )
    )
    initial_circuit = initial_circuit.transform_qubits(qubit_map=qubit_map)

    concatenated_circuit = cirq.Circuit(initial_circuit.moments + extracted_circuit_reversed.moments)
    return concatenated_circuit


def verify_C_Ct_eq_I(concatenated_circuit):
    create_linked_table(conn=connection, clean=True)
    refresh_all_stored_procedures(conn=connection)

    db_tuples, _ = cirq_to_db(cirq_circuit=concatenated_circuit, last_id=0, add_margins=True, label='verification')
    insert_in_batches(db_tuples=db_tuples, conn=connection)
    cursor.execute("ALTER SEQUENCE linked_circuit_id_seq RESTART WITH 10000000")

    thread_procedures = [
        (1, f"call linked_hhcxhh_to_cx(100, 3)"),
        (1, f"call cancel_two_qubit_bernoulli('CXPowGate', 'CXPowGate', 100, 3)"),
        (1, f"CALL stopper({5});")
    ]

    db_multi_threaded(thread_proc=thread_procedures)
    print("finished with threads")
    extracted_circuit = extract_cirq_circuit(conn=connection,
                                             circuit_label=f'verification',
                                             remove_io_gates=True)

    print(extracted_circuit)
    assert len(extracted_circuit) == 0


if __name__ == "__main__":
    cx_count = 3
    # input_circ = generate_random_CX_circuit(n_templates=cx_count, n_qubits=3)

    q1, q2, q3 = cirq.LineQubit(0), cirq.LineQubit(1), cirq.LineQubit(2)
    initial_circuit = cirq.Circuit([cirq.CX.on(q1, q2), cirq.CX.on(q1, q3), cirq.CX.on(q1, q2)])

    concatenated = concatenate(initial_circuit=initial_circuit)
    verify_C_Ct_eq_I(concatenated_circuit=concatenated)
