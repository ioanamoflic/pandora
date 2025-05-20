import time

# import pyLIQTR
# from memory_profiler import profile

# from pyLIQTR.BlockEncodings import PauliStringLCU
# from pyLIQTR.qubitization.qubitized_gates import QubitizedRotation
#
# import monkey_patching.lazy_load as monkey_patching
#
# pyLIQTR.qubitization.qubitized_gates.QubitizedRotation = \
#     lambda *args, **kwargs: monkey_patching.LazyProxy(QubitizedRotation, None, *args, **kwargs)
# pyLIQTR.BlockEncodings.PauliStringLCU.PauliStringLCU = \
#     lambda *args, **kwargs: monkey_patching.LazyProxy(PauliStringLCU, None, *args, **kwargs)

from pandora.pyLIQTR.pyliqtr_circuit_decomposition import generator_decompose, circuit_decompose_multi
from pandora.cirq_to_pandora_util import cirq_to_pandora_from_op_list
from pandora.connection_util import get_connection, insert_single_batch
# from pandora.pyliqtr_to_pandora_util import make_fh_circuit
from pandora.qualtran_to_pandora_util import generator_get_pandora_compatible_batch_via_pyliqtr, get_RSA


def parallel_decompose_and_insert(N: int,
                                  proc_id: int,
                                  nprocs: int,
                                  config_file_path: str = None,
                                  window_size: int = 1000,
                                  conn_lifetime: int = 120):
    """
     Embarrassingly parallel version of the generator decomposition.
     This is now only working for Fermi-Hubbard circuits.
     """
    # get a connection for each process
    proc_conn = get_connection(config_file_path)
    start_time = time.time()

    # each process will generate its own copy of the pyLIQTR circuit
    print(f"Hello, I am process {proc_id} and I am creating my own FH circuit.")

    proc_circuit = make_fh_circuit(N=N, p_algo=0.9999999904, times=0.01)

    total_bloqs = sum(1 for _ in generator_decompose(proc_circuit, max_decomposition_passes=2))
    print(total_bloqs)

    proc_start = (total_bloqs * proc_id) // nprocs
    proc_end = (total_bloqs * (proc_id + 1)) // nprocs

    print(f"Hello, I am process {proc_id}, I have range [{proc_start}, {proc_end}) out of [0, {total_bloqs}]")

    per_process_gate_list = []
    # go down two levels to reach sequences of (QubitizedRotation, _PauliZ, PauliStringLCU)
    for bloq_id, dop in enumerate(generator_decompose(proc_circuit,
                                                      max_decomposition_passes=2)):
        if proc_start <= bloq_id < proc_end:
            process_batches = generator_get_pandora_compatible_batch_via_pyliqtr(circuit=dop,
                                                                                 window_size=window_size)
            for batch, _ in process_batches:
                pandora_gates = cirq_to_pandora_from_op_list(op_list=batch,
                                                             label=bloq_id)
                per_process_gate_list.extend(pandora_gates)

            if len(per_process_gate_list) >= window_size:
                insert_single_batch(connection=proc_conn,
                                    batch=per_process_gate_list,
                                    table_name='batched_circuit')
                per_process_gate_list = []

    # insert last batch
    insert_single_batch(connection=proc_conn,
                        batch=per_process_gate_list,
                        table_name='batched_circuit')

    print(f"Hello, I am process {proc_id} finished in {time.time() - start_time}")


# @profile
def parallel_decompose_multi_and_insert(N: int,
                                        proc_id: int,
                                        nprocs: int,
                                        table_name: str,
                                        config_file_path: str = None,
                                        window_size: int = 1000,
                                        conn_lifetime: int = 120):
    """
    Embarrassingly parallel version of the generator decomposition.
    This is now only working for Fermi-Hubbard circuits.
    """
    start_time = time.time()

    # each process will generate its own copy of the pyLIQTR circuit
    print(f"Hello, I am process {proc_id} and I am creating my own FH circuit.")

    # proc_circuit = make_fh_circuit(N=N, p_algo=0.9999999904, times=0.01)
    proc_circuit = get_RSA()
    circuit_decomposed_shallow = circuit_decompose_multi(proc_circuit, N=2)

    high_level_op_list = [op for mom in circuit_decomposed_shallow for op in mom]
    op_count = len(high_level_op_list)

    proc_start = (op_count * proc_id) // nprocs
    proc_end = (op_count * (proc_id + 1)) // nprocs

    print(f"Hello, I am process {proc_id}, I have range [{proc_start}, {proc_end}) out of [0, {op_count}]")

    per_process_gate_list = []
    for i, high_level_op in enumerate(high_level_op_list):
        if proc_start <= i < proc_end:
            process_batches = generator_get_pandora_compatible_batch_via_pyliqtr(circuit=high_level_op,
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
                    per_process_gate_list = []

    # insert last batch
    if len(per_process_gate_list) > 0:
        proc_conn = get_connection(autocommit=False, config_file_path=config_file_path)
        insert_single_batch(connection=proc_conn,
                            batch=per_process_gate_list,
                            table_name=table_name,
                            close_conn=True)

    print(f"Hello, I am process {proc_id} finished in {time.time() - start_time}")
    # proc_conn.close()
