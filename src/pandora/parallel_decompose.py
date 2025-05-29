import time

from pyLIQTR.utils.circuit_decomposition import circuit_decompose_multi

from pandora.cirq_to_pandora_util import cirq_to_pandora_from_op_list
from pandora.connection_util import get_connection, insert_single_batch
from pandora.qualtran_to_pandora_util import get_RSA, generator_get_RSA_compatible_batch


def parallel_decompose_multi_and_insert(proc_id: int,
                                        nprocs: int,
                                        table_name: str,
                                        N: int = None,
                                        config_file_path: str = None,
                                        window_size: int = 1000,
                                        conn_lifetime: int = 120):
    """
    Embarrassingly parallel version of the generator decomposition.
    """
    start_time = time.time()

    # each process will generate its own copy of the pyLIQTR circuit
    print(f"Hello, I am process {proc_id} and I am creating my own circuit.")

    proc_circuit = get_RSA()
    circuit_decomposed_shallow = circuit_decompose_multi(proc_circuit, N=2)

    high_level_op_list = [op for mom in circuit_decomposed_shallow for op in mom]

    del circuit_decomposed_shallow

    op_count = len(high_level_op_list)

    proc_start = (op_count * proc_id) // nprocs
    proc_end = (op_count * (proc_id + 1)) // nprocs

    print(f"Hello, I am process {proc_id}, I have range [{proc_start}, {proc_end}) out of [0, {op_count}]")

    per_process_gate_list = []
    for i, high_level_op in enumerate(high_level_op_list):
        if proc_start <= i < proc_end:
            process_batches = generator_get_RSA_compatible_batch(circuit=high_level_op,
                                                                 window_size=window_size)
            for batch, _ in process_batches:
                pandora_gates = cirq_to_pandora_from_op_list(op_list=batch,
                                                             label=i)
                per_process_gate_list.extend(pandora_gates)

                if len(per_process_gate_list) >= window_size:
                    proc_conn = get_connection(autocommit=False, config_file_path=config_file_path)
                    insert_single_batch(connection=proc_conn,
                                        batch=per_process_gate_list,
                                        table_name=table_name,
                                        close_conn=True)
                    per_process_gate_list.clear()

    # insert last batch
    if len(per_process_gate_list) > 0:
        proc_conn = get_connection(autocommit=False, config_file_path=config_file_path)
        insert_single_batch(connection=proc_conn,
                            batch=per_process_gate_list,
                            table_name=table_name,
                            close_conn=True)

    print(f"Hello, I am process {proc_id} finished in {time.time() - start_time}")
