import csv
import time

import psycopg2
from benchmarking.benchmark_db import generate_random_CX_circuit
from cirq2db import *
from main import db_multi_threaded
from qualtran2db import *

connection = psycopg2.connect(
    database="postgres",
    user="postgres",
    host="localhost",
    port=5432,
    password="1234")

cursor = connection.cursor()
connection.set_session(autocommit=True)

if connection:
    print("Connection to the PostgreSQL established successfully.")
else:
    print("Connection to the PostgreSQL encountered and error.")


def concatenate(initial_circuit, cnt):
    create_linked_table(conn=connection, clean=True)
    refresh_all_stored_procedures(conn=connection)

    db_tuples, _ = cirq_to_db(cirq_circuit=initial_circuit, last_id=0, add_margins=True, label='verification')
    insert_in_batches(db_tuples=db_tuples, conn=connection, reset_id=10000000)

    thread_procedures = [
        (1, f"call linked_cx_to_hhcxhh_bernoulli(50, {cnt})"),
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


def verify_C_Ct_eq_I(concatenated_circuit, cnt):
    create_linked_table(conn=connection, clean=True)
    refresh_all_stored_procedures(conn=connection)

    db_tuples, _ = cirq_to_db(cirq_circuit=concatenated_circuit, last_id=0, add_margins=True, label='verification')
    insert_in_batches(db_tuples=db_tuples, conn=connection, reset_id=10000000)

    thread_procedures = [
        (1, f"call linked_hhcxhh_to_cx_bernoulli(50, {cnt})"),
        (1, f"call cancel_two_qubit_bernoulli('CXPowGate', 'CXPowGate', 50, {cnt})"),
    ]

    db_multi_threaded(thread_proc=thread_procedures)
    extracted_circuit = extract_cirq_circuit(conn=connection,
                                             circuit_label=f'verification',
                                             remove_io_gates=True)

    assert len(extracted_circuit) == 0


if __name__ == "__main__":
    times = []
    for cx_count in range(2, 100):
        initial_circuit = generate_random_CX_circuit(n_templates=cx_count, n_qubits=cx_count)
        concatenated = concatenate(initial_circuit=initial_circuit, cnt=cx_count)
        start_time = time.time()
        verify_C_Ct_eq_I(concatenated_circuit=concatenated, cnt=cx_count)
        times.append((cx_count, time.time() - start_time))
        print(cx_count)

    with open('results/verification.csv', 'w') as f:
        writer = csv.writer(f)
        for row in times:
            writer.writerow(row)

