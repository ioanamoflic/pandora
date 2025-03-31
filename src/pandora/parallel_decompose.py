import os
import sys
import time

from pyLIQTR.utils.circuit_decomposition import generator_decompose

from pandora.cirq_to_pandora_util import cirq_to_pandora_from_op_list
from pandora.connection_util import get_connection, insert_single_batch
from pandora.pyliqtr_to_pandora_util import make_fh_circuit
from pandora.qualtran_to_pandora_util import generator_get_pandora_compatible_batch_via_pyliqtr


def parallel_decompose_and_insert(affinity, N: int, proc_id: int, nprocs: int, window_size: int = 1e6):
    """
    Embarrassingly parallel version of the generator decomposition.
    This is now only working for Fermi-Hubbard circuits.
    """
    # set affinity of each process
    # if sys.platform == "linux":
    #     my_pid = os.getppid()
    #     old_aff = os.sched_getaffinity(0)
    #     os.sched_setaffinity(my_pid, affinity)
    #     print(f"My pid is {my_pid} and my old affinity was {old_aff}, my new affinity is {os.sched_getaffinity(0)}")

    # get a connection for each process
    proc_conn = get_connection()
    start_time = time.time()

    # each process will generate its own copy of the pyLIQTR circuit. This might be a bit inefficient as they
    # take some memory but there's no other obvious way to do it
    print(f"Hello, I am process {proc_id} and I am creating my own FH circuit.")
    proc_circuit = make_fh_circuit(N=N, p_algo=0.9999999904, times=0.01)
    total_bloqs = sum(1 for _ in generator_decompose(proc_circuit, max_decomposition_passes=2))

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
