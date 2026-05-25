import asyncio
import logging
import sys

from benchmarking.benchmark_adders import get_adder, replace_all_toffolis_qiskit
from pandora.db.core import PandoraDB
from pandora.db.repository import GateRepository, GateLayerRepository
from pandora.db.service import PandoraService


async def run_rsa(config_file, BIG_N: int, nproc: int, container_id: int):
    print(f"Starting RSA with {nproc} processes.")

    db = PandoraDB(config_file)
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


async def run_adder(config_file):
    adder_circuit = replace_all_toffolis_qiskit(get_adder(n_bits=2048))

    db = PandoraDB(config_file)
    await db.connect()

    repo = GateRepository(db)
    repo_layer = GateLayerRepository(db)

    service = PandoraService(db=db,
                             repo=repo,
                             repo_layered=repo_layer)

    await service.build_circuit(
        circuit=adder_circuit
    )
    await service.load_circuit_into_layered()


async def main():
    logging.basicConfig()
    logger = logging.getLogger("pandora")
    logger.setLevel(logging.INFO)

    if len(sys.argv) == 1:
        return

    next_arg = 1

    cmd = sys.argv[next_arg]
    config_file_path = sys.argv[next_arg + 1]

    if cmd == "adder":
        await run_adder(config_file_path)

    elif cmd == "rsa":
        BIG_N = int(sys.argv[next_arg + 2])
        NPROC = int(sys.argv[next_arg + 3])
        CONTAINER_ID = int(sys.argv[next_arg + 4])

        await run_rsa(config_file_path, BIG_N, NPROC, CONTAINER_ID)

    else:
        raise ValueError(f"Unknown mode: {cmd}")


if __name__ == "__main__":
    asyncio.run(main())
