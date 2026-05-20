import asyncio
import csv
import sys
import time

from benchmark_tket import generate_random_HHCXHH_circuit_occasionally_flipped

from pandora.db.core import PandoraDB
from pandora.db.repository import GateRepository
from pandora.db.service import PandoraService
from pandora.optimisation.optimiser import PandoraOptimiser
from pandora.translation.translator import PandoraGateTranslator


async def count_h_gates(db: PandoraDB) -> int:
    async with db.pool.acquire() as conn:
        return await conn.fetchval(
            "select count(id) from linked_circuit where type=$1;",
            PandoraGateTranslator.HPowGate.value,
        ) 

async def partition_table(db: PandoraDB, nprocs: int):
    async with db.pool.acquire() as conn:
        await conn.execute("alter table linked_circuit add column partition_id integer;")
        await conn.execute("update linked_circuit set partition_id = id % $1;", nprocs)
        
    
async def rewrite_parallel(
    db: PandoraDB,
    nprocs: int,
    nr_passes: int,
) -> None:
    
    await partition_table(db, nprocs)

    optimiser = PandoraOptimiser(
        db=db,
        pass_count=nr_passes,
        timeout=100,
        logger_id=1,
        max_concurrency=nprocs if nprocs > 0 else 1,
    )

    optimiser.hhcxhh_to_cx(dedicated_nproc=nprocs, run_multiple=True)
    await optimiser.start()


async def rewrite_sequential(db: PandoraDB, nr_passes: int) -> None:
    async with db.pool.acquire() as conn:
        await conn.execute(f"call linked_hhcxhh_to_cx_seq({nr_passes})")


async def run_single_case(
    db: PandoraDB,
    nq: int,
    n_rounds: int,
    nr_passes: int,
    sample_percentage: int | float,
    nprocs: int,
) -> float:
    total_time = 0.0

    for _ in range(n_rounds):
        rewrites, qc = generate_random_HHCXHH_circuit_occasionally_flipped(
            n_templates=nq,
            n_qubits=3,
            proba=sample_percentage / 100,
        )

        repo = GateRepository(db)
        service = PandoraService(db=db, repo=repo)

        await service.build_circuit(
            circuit=qc
        )

        print(
            f"Number of templates: {nq} for {nr_passes} passes and "
            f"{sample_percentage} proba with {rewrites} rewrites"
        )

        print("Rewrite...")
        start_time = time.time()

        if nprocs > 0:
            await rewrite_parallel(
                db=db,
                nprocs=nprocs,
                nr_passes=nr_passes,
            )
        else:
            await rewrite_sequential(
                db=db,
                nr_passes=nr_passes,
            )

        elapsed = time.time() - start_time
        print("Time to rewrite:", elapsed)
        total_time += elapsed

        h_count = await count_h_gates(db)
        assert h_count == 0

    return total_time / n_rounds


async def main():
    if len(sys.argv) != 3:
        sys.exit(0)

    config_file_path = sys.argv[1]
    nprocs = int(sys.argv[2])
    
    n_rounds = 1
    nr_passes = 1

    for sample_percentage in [0.1, 1, 10]:

        db = PandoraDB(config_file_path)
        await db.connect()

        try:
            out_file = f"pandora_template_search_random_flip_{sample_percentage}.csv"
            if nprocs > 0:
                out_file = f"pandora_template_search_random_flip_{sample_percentage}_parallel.csv"

            for nq in range(10_000, 100_001, 10_000):
                avg_time = await run_single_case(
                    db=db,
                    nq=nq,
                    n_rounds=n_rounds,
                    nr_passes=nr_passes,
                    sample_percentage=sample_percentage,
                    nprocs=nprocs,
                )

                with open(out_file, "a", newline="") as f:
                    writer = csv.writer(f)
                    writer.writerow((nq, avg_time, sample_percentage, nprocs))
        finally:
            await db.close()


if __name__ == "__main__":
    asyncio.run(main())
