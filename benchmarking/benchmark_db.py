import random
import time
import csv
from cirq2db import *
from qualtran2db import *


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


def test_cx_to_hhcxhh(connection, initial_circuit, n_CX):
    cursor = connection.cursor()
    create_linked_table(connection=connection, clean=True)
    refresh_all_stored_procedures(connection=connection)

    db_tuples, _ = cirq_to_db(cirq_circuit=initial_circuit, last_id=0, add_margins=True, label='test_random')
    insert_in_batches(db_tuples=db_tuples, connection=connection)
    cursor.execute("ALTER SEQUENCE linked_circuit_id_seq RESTART WITH 10000000")

    st_time = time.time()
    print('I started optimizing...')
    cursor.execute(f"call linked_cx_to_hhcxhh_visit({n_CX // 10}, {n_CX})")
    print('I finished optimizing...')

    return time.time() - st_time


if __name__ == "__main__":
    connection = get_connection()
    n_CX = [1000, 10000, 100000, 1000000, 10000000]

    times = []
    for cx_count in n_CX:
        print('cx count:', cx_count)
        input_circ = generate_random_CX_circuit(n_templates=cx_count, n_qubits=50)
        start_time = time.time()
        tot_time = test_cx_to_hhcxhh(connection=connection, initial_circuit=input_circ, n_CX=cx_count)
        print('time to optimize:', tot_time)
        times.append(tot_time)

    rows = zip(n_CX, times)
    with open('results/db_random.csv', 'w') as f:
        writer = csv.writer(f)
        for row in rows:
            writer.writerow(row)
    connection.close()

