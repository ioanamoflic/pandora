"""Pivot-order ablation and repeated runs for the PandoraZX DAC paper.

    python benchmarking/dac_ablation.py --database pandorazx_fig --repeats 3 \
        --out benchmarking/dac_ablation.csv [--quick]

For every case, PandoraZX full_reduce runs in two variants:
  cost  the default implementation (pivots in order of (deg u - 1)(deg v - 1))
  id    identical, except that the cost term is removed from the ORDER BY of
        zx_pivot_simp and zx_pivot_boundary_simp, so pivots run in identifier order
Each (case, variant) is repeated --repeats times; runtime and spider/edge counts
are appended to the CSV. Use a scratch database: build_pandora drops its tables.
Run it when no other benchmark is running, since it measures wall-clock time.
"""

import argparse
import asyncio
import csv
import json
import time
from pathlib import Path

import pyzx as zx
import qiskit.qasm2
from qiskit.circuit.library import SwapGate

from pandora.db.core import PandoraDB
from pandora.db.repository import GateRepository
from pandora.db.service import PandoraService

ROOT = Path(__file__).resolve().parent.parent
OPT = ROOT / "circuits" / "optimizer"
GEN = ROOT / "circuits" / "generated"
PIVOT_SQL = ROOT / "src/pandora/db/generic_procedures/zx_rewrites/zx_pivot_simp.sql"
SWAP = [qiskit.qasm2.CustomInstruction("swap", 0, 2, SwapGate, builtin=True)]

CASES = {   # family -> circuit files (moderate sizes; all finish within seconds to minutes)
    "Binary adder": [OPT / "QFT_and_Adders" / f"Adder{n}_before" for n in (64, 128, 256)],
    "GF multiplier": [OPT / "Arithmetic_and_Toffoli" / f"gf2^E{n}_mult_before" for n in (16, 32, 64)],
    "IQP": [GEN / "IQP" / f"IQP {n}.qasm" for n in (32, 48, 64)],
}
QUICK = {
    "Binary adder": [OPT / "QFT_and_Adders" / "Adder8_before"],
    "GF multiplier": [OPT / "Arithmetic_and_Toffoli" / "gf2^E4_mult_before"],
    "IQP": [GEN / "IQP" / "IQP 4.qasm"],
}
COST_TERMS = [
    "                GREATEST((v0.degree - 1), 0) * GREATEST((v1.degree - 1), 0),\n",
    "                GREATEST(p.v_degree - 1, 0) * GREATEST(wb.w_degree - 1, 0),\n",
]


def case_name(path: Path) -> str:
    return path.name.removesuffix("_before").removesuffix(".qasm")


def id_ordered_pivot_sql() -> str:
    sql = PIVOT_SQL.read_text()
    for term in COST_TERMS:
        assert sql.count(term) == 1, f"pivot ORDER BY changed: {term.strip()}"
        sql = sql.replace(term, "")
    return sql


async def run_case(config, path: Path, variant: str):
    circuit = zx.Circuit.load(str(path)).to_basic_gates()
    db = PandoraDB(config)
    await db.connect()
    try:
        service = PandoraService(db=db, repo=GateRepository(db))
        await service.build_circuit(qiskit.qasm2.loads(circuit.to_qasm(), custom_instructions=SWAP))
        if variant == "id":
            async with db.acquire() as conn:
                await conn.execute(id_ordered_pivot_sql())
        await service.convert_linked_circuit_to_zx()
        async with db.acquire() as conn:
            before = await conn.fetchrow("SELECT (SELECT count(*) FROM zx_edge) AS e, "
                                         "(SELECT count(*) FROM zx_vertex WHERE type IN (32, 33)) AS s")
        start = time.perf_counter()
        await service.simplify_zx_full()
        seconds = time.perf_counter() - start
        async with db.acquire() as conn:
            after = await conn.fetchrow("SELECT (SELECT count(*) FROM zx_edge) AS e, "
                                        "(SELECT count(*) FROM zx_vertex WHERE type IN (32, 33)) AS s")
        graph = await service.export_to_pyzx() if len(circuit.gates) < 200 else None
    finally:
        await db.close()
    ok = zx.compare_tensors(circuit, graph, preserve_scalar=False) if graph is not None else None
    return {"gates": len(circuit.gates), "seconds": seconds,
            "spiders_before": before["s"], "spiders_after": after["s"],
            "edges_before": before["e"], "edges_after": after["e"], "tensor_ok": ok}


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--database", required=True, help="scratch PostgreSQL database")
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--out", type=Path, default=Path(__file__).with_name("dac_ablation.csv"))
    parser.add_argument("--quick", action="store_true", help="tiny circuits only (smoke test)")
    args = parser.parse_args()

    config = json.loads((ROOT / "default_config.json").read_text())
    if args.database == config.get("database", "postgres"):
        raise SystemExit(f"Refusing to use '{args.database}': it is the benchmark database of "
                         "default_config.json, and build_pandora would drop its tables.")
    config["database"] = args.database
    cases = QUICK if args.quick else CASES
    new_file = not args.out.exists()
    with args.out.open("a", newline="") as f:
        writer = None
        for family, paths in cases.items():
            for path in paths:
                for run in range(1, args.repeats + 1):
                    for variant in ("cost", "id"):     # interleaved, so drift affects both
                        row = {"family": family, "circuit": case_name(path),
                               "variant": variant, "run": run,
                               **asyncio.run(run_case(config, path, variant))}
                        if writer is None:
                            writer = csv.DictWriter(f, fieldnames=list(row))
                            if new_file:
                                writer.writeheader()
                        writer.writerow(row)
                        f.flush()
                        print(f"{family:14s} {row['circuit']:16s} {variant:4s} run {run}: "
                              f"{row['seconds']:7.2f} s, spiders {row['spiders_after']}, "
                              f"edges {row['edges_after']}, tensor {row['tensor_ok']}")


if __name__ == "__main__":
    main()
