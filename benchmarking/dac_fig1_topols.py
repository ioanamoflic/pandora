"""Panels (c) and (d) of Fig. 1: run TopoLS and tqec on the PandoraZX example.

Run with the Python of the TopoLS environment (it needs topols, tqec, stim):

    .venv_claude/bin/python benchmarking/dac_fig1_topols.py \
        --qasm <example.qasm> --topols TopoLS --work <scratch dir> \
        --out benchmarking/dac_fig1_topols.json

Steps: TopoLS `prog.py` (3D embedding) and `2tqec.py` (block graph) run with
`--work` as working directory, so nothing is written into the TopoLS checkout.
tqec then fills the ports, compiles the block graph and generates the Stim
circuit at distance 3. The JSON holds the pipe diagram (cubes and pipes) and,
for panel (d), the qubits and stabilizers of one round of the Stim circuit.
"""

import argparse
import json
import pickle
import shutil
import subprocess
import sys
from pathlib import Path

TOPOLS_ARGS = ["-b", "20", "-zx", "1", "-dir", "1", "-l", "4", "-r", "0",
               "-s", "2", "-t", "2", "-i", "1000", "-csv", "result", "-sp", "0"]


def run_topols(qasm: Path, topols: Path, work: Path, name: str) -> Path:
    (work / "benchmark").mkdir(parents=True, exist_ok=True)
    shutil.copy(qasm, work / "benchmark" / f"{name}.qasm")
    docs = topols / "docs"
    subprocess.run([sys.executable, str(docs / "prog.py"), "-f", name, *TOPOLS_ARGS],
                   cwd=work, check=True)
    subprocess.run([sys.executable, str(docs / "2tqec.py"), "-f", name, "-p", "True"],
                   cwd=work, check=True)
    return work / "result" / "bgraph" / f"{name}.bgraph"


def pipe_diagram(bgraph: Path) -> dict:
    data = pickle.loads(bgraph.read_bytes())
    nodes = []
    for node_id, node in data["bgraph_metadata"].items():
        other = node.get("other")
        nodes.append({
            "id": str(node_id),
            "position": [int(c) for c in node["position"]],
            "tqec": node.get("tqec"),
            "other": other if isinstance(other, (str, type(None))) else
                     {k: (v if isinstance(v, (str, int, float)) else str(v)) for k, v in other.items()},
        })
    pipes = [[[int(c) for c in a], [int(c) for c in b]] for a, b in data["edge_metadata"].values()]
    return {"nodes": nodes, "pipes": pipes}


def surface_code_slice(bgraph: Path, distance_k: int = 1) -> dict:
    """Qubits and stabilizers of the busiest measurement round of the circuit."""
    import stim
    from tqec import compile_block_graph
    from topols.tools.pipe_sim import load_block_graph

    block_graph = load_block_graph(bgraph)
    filled = block_graph.fill_ports_for_minimal_simulation()[0]
    compiled = compile_block_graph(filled.graph, observables=filled.observables)
    circuit = compiled.generate_stim_circuit(k=distance_k, manhattan_radius=2)

    coords = {q: c for q, c in circuit.get_final_qubit_coordinates().items()}
    flat = circuit.flattened()
    # Split into rounds at every measurement layer; keep the round in which the
    # most measurement qubits are measured (a full layer of stabilizers).
    rounds, current = [], {"reset_x": set(), "reset_z": set(), "measured": set(), "h": set()}
    for inst in flat:
        name = inst.name
        targets = [t.value for t in inst.targets_copy() if t.is_qubit_target]
        if name in ("RX",):
            current["reset_x"].update(targets)
        elif name in ("R", "RZ"):
            current["reset_z"].update(targets)
        elif name == "H":
            current["h"].update(targets)
        elif name in ("M", "MZ", "MR", "MX", "MRX"):
            current["measured"].update(targets)
            current["measure_basis_x"] = current.get("measure_basis_x", set())
            if name in ("MX", "MRX"):
                current["measure_basis_x"].update(targets)
            rounds.append(current)
            current = {"reset_x": set(), "reset_z": set(), "measured": set(), "h": set()}
    best = max(rounds, key=lambda r: len(r["measured"]))
    ancillas = sorted(best["measured"])
    x_type = sorted(q for q in ancillas
                    if q in best["reset_x"] or q in best.get("measure_basis_x", set()) or q in best["h"])
    used = set()
    for inst in flat:
        used.update(t.value for t in inst.targets_copy() if t.is_qubit_target)
    data_qubits = sorted(q for q in used if q not in set(ancillas) and q in coords)
    return {
        "qubits": {str(q): list(coords[q]) for q in used if q in coords},
        "ancillas": ancillas,
        "x_ancillas": x_type,
        "data": data_qubits,
        "num_qubits": circuit.num_qubits,
        "num_detectors": circuit.num_detectors,
        "num_rounds": len(rounds),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--qasm", type=Path, required=True)
    parser.add_argument("--topols", type=Path, required=True, help="TopoLS checkout")
    parser.add_argument("--work", type=Path, required=True, help="scratch working directory")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--name", default="pzx_fig1")
    args = parser.parse_args()

    bgraph = run_topols(args.qasm.resolve(), args.topols.resolve(), args.work.resolve(), args.name)
    result = {"pipe_diagram": pipe_diagram(bgraph)}
    result["surface_code"] = surface_code_slice(bgraph)
    args.out.write_text(json.dumps(result, indent=1))
    sc = result["surface_code"]
    print(f"{len(result['pipe_diagram']['nodes'])} nodes, {len(result['pipe_diagram']['pipes'])} pipes; "
          f"stim: {sc['num_qubits']} qubits, {sc['num_detectors']} detectors")


if __name__ == "__main__":
    main()
