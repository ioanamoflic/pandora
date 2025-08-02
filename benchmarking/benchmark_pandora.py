from multiprocessing import Pool

from pandora.connection_util import *
from pandora.connection_pool_util import map_procedure_call, init_worker
from pandora.qiskit_to_pandora_util import convert_qiskit_to_pandora

from benchmark_tket import generate_random_HHCXHH_circuit_occasionally_flipped


def reset_pandora(connection, quantum_circuit):
    drop_and_replace_tables(connection=connection, clean=True)
    refresh_all_stored_procedures(connection=connection)

    db_tuples, _ = convert_qiskit_to_pandora(qiskit_circuit=quantum_circuit,
                                             add_margins=True,
                                             label='q')

    insert_in_batches(pandora_gates=db_tuples,
                      connection=connection,
                      table_name='linked_circuit',
                      reset_id=False)

    reset_database_id(connection=connection,
                      table_name='linked_circuit',
                      large_buffer_value=10000000)


def create_pool(n_workers, config_file_path):
    return Pool(processes=n_workers, initializer=init_worker, initargs=(config_file_path,))


def close_pool(proc_pool):
    proc_pool.close()
    proc_pool.join()


if __name__ == "__main__":
    FILEPATH = sys.argv[1]
    NPROCS = int(sys.argv[2])

    conn = get_connection(config_file_path=FILEPATH)

    nr_passes = 1
    sample_percentage = 10

    pool = None
    if NPROCS > 0:
        pool = create_pool(n_workers=NPROCS, config_file_path=FILEPATH)
        # Warmup
        pool.map(print, ".")

    for nq in range(10000, 100001, 10000):
        rewrites, qc = generate_random_HHCXHH_circuit_occasionally_flipped(n_templates=nq,
                                                                           n_qubits=50,
                                                                           proba=sample_percentage / 100)

        print(f'Number of qubits: {nq} for {nr_passes} passes and {sample_percentage} proba with {rewrites} rewrites')

        proc_calls = []
        for proc_id in range(NPROCS):
            proc_calls.append(
                f"call linked_hhcxhh_to_cx_parallel({proc_id}, {NPROCS}, {rewrites}, {nr_passes}, null)")

        reset_pandora(connection=conn, quantum_circuit=qc)

        print("Rewrite...", end=None)
        start_time = time.time()
        if NPROCS > 0:
            pool.map(map_procedure_call, proc_calls)
        else:
            cursor = conn.cursor()
            cursor.execute(f"call linked_hhcxhh_to_cx_seq({sample_percentage}, {nr_passes})")
            cursor.close()

        tot_time = time.time() - start_time
        print('Time to rewrite:', tot_time)

        with open('pandora_template_search_random_flip.csv', 'a') as f:
            writer = csv.writer(f)
            writer.writerow((nq, tot_time, sample_percentage, NPROCS))

    if NPROCS > 0:
        close_pool(pool)
    conn.close()
