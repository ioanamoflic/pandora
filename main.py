import asyncio
import logging
import sys

from pandora.db.core import PandoraDB
from pandora.db.repository import GateRepository
from pandora.db.service import PandoraService

DSN = "postgresql://moflici1:1234@localhost:5432/postgres"


async def run_fh(N: int, nproc: int, CONTAINER_ID):
    print(f"Starting FH {N}x{N} with {nproc} processes.")

    db = PandoraDB(DSN)
    await db.connect()

    repo = GateRepository(db)
    service = PandoraService(db=db, repo=repo)

    await service.build_pandora()

    service.parallel_decompose(
        nprocs=nproc,
        container_id=CONTAINER_ID,
        n_containers=1,
        N=N,
        window_size=10000,
    )

    await db.close()


async def run_rsa(BIG_N: int, nproc: int, container_id: int):
    print(f"Starting RSA with {nproc} processes.")

    db = PandoraDB(DSN)
    await db.connect()

    repo = GateRepository(db)
    service = PandoraService(db=db, repo=repo)

    await service.build_pandora()

    await db.close()

    service.parallel_decompose(
        nprocs=nproc,
        N=BIG_N,
        container_id=container_id,
        n_containers=1,
        window_size=10000,
    )


async def main():
    logging.basicConfig()
    logger = logging.getLogger("pandora")
    logger.setLevel(logging.INFO)

    if len(sys.argv) == 1:
        return

    next_arg = 1

    cmd = sys.argv[next_arg]

    if cmd == "fh":
        N = int(sys.argv[next_arg + 1])
        NPROC = int(sys.argv[next_arg + 2])
        CONTAINER_ID = int(sys.argv[next_arg + 3])

        await run_fh(N, NPROC, CONTAINER_ID)

    elif cmd == "rsa":
        BIG_N = int(sys.argv[next_arg + 1])
        NPROC = int(sys.argv[next_arg + 2])
        CONTAINER_ID = int(sys.argv[next_arg + 3])

        await run_rsa(BIG_N, NPROC, CONTAINER_ID)

    else:
        raise ValueError(f"Unknown mode: {cmd}")


if __name__ == "__main__":
    asyncio.run(main())
