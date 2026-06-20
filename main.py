import asyncio
import logging
import time

from benchmarking.benchmark_adders import get_adder, replace_all_toffolis_qiskit
from pandora.db.core import PandoraDB
from pandora.db.repository import GateRepository, GateLayerRepository
from pandora.db.service import PandoraService

import argparse

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
        config_file=config_file,
        container_id=container_id,
        n_containers=1,
        window_size=10000,
    )


async def run_adder(config_file, N_BITS: int):
    adder_circuit = replace_all_toffolis_qiskit(get_adder(n_bits=N_BITS))

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
    parser = argparse.ArgumentParser()
    parser.add_argument('-c', '--config',
                        help='PostgreSQL config file path',
                        default='default_config.json')

    subparsers = parser.add_subparsers(dest='mode', required=True)

    rsa_parser = subparsers.add_parser('rsa', help='Run RSA decomposition')
    rsa_parser.add_argument('BIG_N', type=int, help='RSA modulus bit size')
    rsa_parser.add_argument('NPROC', type=int, help='Number of parallel processes')
    rsa_parser.add_argument('CONTAINER_ID', type=int, help='Container ID')

    adder_parser = subparsers.add_parser('adder', help='Run adder circuit')
    adder_parser.add_argument('N_BITS', type=int, help='Number of bits for the adder')

    subparsers.add_parser('fh', help='Fermi-Hubbard (not yet implemented)')

    args = parser.parse_args()

    logging.basicConfig()
    logger = logging.getLogger("pandora")
    logger.setLevel(logging.INFO)

    match args.mode:
        case "adder":
            await run_adder(args.config, args.N_BITS)
        case "rsa":
            await run_rsa(args.config, args.BIG_N, args.NPROC, args.CONTAINER_ID)
        case "fh":
            raise NotImplementedError("FH not supported in this version yet")


if __name__ == "__main__":
    start = time.time()
    asyncio.run(main())
    print("this took: ", time.time() - start)