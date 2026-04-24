import asyncio
import logging
import sys

from pandora.db.core import PandoraDB
from pandora.db.repository import GateRepository
from pandora.db.service import PandoraService
from pandora.parallel.job import ProcJob


async def run_decomposition(config_file, job: ProcJob):

    db = PandoraDB(config_file)
    await db.connect()

    repo = GateRepository(db)
    service = PandoraService(db=db, repo=repo)

    await service.build_pandora()

    await db.close()

    service.parallel_decompose(
        job=job,
        window_size=int(1e5),
    )


async def main():
    logging.basicConfig()
    logger = logging.getLogger("pandora")
    logger.setLevel(logging.INFO)

    if len(sys.argv) == 1:
        return

    next_arg = 1

    config_file = sys.argv[next_arg]
    cmd = sys.argv[next_arg + 1]
    N_NODES = int(sys.argv[next_arg + 2])
    N_PROC_PER_NODE = int(sys.argv[next_arg + 3])
    MY_NODE_ID = int(sys.argv[next_arg + 4])

    if cmd == "fh":
        N = int(sys.argv[next_arg + 5])

        job = ProcJob(kind='fermi-hubbard',
                      N=N,
                      nprocs_per_node=N_PROC_PER_NODE,
                      n_nodes=N_NODES,
                      my_node_id=MY_NODE_ID)

        await run_decomposition(config_file=config_file, job=job)

    elif cmd == "rsa":
        N_BITS = int(sys.argv[next_arg + 5])

        job = ProcJob(kind='rsa',
                      n_bits=N_BITS,
                      nprocs_per_node=N_PROC_PER_NODE,
                      n_nodes=N_NODES,
                      my_node_id=MY_NODE_ID)

        await run_decomposition(config_file=config_file, job=job)

    else:
        raise ValueError(f"Unknown circuit: {cmd}")


if __name__ == "__main__":
    asyncio.run(main())
