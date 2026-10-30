import asyncio
import argparse
import os


def positive_int(value):
    value = int(value)
    if value < 1:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return value


def rsa_node_id(nodes: int) -> int:
    """Validate the launcher's shard assignment before opening a database."""
    raw_id = os.environ.get("PANDORA_NODE_ID")
    raw_count = os.environ.get("PANDORA_NODE_COUNT")
    if raw_id is None and raw_count is None:
        if nodes == 1:
            return 0
        raise ValueError("--nodes > 1 requires a multi-node Pandora launcher")
    if raw_id is None or raw_count is None:
        raise ValueError("PANDORA_NODE_ID and PANDORA_NODE_COUNT must both be set")
    try:
        node_id, node_count = int(raw_id), int(raw_count)
    except ValueError as exc:
        raise ValueError("Pandora node ID and count must be integers") from exc
    if node_count != nodes:
        raise ValueError("PANDORA_NODE_COUNT must match --nodes")
    if not 0 <= node_id < nodes:
        raise ValueError("PANDORA_NODE_ID must be in the range 0 to --nodes - 1")
    return node_id


async def run_rsa(config_file, BIG_N: int, nproc: int, nodes: int):
    if nproc < 1 or nodes < 1:
        raise ValueError("--nproc and --nodes must be positive integers")
    node_id = rsa_node_id(nodes)

    from pandora.db.core import PandoraDB
    from pandora.db.repository import GateRepository
    from pandora.db.service import PandoraService

    print(f"Starting RSA chunk {node_id + 1}/{nodes} with {nproc} processes.")

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
        container_id=node_id,
        n_containers=nodes,
        window_size=10000,
    )


async def run_adder(config_file, N_BITS: int):
    from benchmarking.benchmark_adders import get_adder, replace_all_toffolis_qiskit
    from pandora.db.core import PandoraDB
    from pandora.db.repository import GateRepository, GateLayerRepository
    from pandora.db.service import PandoraService

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
                        default=None)

    subparsers = parser.add_subparsers(dest='mode', required=True)

    rsa_parser = subparsers.add_parser('rsa', help='Run RSA decomposition')
    rsa_parser.add_argument('--n', type=int, required=True, help='RSA modulus bit size')
    rsa_parser.add_argument('--nproc', type=positive_int, required=True,
                            help='Number of parallel processes per node')
    rsa_parser.add_argument('--nodes', type=positive_int, default=1,
                            help='Number of nodes sharing the circuit decomposition (default: 1)')

    adder_parser = subparsers.add_parser('adder', help='Run adder circuit')
    adder_parser.add_argument('--nbits', type=int, required=True, help='Number of bits for the adder')

    subparsers.add_parser('fh', help='Fermi-Hubbard (not yet implemented)')

    args = parser.parse_args()

    match args.mode:
        case "adder":
            await run_adder(args.config, args.nbits)
        case "rsa":
            try:
                rsa_node_id(args.nodes)
            except ValueError as exc:
                parser.error(str(exc))
            await run_rsa(args.config, args.n, args.nproc, args.nodes)
        case "fh":
            raise NotImplementedError("FH not supported in this version yet")


if __name__ == "__main__":
    asyncio.run(main())
