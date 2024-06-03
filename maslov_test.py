from main import db_multi_threaded
from maslov_files_reader import *
import psycopg2
import subprocess

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

if __name__ == "__main__":
    stop_after = 60
    for n_bit in range(3, 11):
        adder_size = 2 ** n_bit
        stop_after = stop_after * 2

        cursor.execute("update stop_condition set stop=True")
        create_linked_table(conn=connection, clean=True)
        refresh_all_stored_procedures(conn=connection)

        url = f'https://raw.githubusercontent.com/njross/optimizer/master/QFT_and_Adders/Adder{adder_size}_before'
        db_tuples, gate_id = markov_file_to_tuples(url, gate_id=0, label=f'Adder{adder_size}')
        insert_in_batches(conn=connection, db_tuples=db_tuples)

        cursor.execute("ALTER SEQUENCE linked_circuit_id_seq RESTART WITH 1000000")
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
            (1, f"CALL linked_cx_to_hhcxhh(10, 10000000);"),
            (1, f"CALL stopper({stop_after});")
        ]
        subprocess.Popen(["./readout_threadripper.sh"], shell=True, executable="/bin/bash")
        cursor.execute("update stop_condition set stop=False")
        db_multi_threaded(thread_proc=thread_procedures)
