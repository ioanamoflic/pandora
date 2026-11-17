"""TopoLS comparison, robustness check: extraction vs. vertex numbering, and equivalence.

    python benchmarking/dac_topols_extract_check.py [--database pandorazx_fig] [--renumberings 20]

PyZX's extract_circuit is a heuristic whose CNOT count depends on the numbering
of the vertices, and the diagrams of PyZX and PandoraZX are numbered differently.
For each circuit of benchmarking/dac_topols_inputs, this script simplifies the
diagram with both tools, renumbers each simplified diagram at random, extracts
with the same post-processing as dac_topols_prepare.py, and reports the CNOT
distribution. It also checks the committed extracted circuits with more than 10
qubits against the original with QCEC (smaller ones are tensor-checked by
dac_topols_prepare.py). Results: benchmarking/dac_topols_inputs/extract_renumbering.json
"""
import asyncio
import json
import random
import statistics
import sys
from pathlib import Path

import pyzx as zx
import qiskit.qasm2
from mqt import qcec
from qiskit.circuit.library import SwapGate

from pandora.db.core import PandoraDB
from pandora.db.repository import GateRepository
from pandora.db.service import PandoraService

ROOT = Path(__file__).resolve().parent.parent
INPUTS = ROOT / "benchmarking" / "dac_topols_inputs"
SW = [qiskit.qasm2.CustomInstruction("swap", 0, 2, SwapGate, builtin=True)]
K = int(sys.argv[sys.argv.index("--renumberings") + 1]) if "--renumberings" in sys.argv else 20
cfg = json.loads((ROOT / "default_config.json").read_text())
DATABASE = sys.argv[sys.argv.index("--database") + 1] if "--database" in sys.argv else "pandorazx_fig"
assert DATABASE != cfg.get("database", "postgres"), "use a scratch database, not the benchmark database"
cfg["database"] = DATABASE
rng = random.Random(1)


def post(g):
    """Same post-processing as dac_topols_prepare.py: extract, basic gates, basic optimisation."""
    return zx.optimize.basic_optimization(zx.extract_circuit(g.copy()).to_basic_gates()).to_basic_gates()


async def pandora(c):
    db = PandoraDB(cfg)
    await db.connect()
    try:
        svc = PandoraService(db=db, repo=GateRepository(db))
        await svc.build_circuit(qiskit.qasm2.loads(c.to_qasm(), custom_instructions=SW))
        await svc.convert_linked_circuit_to_zx()
        await svc.simplify_zx_full()
        return await svc.export_to_pyzx()
    finally:
        await db.close()


def renumber(g):
    h = zx.Graph()
    vs = list(g.vertices())
    rng.shuffle(vs)
    m = {v: h.add_vertex(g.type(v), g.qubit(v), g.row(v), g.phase(v)) for v in vs}
    es = list(g.edges())
    rng.shuffle(es)
    for e in es:
        s, t = g.edge_st(e)
        h.add_edge((m[s], m[t]), g.edge_type(e))
    h.set_inputs(tuple(m[v] for v in g.inputs()))
    h.set_outputs(tuple(m[v] for v in g.outputs()))
    return h


rows = {}
for name, info in json.loads((INPUTS / "prepare.json").read_text()).items():
    c = zx.Circuit.load(str(ROOT / "circuits/optimizer/Arithmetic_and_Toffoli" / f"{name}_before")).to_basic_gates()
    gp = c.to_graph()
    zx.full_reduce(gp)
    gz = asyncio.run(pandora(c))
    rows[name] = {}
    for tool, g in (("pyzx", gp), ("pandora", gz)):
        samples = [post(renumber(g)).twoqubitcount() for _ in range(K)]
        rows[name][tool] = {"as_is": post(g).twoqubitcount(), "min": min(samples), "max": max(samples),
                            "median": statistics.median(samples), "samples": samples}
    p, z = rows[name]["pyzx"], rows[name]["pandora"]
    print(f"{name:15s} CNOTs PyZX {p['as_is']:4d} renumbered {p['min']}-{p['max']} (median {p['median']}) | "
          f"PZX {z['as_is']:4d} renumbered {z['min']}-{z['max']} (median {z['median']})", flush=True)
    if info["qubits"] > 10:
        orig = qiskit.qasm2.loads((INPUTS / f"{name}__orig.qasm").read_text())
        for tool in ("pyzx", "pandora"):
            other = qiskit.qasm2.loads((INPUTS / f"{name}__{tool}.qasm").read_text())
            rows[name][f"qcec_{tool}"] = str(qcec.verify(orig, other).equivalence)
            print(f"  QCEC orig vs {tool}: {rows[name][f'qcec_{tool}']}", flush=True)

lower = sum(r["pandora"]["median"] < r["pyzx"]["median"] for r in rows.values())
overlap = sum(not (r["pandora"]["max"] < r["pyzx"]["min"] or r["pyzx"]["max"] < r["pandora"]["min"])
              for r in rows.values())
ratio = max(r[t]["max"] / r[t]["min"] for r in rows.values() for t in ("pyzx", "pandora"))
print(f"\nPZX median CNOTs lower on {lower}/{len(rows)}; ranges overlap on {overlap}/{len(rows)}; "
      f"largest max/min CNOT ratio {ratio:.2f}")
(INPUTS / "extract_renumbering.json").write_text(json.dumps(rows, indent=1))
