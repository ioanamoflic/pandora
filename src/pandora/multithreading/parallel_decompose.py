import asyncio
from typing import Optional

from pandora.db.core import PandoraDB
from pandora.db.repository import GateRepository
from pandora.translation.circuit_to_dag import PandoraWindowedBuilder
from pyLIQTR.utils.circuit_decomposition import circuit_decompose_multi

from pandora.util.qualtran_util import get_RSA, get_RSA_batch


def worker_entry(
    worker_id: int,
    nprocs: int,
    container_id: int,
    n_containers: int,
    dsn: str,
    window_size: int,
    N: Optional[int],
) -> None:
    asyncio.run(
        _worker_main(
            worker_id=worker_id,
            nprocs=nprocs,
            container_id=container_id,
            n_containers=n_containers,
            dsn=dsn,
            window_size=window_size,
            N=N,
        )
    )


async def _worker_main(
    worker_id: int,
    nprocs: int,
    container_id: int,
    n_containers: int,
    dsn: str,
    window_size: int,
    N: Optional[int],
) -> None:
    proc_circuit = get_RSA(n=N)
    circuit_decomposed_shallow = circuit_decompose_multi(proc_circuit, N=2)

    high_level_op_list = [op for mom in circuit_decomposed_shallow for op in mom]
    op_count = len(high_level_op_list)

    container_start = (op_count * container_id) // n_containers
    container_end = (op_count * (container_id + 1)) // n_containers
    container_op_list = high_level_op_list[container_start:container_end]

    container_op_count = len(container_op_list)
    proc_start = (container_op_count * worker_id) // nprocs
    proc_end = (container_op_count * (worker_id + 1)) // nprocs

    db = PandoraDB(dsn)
    await db.connect()

    try:
        repo = GateRepository(db)
        builder = PandoraWindowedBuilder(window_size=window_size, label=worker_id)

        for i, high_level_op in enumerate(container_op_list):
            if not (proc_start <= i < proc_end):
                continue

            for batch, _ in get_RSA_batch(
                circuit=high_level_op,
                window_size=window_size,
            ):
                for out in builder.consume(batch):
                    await repo.insert_copy(out)

        final = builder.finalize()
        if final:
            await repo.insert_copy(final)
    finally:
        await db.close()
