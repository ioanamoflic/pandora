import asyncio
import time
from typing import Optional

from pandora.db.core import PandoraDB
from pandora.db.repository import GateRepository
from pandora.translation.circuit_to_dag import PandoraWindowedBuilder
from pandora.pyLIQTR.utils.circuit_decomposition import circuit_decompose_multi

from pandora.util.qualtran_util import get_RSA, get_RSA_batch


def worker_entry(
    worker_id: int,
    nprocs: int,
    container_id: int,
    n_containers: int,
    window_size: int,
    N: Optional[int],
    config_file: str = None,
) -> None:
    asyncio.run(
        _worker_main(
            worker_id=worker_id,
            nprocs=nprocs,
            container_id=container_id,
            n_containers=n_containers,
            config_file=config_file,
            window_size=window_size,
            N=N,
        )
    )


async def _worker_main(
    worker_id: int,
    nprocs: int,
    container_id: int,
    n_containers: int,
    window_size: int,
    N: Optional[int],
    config_file: str = None,
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

    db = PandoraDB(config_file)
    await db.connect()

    try:
        repo = GateRepository(db)
        builder = PandoraWindowedBuilder(window_size=window_size, label=str(worker_id))

        for i, high_level_op in enumerate(container_op_list):
            if not (proc_start <= i < proc_end):
                continue

            for batch, t in get_RSA_batch(
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


async def _worker_main_verbose(
    worker_id: int,
    nprocs: int,
    container_id: int,
    n_containers: int,
    window_size: int,
    N: Optional[int],
    config_file: str = None,
) -> None:
    worker_label = str(worker_id)

    t0_total = time.perf_counter()

    t0 = time.perf_counter()
    proc_circuit = get_RSA(n=N)
    print(worker_label, "time_get_RSA:", time.perf_counter() - t0)

    t0 = time.perf_counter()
    circuit_decomposed_shallow = circuit_decompose_multi(proc_circuit, N=2)
    print(worker_label, "time_shallow_decompose:", time.perf_counter() - t0)

    t0 = time.perf_counter()
    high_level_op_list = [op for mom in circuit_decomposed_shallow for op in mom]
    print(worker_label, "time_flatten:", time.perf_counter() - t0)

    op_count = len(high_level_op_list)

    container_start = (op_count * container_id) // n_containers
    container_end = (op_count * (container_id + 1)) // n_containers
    container_op_list = high_level_op_list[container_start:container_end]

    container_op_count = len(container_op_list)
    proc_start = (container_op_count * worker_id) // nprocs
    proc_end = (container_op_count * (worker_id + 1)) // nprocs

    worker_op_list = container_op_list[proc_start:proc_end]

    print(
        worker_label,
        "op_count:", op_count,
        "container_ops:", container_op_count,
        "worker_ops:", len(worker_op_list),
        "window_size:", window_size,
    )

    db = PandoraDB(config_file)

    t0 = time.perf_counter()
    await db.connect()
    print(worker_label, "time_db_connect:", time.perf_counter() - t0)

    total_next_batch_time = 0.0
    total_reported_rsa_time = 0.0
    total_builder_time = 0.0
    total_insert_time = 0.0
    total_batches = 0
    total_input_ops = 0
    total_produced_gates = 0
    total_windows = 0

    try:
        repo = GateRepository(db)
        builder = PandoraWindowedBuilder(
            window_size=window_size,
            label=worker_label,
        )

        for op_idx, high_level_op in enumerate(worker_op_list):
            gen = get_RSA_batch(
                circuit=high_level_op,
                window_size=window_size,
            )

            while True:
                t_next = time.perf_counter()
                try:
                    batch, reported_rsa_time = next(gen)
                except StopIteration:
                    break
                next_batch_time = time.perf_counter() - t_next

                total_next_batch_time += next_batch_time
                total_reported_rsa_time += reported_rsa_time
                total_batches += 1
                total_input_ops += len(batch)

                produced = 0
                windows = 0
                insert_time = 0.0

                t_builder = time.perf_counter()

                for out in builder.consume(batch):
                    windows += 1
                    produced += len(out)

                    t_insert = time.perf_counter()
                    await repo.insert_copy(out)
                    insert_time += time.perf_counter() - t_insert

                builder_total = time.perf_counter() - t_builder
                builder_only = builder_total - insert_time

                total_builder_time += builder_only
                total_insert_time += insert_time
                total_produced_gates += produced
                total_windows += windows

                print(
                    worker_label,
                    "op_idx:", op_idx,
                    "batch_len:", len(batch),
                    "windows:", windows,
                    "produced:", produced,
                    "buffer_len:", len(builder.buffer),
                    "known_gates:", len(builder.gates),
                    "time_next_batch:", next_batch_time,
                    "time_rsa_reported:", reported_rsa_time,
                    "time_builder_only:", builder_only,
                    "time_insert:", insert_time,
                    "time_builder_plus_insert:", builder_total,
                )

        t_finalize = time.perf_counter()
        final = builder.finalize()
        finalize_time = time.perf_counter() - t_finalize

        final_insert_time = 0.0
        final_len = len(final) if final else 0

        if final:
            t_insert = time.perf_counter()
            await repo.insert_copy(final)
            final_insert_time = time.perf_counter() - t_insert

        total_insert_time += final_insert_time
        total_produced_gates += final_len

        print(
            worker_label,
            "FINAL",
            "final_len:", final_len,
            "time_finalize:", finalize_time,
            "time_final_insert:", final_insert_time,
        )

    finally:
        t_close = time.perf_counter()
        await db.close()
        db_close_time = time.perf_counter() - t_close

    total_time = time.perf_counter() - t0_total

    print(
        worker_label,
        "SUMMARY",
        "total_time:", total_time,
        "total_batches:", total_batches,
        "total_input_ops:", total_input_ops,
        "total_windows:", total_windows,
        "total_produced_gates:", total_produced_gates,
        "total_next_batch_time:", total_next_batch_time,
        "total_reported_rsa_time:", total_reported_rsa_time,
        "total_builder_time:", total_builder_time,
        "total_insert_time:", total_insert_time,
        "time_db_close:", db_close_time,
        "unaccounted_time:",
        total_time
        - total_next_batch_time
        - total_builder_time
        - total_insert_time,
    )
