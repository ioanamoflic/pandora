# from _connection import *
import subprocess
import time
import cirq2db
from _connection import create_linked_table, refresh_all_stored_procedures, insert_in_batches, extract_cirq_circuit
from maslov_files_reader import markov_file_to_tuples
import psycopg2
import os
import sys
import typing
from itertools import cycle
from multiprocessing import Process
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


def map_hack(aff, proc_call):
    if sys.platform == "linux":
        my_pid = os.getppid()
        old_aff = os.sched_getaffinity(0)
        x = (my_pid, old_aff, os.sched_getaffinity(0))
        print("My pid is {} and my old affinity was {}, my new affinity is {}".format(*x))

    connection = psycopg2.connect(
        database="postgres",
        user="postgres",
        host="localhost",
        port=5432,
        password="1234")

    if connection:
        print("Connection to the PostgreSQL established successfully.")
    else:
        print("Connection to the PostgreSQL encountered and error.")

    cursor = connection.cursor()
    connection.set_session(autocommit=True)
    print('Calling procedure...')
    cursor.execute(proc_call)


def db_multi_threaded(thread_proc: typing.List[tuple]):
    print(f"MAIN PPID {os.getppid()} PID {os.getpid()} ")

    n_threads = sum([n for (n, _) in thread_proc])
    if sys.platform == "linux":
        my_cpus = cycle(os.sched_getaffinity(0))
        cpus = [[next(my_cpus) * 2] for _ in range(n_threads)]

    process_list = []
    for (n, proc) in thread_proc:
        for _ in range(n):
            if sys.platform == "linux":
                p = Process(target=map_hack, args=(cpus.pop(), proc))
            else:
                p = Process(target=map_hack, args=(None, proc))
            process_list.append(p)

    print(process_list)
    for i in range(n_threads):
        process_list[i].start()
    for i in range(n_threads):
        process_list[i].join()


if __name__ == "__main__":
    print('...refreshing table')
    cursor.execute("update stop_condition set stop=True")
    create_linked_table(conn=connection, clean=True)
    refresh_all_stored_procedures(conn=connection)

    # print('...insert circuit')
    # url = 'https://raw.githubusercontent.com/njross/optimizer/master/QFT_and_Adders/Adder128_before'
    # db_tuples, gate_id = markov_file_to_tuples(url, gate_id=0, label='Adder128')
    # insert_in_batches(conn=connection, db_tuples=db_tuples)

    bloq = Add(QUInt(4))
    circuit = get_clifford_plus_t_cirq_circuit_for_bloq(bloq)
    assert_circuit_in_clifford_plus_t(circuit)

    db_tuples, _ = cirq2db.cirq_to_db(cirq_circuit=circuit, last_id=0, label='Q-adder', add_margins=True)
    insert_in_batches(db_tuples=db_tuples, conn=connection, batch_size=100000, reset_id=100000)

    cursor.execute("update stop_condition set stop=False")
    print('...decomposing Toffolis')
    cursor.execute("call linked_toffoli_decomp()")

    print('...running optimization')
    thread_procedures = [
        (4, f"CALL cancel_single_qubit('H', 'H', 10, 10000000)"),
        (2, f"CALL cancel_single_qubit('T', 'T**-1', 10, 10000000)"),
        (1, f"CALL cancel_single_qubit('X', 'X', 10, 10000000)"),
        (4, f"CALL cancel_two_qubit('CNOT', 'CNOT', 10, 10000000)"),
        (2, f"CALL replace_two_qubit('T', 'T', 'S', 10, 10000000)"),
        (2, f"CALL replace_two_qubit('T**-1', 'T**-1', 'S**-1', 10, 10000000)"),
        (2, f"CALL commute_single_control_left('T', 10, 10000000)"),
        (2, f"CALL commute_single_control_left('T**-1', 10, 10000000)"),
        (2, f"CALL commute_single_control_left('S', 10, 10000000)"),
        (2, f"CALL commute_single_control_left('S**-1', 10, 10000000)"),
        (2, f"CALL linked_hhcxhh_to_cx(10, 10000000);"),
        (1, f"CALL linked_cx_to_hhcxhh(10, 10000000);")
    ]
    # subprocess.Popen(["./readout_threadripper.sh"], shell=True, executable="/bin/bash")
    # db_multi_threaded(thread_proc=thread_procedures)
    # print(extract_cirq_circuit(conn=connection, circuit_label='Adder128', remove_io_gates=True))
