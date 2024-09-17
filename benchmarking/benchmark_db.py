import random
import time
import cirq
import psycopg2
import csv
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


def generate_random_CX_circuit(n_templates, n_qubits=50):
    qubits = [cirq.LineQubit(i) for i in range(n_qubits)]
    c = cirq.Circuit()
    for _ in range(n_templates):
        q1, q2 = random.choices(qubits, k=2)
        while q1 == q2:
            q1, q2 = random.choices(qubits, k=2)
        c.append(cirq.CNOT.on(q1, q2))

    return c


def gate_count(circuit):
    cnt = 0
    for mom in circuit:
        cnt += len(mom)
    return cnt


def test_cx_to_hhcxhh(initial_circuit, n_CX):
    create_linked_table(conn=connection, clean=True)
    refresh_all_stored_procedures(conn=connection)

    db_tuples, _ = cirq_to_db(cirq_circuit=initial_circuit, last_id=0, add_margins=True, label='test_random')
    insert_in_batches(db_tuples=db_tuples, conn=connection)
    cursor.execute("ALTER SEQUENCE linked_circuit_id_seq RESTART WITH 10000000")

    start_time = time.time()
    print('I started optimizing...')
    cursor.execute(f"call linked_cx_to_hhcxhh_visit({n_CX // 10}, {n_CX})")
    tot_time = time.time() - start_time
    print('I finished optimizing...')

    # extracted_circuit = extract_cirq_circuit(conn=connection, circuit_label='test_random', remove_io_gates=True)
    # gc = gate_count(extracted_circuit)
    # assert gc == 5 * n_CX

    return tot_time


if __name__ == "__main__":
    n_CX = [1000, 10000, 100000, 1000000, 10000000]

    times = []
    for cx_count in n_CX:
        print('cx count:', cx_count)
        input_circ = generate_random_CX_circuit(n_templates=cx_count, n_qubits=50)
        start_time = time.time()
        tot_time = test_cx_to_hhcxhh(input_circ, n_CX=cx_count)
        print('time to optimize:', tot_time)
        times.append(tot_time)

    rows = zip(n_CX, times)
    with open('results/db_random.csv', 'w') as f:
        writer = csv.writer(f)
        for row in rows:
            writer.writerow(row)
