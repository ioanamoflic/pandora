"""TopoLS comparison, step 1: original / PyZX / PandoraZX versions of small Clifford+T circuits.

    python benchmarking/dac_topols_prepare.py <work dir> [--database pandorazx_fig]

For 12 small circuits of the Nam et al. suite, simplifies the ZX diagram with
PyZX full_reduce and with PandoraZX full_reduce (in a scratch database), extracts
a circuit from each with the same post-processing (PyZX extract_circuit,
basic gates, basic_optimization), checks tensors up to 10 qubits, and writes
<work dir>/benchmark/<circuit>__{orig,pyzx,pandora}.qasm and prepare.json.
"""
import asyncio, json, sys
from fractions import Fraction
from pathlib import Path
import pyzx as zx
import qiskit.qasm2
from qiskit.circuit.library import SwapGate
from pandora.db.core import PandoraDB
from pandora.db.repository import GateRepository
from pandora.db.service import PandoraService

OUT = Path(sys.argv[1]); (OUT / "benchmark").mkdir(parents=True, exist_ok=True)
ROOT = Path("/home/ioanamoflic/pandora")
OPT = ROOT / "circuits/optimizer"
SW = [qiskit.qasm2.CustomInstruction("swap", 0, 2, SwapGate, builtin=True)]
cfg = json.loads((ROOT / "default_config.json").read_text())
DATABASE = sys.argv[sys.argv.index("--database") + 1] if "--database" in sys.argv else "pandorazx_fig"
assert DATABASE != cfg.get("database", "postgres"), "use a scratch database, not the benchmark database"
cfg["database"] = DATABASE

def qasm(c):
    lines = ['OPENQASM 2.0;', 'include "qelib1.inc";', f'qreg q[{c.qubits}];']
    for g in c.gates:
        n = g.name
        if n == "CNOT": lines.append(f"cx q[{g.control}], q[{g.target}];")
        elif n == "CZ": lines.append(f"cz q[{g.control}], q[{g.target}];")
        elif n == "HAD": lines.append(f"h q[{g.target}];")
        elif n == "NOT": lines.append(f"x q[{g.target}];")
        elif n in ("Z", "S", "T", "ZPhase"):
            ph = {"Z": Fraction(1), "S": Fraction(1, 2), "T": Fraction(1, 4)}.get(n) if n != "ZPhase" else Fraction(g.phase)
            if getattr(g, "adjoint", False): ph = -ph
            ph %= 2
            seq = {Fraction(0): [], Fraction(1, 4): ["t"], Fraction(1, 2): ["s"], Fraction(3, 4): ["s", "t"], Fraction(1): ["z"],
                   Fraction(5, 4): ["z", "t"], Fraction(3, 2): ["sdg"], Fraction(7, 4): ["tdg"]}[ph]
            lines += [f"{x} q[{g.target}];" for x in seq]
        else:
            raise ValueError(f"unsupported gate {g}")
    return "\n".join(lines) + "\n"

def post(g):
    """Identical post-processing for both tools: extract, basic gates, basic optimisation."""
    return zx.optimize.basic_optimization(zx.extract_circuit(g.copy()).to_basic_gates()).to_basic_gates()

def stats(c):
    return {"gates": len(c.gates), "twoq": c.twoqubitcount(), "t": zx.tcount(c)}

async def pandora(c):
    db = PandoraDB(cfg); await db.connect()
    try:
        svc = PandoraService(db=db, repo=GateRepository(db))
        await svc.build_circuit(qiskit.qasm2.loads(c.to_qasm(), custom_instructions=SW))
        await svc.convert_linked_circuit_to_zx()
        await svc.simplify_zx_full()
        return await svc.export_to_pyzx()
    finally:
        await db.close()

def diag(g):
    return sum(1 for v in g.vertices() if g.type(v) in (1, 2)), g.num_edges()

names = ["tof_3", "tof_4", "tof_5", "barenco_tof_3", "barenco_tof_4", "barenco_tof_5", "mod5_4",
         "vbe_adder_3", "rc_adder_6", "mod_mult_55", "gf2^E4_mult", "qcla_com_7", "mod_red_21"]
report = {}
for name in names:
    f = OPT / "Arithmetic_and_Toffoli" / f"{name}_before"
    if not f.exists():
        continue
    c = zx.Circuit.load(str(f)).to_basic_gates()
    if c.qubits > 16 or len(c.gates) > 400:
        continue
    gp = c.to_graph(); zx.full_reduce(gp)
    gz = asyncio.run(pandora(c))
    versions = {"orig": c, "pyzx": post(gp), "pandora": post(gz)}
    ok = {k: (zx.compare_tensors(c, v, preserve_scalar=False) if c.qubits <= 10 else None) for k, v in versions.items()}
    for k, v in versions.items():
        (OUT / "benchmark" / f"{name}__{k}.qasm").write_text(qasm(v))
    report[name] = {"qubits": c.qubits, "diagram": {"pyzx": diag(gp), "pandora": diag(gz)},
                    **{k: stats(v) for k, v in versions.items()}, "tensor_ok": ok}
    print(f"{name:14s} q={c.qubits:2d} | diagram PyZX {diag(gp)} PZX {diag(gz)} | "
          + " | ".join(f"{k}: {stats(v)['gates']}g {stats(v)['twoq']}cx {stats(v)['t']}T" for k, v in versions.items())
          + f" | tensor {ok}")
(OUT / "prepare.json").write_text(json.dumps(report, indent=1))
