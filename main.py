# from _connection import *
import subprocess
import time
import cirq2db
from _connection import create_linked_table, refresh_all_stored_procedures, insert_in_batches, extract_cirq_circuit
from maslov_files_reader import *
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


def map_hack(aff, proc_call, verbose=False):
    if sys.platform == "linux":
        my_pid = os.getppid()
        old_aff = os.sched_getaffinity(0)
        x = (my_pid, old_aff, os.sched_getaffinity(0))
        # print("My pid is {} and my old affinity was {}, my new affinity is {}".format(*x))

    connection = psycopg2.connect(
        database="postgres",
        user="postgres",
        host="localhost",
        port=5432,
        password="1234")

    if verbose:
        if connection:
            print("Connection to the PostgreSQL established successfully.")
        else:
            print("Connection to the PostgreSQL encountered and error.")

    cursor = connection.cursor()
    connection.set_session(autocommit=True)
    if verbose:
        print('Calling procedure...')

    cursor.execute(proc_call)


def db_multi_threaded(thread_proc: typing.List[tuple]):
    # print(f"MAIN PPID {os.getppid()} PID {os.getpid()} ")

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

    for i in range(n_threads):
        process_list[i].start()
    for i in range(n_threads):
        process_list[i].join()


if __name__ == "__main__":
    n_bits = [8, 16, 32, 64, 128, 256, 512, 1024, 2048]
    for bits in n_bits:
        print('...refreshing table')
        create_linked_table(conn=connection, clean=True)
        refresh_all_stored_procedures(conn=connection)

        db_tuples = get_maslov_adder(conn=connection, n_bits=bits)
        insert_in_batches(db_tuples=db_tuples, conn=connection, batch_size=1000000, reset_id=100000)

        print('...decomposing Toffolis')
        cursor.execute("call linked_toffoli_decomp()")

        print('...running optimization')
        stop_after = 180
        thread_procedures = [
            (1, f"CALL stopper({stop_after});"),
            (8, f"CALL cancel_single_qubit_bernoulli('HPowGate', 'HPowGate', 10, 10000000)"),
            (4, f"CALL cancel_single_qubit_bernoulli('ZPowGate**0.25', 'ZPowGate**-0.25', 10, 10000000)"),
            (4, f"CALL cancel_single_qubit_bernoulli('_PauliX', '_PauliX', 10, 10000000)"),
            (4, f"CALL cancel_two_qubit_bernoulli('CXPowGate', 'CXPowGate', 10, 10000000)"),
            (4, f"CALL replace_two_qubit_bernoulli('ZPowGate**0.25', 'ZPowGate**0.25', 'ZPowGate**0.5', 0.5, 10, "
                f"10000000)"),
            (4, f"CALL replace_two_qubit_bernoulli('ZPowGate**-0.25', 'ZPowGate**-0.25', 'ZPowGate**-0.5', 0.5, 10, "
                f"10000000)"),
            (4, f"CALL commute_single_control_left_bernoulli('ZPowGate**0.25', 10, 10000000)"),
            (4, f"CALL commute_single_control_left_bernoulli('ZPowGate**-0.25', 10, 10000000)"),
            (4, f"CALL commute_single_control_left_bernoulli('ZPowGate**0.5', 10, 10000000)"),
            (4, f"CALL commute_single_control_left_bernoulli('ZPowGate**-0.5', 10, 10000000)"),
            (4, f"CALL linked_hhcxhh_to_cx_bernoulli(10, 10000000);"),
            (1, f"CALL linked_cx_to_hhcxhh_bernoulli(10, 10000000);"),
        ]
        proc = subprocess.Popen([f'./readout_epyc.sh results_{bits}.csv'], shell=True, executable="/bin/bash")
        db_multi_threaded(thread_proc=thread_procedures)
        subprocess.Popen.kill(proc)

