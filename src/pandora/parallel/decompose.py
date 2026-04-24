import asyncio

from pandora.db.core import PandoraDB
from pandora.db.repository import GateRepository
from pandora.parallel.job import ProcJob
from pandora.translation.circuit_to_dag import PandoraWindowedBuilder
from pyLIQTR.utils.circuit_decomposition import circuit_decompose_multi

from pandora.util.qualtran_util import (
    get_RSA,
    get_RSA_batch,
    get_batch
)


def worker_entry(
        job: ProcJob,
        dsn: str,
        window_size: int,
) -> None:
    asyncio.run(
        _worker_main(
            job=job,
            dsn=dsn,
            window_size=window_size
        )
    )


def get_circuit(job: ProcJob):
    match job.kind:
        case "rsa":
            return get_RSA(n=job.n_bits), get_RSA_batch
        case "fermi-hubbard":
            try:
                from pandora.util.pyliqtr_util import make_fh_circuit
            except ImportError as e:
                raise ImportError(
                    "The 'fermi-hubbard' circuit requires pyLIQTR to be installed."
                ) from e
            return make_fh_circuit(N=job.N,
                                   times=job.times,
                                   p_algo=job.p_algo), get_batch
        case _:
            raise NotImplementedError


def get_my_position(count: int, my_pu_id: int, total_pu: int):
    return ((count * my_pu_id) // total_pu,
            (count * (my_pu_id + 1)) // total_pu)


async def _worker_main(
        job: ProcJob,
        dsn: str,
        window_size: int,
) -> None:
    proc_circuit, generator_func = get_circuit(job)

    circuit_decomposed_shallow = circuit_decompose_multi(proc_circuit, N=2)

    high_level_op_list = [op for mom in circuit_decomposed_shallow for op in mom]

    node_start, node_end = get_my_position(len(high_level_op_list),
                                           job.my_node_id,
                                           job.n_nodes)

    container_op_list = high_level_op_list[node_start:node_end]

    proc_start, proc_end = get_my_position(len(container_op_list),
                                           job.my_proc_id,
                                           job.nprocs_per_node)
    db = PandoraDB(dsn=dsn, config='')
    await db.connect()

    try:
        repo = GateRepository(db)

        await repo.create_batched_table(node_id=job.my_node_id,
                                        proc_id=job.my_proc_id)

        builder = PandoraWindowedBuilder(window_size=window_size,
                                         label=job.my_proc_id)

        pending = []
        insert_batch_size = 1_000_000

        for high_level_op in container_op_list[proc_start:proc_end]:
            for batch, generator_time in generator_func(
                    circuit=high_level_op,
                    window_size=window_size,
            ):
                for out in builder.consume(batch):
                    pending.extend(out)

                    if len(pending) >= insert_batch_size:
                        await repo.insert_copy(pending)
                        pending.clear()

        final = builder.finalize()
        pending.extend(final)

        if pending:
            await repo.insert_copy(pending)

    finally:
        await db.close()

