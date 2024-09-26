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

TIMEOUT_VAL = 10000000


def concatenate(init_circ, cnt, bernoulli_percentage=10):
    create_linked_table(conn=connection, clean=True)
    refresh_all_stored_procedures(conn=connection)

    db_tuples, _ = cirq_to_db(cirq_circuit=init_circ, last_id=0, add_margins=True, label='verification')
    insert_in_batches(db_tuples=db_tuples, conn=connection, reset_id=10000000)

    thread_procedures = [
        (1, f"call linked_cx_to_hhcxhh_bernoulli({bernoulli_percentage}, {cnt})"),
    ]

    db_multi_threaded(thread_proc=thread_procedures)
    extracted_circuit = extract_cirq_circuit(conn=connection,
                                             circuit_label=f'verification',
                                             remove_io_gates=True)

    extracted_circuit_reversed = extracted_circuit[::-1]
    qubit_map = dict(
        zip(
            sorted(init_circ.all_qubits()),
            sorted(extracted_circuit_reversed.all_qubits())
        )
    )
    init_circ = init_circ.transform_qubits(qubit_map=qubit_map)
    concatenated_circuit = cirq.Circuit(init_circ.moments + extracted_circuit_reversed.moments)

    return concatenated_circuit


def verify_C_Ct_eq_I(concatenated_circuit, cnt, bernoulli_percentage, single_threaded=False, stop_after=10):
    create_linked_table(conn=connection, clean=True)
    refresh_all_stored_procedures(conn=connection)

    db_tuples, _ = cirq_to_db(cirq_circuit=concatenated_circuit, last_id=0, add_margins=True, label='verification')
    insert_in_batches(db_tuples=db_tuples, conn=connection, reset_id=10000000)

    if single_threaded is True:
        thread_procedures = [
            (1, f"call stopper({stop_after});"),
            (1, f"call linked_hhcxhh_to_cx_bernoulli({bernoulli_percentage}, {cnt})"),
            (1, f"call cancel_two_qubit_bernoulli('CXPowGate', 'CXPowGate', {bernoulli_percentage}, {cnt})"),
        ]
    else:
        thread_procedures = [(1, f"call stopper({stop_after});")]
        for _ in range(cnt):
            thread_procedures.append((1, f"call linked_hhcxhh_to_cx_bernoulli({bernoulli_percentage}, 1)"))
            thread_procedures.append((1, f"call cancel_two_qubit_bernoulli('CXPowGate', 'CXPowGate', "
                                         f"{bernoulli_percentage}, 1)"))

    start_time = time.time()
    db_multi_threaded(thread_proc=thread_procedures)
    total_time = time.time() - start_time
    extracted_circuit = extract_cirq_circuit(conn=connection,
                                             circuit_label=f'verification',
                                             remove_io_gates=True)

    if len(extracted_circuit) != 0:
        return TIMEOUT_VAL
    return total_time


if __name__ == "__main__":
    single_thr = True
    bp = 25

    for stop in [1, 2, 5, 10, 15, 20, 25, 30, 35]:
        for i in range(3):
            times = []
            for cx_count in range(2, 50):
                initial_circuit = generate_random_CX_circuit(n_templates=cx_count,
                                                             n_qubits=cx_count)
                concatenated = concatenate(init_circ=initial_circuit,
                                           cnt=cx_count,
                                           bernoulli_percentage=bp)
                time_val = verify_C_Ct_eq_I(concatenated_circuit=concatenated,
                                            cnt=cx_count,
                                            single_threaded=single_thr,
                                            bernoulli_percentage=bp,
                                            stop_after=stop)

                times.append((cx_count, time_val))
                print(cx_count)

            with open(f'results/verification_single_{stop}_{i}.csv', 'w') as f:
                writer = csv.writer(f)
                for row in times:
                    writer.writerow(row)
