import sys

import qiskit

from pandora.connection_util import *
from pandora.qiskit_to_pandora_util import convert_qiskit_to_pandora

from benchmark_tket import generate_random_CX_circuit


def test_cx_to_hhcxhh_bernoulli(connection,
                                initial_circuit: qiskit.QuantumCircuit,
                                repetitions: int,
                                bernoulli_percentage=0.1):
    cursor = connection.cursor()

    drop_and_replace_tables(connection=connection,
                            clean=True)
    refresh_all_stored_procedures(connection=connection)

    db_tuples, _ = convert_qiskit_to_pandora(qiskit_circuit=initial_circuit,
                                             add_margins=True,
                                             label='q')

    insert_in_batches(pandora_gates=db_tuples,
                      connection=connection,
                      table_name='linked_circuit',
                      reset_id=False)

    reset_database_id(connection=connection,
                      table_name='linked_circuit',
                      large_buffer_value=10000000)

    print('I started optimizing...')

    st_time = time.time()
    cursor.execute(f"call linked_cx_to_hhcxhh_bernoulli({bernoulli_percentage}, {repetitions})")

    return time.time() - st_time


def test_cx_to_hhcxhh_visit_all(connection,
                                initial_circuit: qiskit.QuantumCircuit,
                                repetitions: int,
                                nprocs: int = 1,
                                bernoulli_percentage=10):
    drop_and_replace_tables(connection=connection, clean=True)
    refresh_all_stored_procedures(connection=connection)
    db_tuples, _ = convert_qiskit_to_pandora(qiskit_circuit=initial_circuit,
                                             add_margins=True,
                                             label='q')

    print("Inserting...")
    insert_in_batches(pandora_gates=db_tuples,
                      connection=connection,
                      table_name='linked_circuit',
                      reset_id=False)

    print("Resetting...")
    reset_database_id(connection=connection,
                      table_name='linked_circuit',
                      large_buffer_value=10000000)

    print("Multithreading...", nprocs)
    thread_procedures = [
        (nprocs - 1, f"call linked_cx_to_hhcxhh_seq({bernoulli_percentage}, {repetitions // nprocs})"),
        (1,
         f"call linked_cx_to_hhcxhh_seq({bernoulli_percentage}, {repetitions - (nprocs - 1) * (repetitions // nprocs)})"),
    ]

    start_pandora = time.time()
    db_multi_threaded(thread_proc=thread_procedures, config_file_path=sys.argv[1])

    return time.time() - start_pandora


def test_cx_to_hhcxhh(connection,
                      initial_circuit: qiskit.QuantumCircuit,
                      nprocs,
                      sys_percentage,
                      nr_passes=1):

    drop_and_replace_tables(connection=connection,
                            clean=True)
    refresh_all_stored_procedures(connection=connection)

    db_tuples, _ = convert_qiskit_to_pandora(qiskit_circuit=initial_circuit,
                                             add_margins=True,
                                             label='q')

    insert_in_batches(pandora_gates=db_tuples,
                      connection=connection,
                      table_name='linked_circuit',
                      reset_id=False)

    reset_database_id(connection=connection,
                      table_name='linked_circuit',
                      large_buffer_value=10000000)



    print('I started rewriting...')
    st_time = time.time()

    if nprocs == 1:
        cursor = connection.cursor()
        cursor.execute(f"call linked_cx_to_hhcxhh_seq({sys_percentage}, {nr_passes})")
    else:
        thread_procedures = [
            (nprocs, f"call linked_cx_to_hhcxhh_seq({sys_percentage}, {nr_passes})"),
        ]
        db_multi_threaded(thread_proc=thread_procedures, config_file_path=sys.argv[1])

    return time.time() - st_time


def test_cx_to_hhcxhh_cached_ids(connection,
                                 initial_circuit: qiskit.QuantumCircuit):
    cursor = connection.cursor()

    drop_and_replace_tables(connection=connection,
                            clean=True)
    refresh_all_stored_procedures(connection=connection)

    db_tuples, _ = convert_qiskit_to_pandora(qiskit_circuit=initial_circuit,
                                             add_margins=True,
                                             label='q')

    insert_in_batches(pandora_gates=db_tuples,
                      connection=connection,
                      table_name='linked_circuit',
                      reset_id=False)

    # get all ids of all CNOTs
    cursor.execute(f"call memorize_cx_ids()")

    reset_database_id(connection=connection,
                      table_name='linked_circuit',
                      large_buffer_value=10000000)

    st_time = time.time()

    print('I started rewriting...')
    cursor.execute(f"call linked_cx_to_hhcxhh_cached()")
    print('I finished rewriting...')

    return time.time() - st_time


if __name__ == "__main__":
    FILEPATH = sys.argv[1]
    NPROCS = int(sys.argv[2])

    conn = get_connection(config_file_path=FILEPATH)

    nr_passes = 100
    sample_percentage = 0.1

    for nq in range(10000, 100001, 10000):
        print(f'Number of qubits: {nq} for {nr_passes} passes and {sample_percentage} probability')

        _, qc = generate_random_CX_circuit(n_templates=nq, n_qubits=50)

        tot_time = test_cx_to_hhcxhh(connection=conn,
                                     initial_circuit=qc,
                                     nprocs=NPROCS,
                                     sys_percentage=sample_percentage / NPROCS,
                                     nr_passes=nr_passes)
        print('Time to rewrite:', tot_time)

        with open('pandora_template_search.csv', 'a') as f:
            writer = csv.writer(f)
            writer.writerow((nq, tot_time))

    conn.close()
