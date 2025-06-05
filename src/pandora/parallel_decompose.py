import time

from pyLIQTR.utils.circuit_decomposition import circuit_decompose_multi

from pandora.cirq_to_pandora_util import cirq_to_pandora_from_op_list
from pandora.connection_util import get_connection, insert_single_batch
from pandora.qualtran_to_pandora_util import get_RSA, generator_get_RSA_compatible_batch


def parallel_decompose_multi_and_insert(proc_id: int,
                                        nprocs: int,
                                        container_id: int,
                                        n_containers: int,
                                        table_name: str,
                                        config_file_path: str = None,
                                        window_size: int = 1000,
                                        N: int = None):
    """
    Embarrassingly parallel version of the generator decomposition.
    """
    start_time = time.time()

    # each process will generate its own copy of the pyLIQTR/Qualtran circuit
    print(f"Hello, I am process {proc_id} and I am creating my own circuit.")

    proc_circuit = get_RSA(n=N)
    circuit_decomposed_shallow = circuit_decompose_multi(proc_circuit, N=2)

    high_level_op_list = [op
                          for mom in circuit_decomposed_shallow
                          for op in mom
                          ]
    op_count = len(high_level_op_list)

    for op in high_level_op_list:
        if str(op.gate) == 'bloq.CtrlScaleModAdd':
            high_level_op_list = [op]
            op_count = 1
            break

    del circuit_decomposed_shallow

    print(len(high_level_op_list))

    container_start = (op_count * container_id) // n_containers
    container_end = (op_count * (container_id + 1)) // n_containers

    container_op_list = high_level_op_list[container_start:container_end]
    container_op_count = len(container_op_list)

    del high_level_op_list

    proc_start = (container_op_count * proc_id) // nprocs
    proc_end = (container_op_count * (proc_id + 1)) // nprocs

    print(f"Hello, I am process {proc_id} of container {container_id}, "
          f"I have range [{container_start + proc_start}, {container_start + proc_end}) "
          f"out of container range [{container_start}, {container_end}) "
          f"out of total_range [0, {op_count})")

    per_process_gate_list = []
    for i, high_level_op in enumerate(container_op_list):
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