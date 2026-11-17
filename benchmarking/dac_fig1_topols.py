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


def load_block_graph(bgraph: Path):
    """Rebuild the tqec BlockGraph from a TopoLS .bgraph file.

    Like topols.tools.pipe_sim.load_block_graph, but S and T gate sites (stored
    by TopoLS as the strings "S"/"T") become tqec ports, i.e. open boundaries
    where the gate's resource state is injected.
    """
    from tqec import BlockGraph
    from tqec.computation.cube import Cube, Port, ZXCube
    from tqec.computation.pipe import Pipe
    from tqec.utils.position import Position3D

    data = pickle.loads(bgraph.read_bytes())
    graph = BlockGraph(bgraph.stem)
    port_kind = {}
    for node_id, node in data["bgraph_metadata"].items():
        position = Position3D(*node["position"])
        if position in graph:
            continue
        other = node["other"]
        if isinstance(other, dict):
            graph.add_cube(position, Port(), f"{other['type']}_{other['qubit']}")
            if node["tqec"]:
                port_kind[position] = ZXCube.from_str(node["tqec"])
        elif isinstance(other, str):
            graph.add_cube(position, Port(), f"{other}_{node_id}")
        else:
            graph.add_cube(position, node["tqec"])
    for a, b in data["edge_metadata"].values():
        a, b = Position3D(*a), Position3D(*b)
        if graph.has_pipe_between(a, b):
            continue
        kind = None
        if a in port_kind or b in port_kind:
            ends = [Cube(q, port_kind.get(q, graph[q].kind)) for q in (a, b)]
            kind = Pipe.from_cubes(*ends).kind
        graph.add_pipe(a, b, kind)
    return graph


def surface_code_slice(bgraph: Path, distance_k: int = 1) -> dict:
    """Stabilizers of the measurement round with the most active plaquettes.

    tqec prepares and measures every syndrome qubit in the X basis; a CX from the
    syndrome qubit measures an X stabilizer, a CZ a Z stabilizer.
    """
    from tqec import compile_block_graph

    block_graph = load_block_graph(bgraph)
    filled = block_graph.fill_ports_for_minimal_simulation()[0]
    compiled = compile_block_graph(filled.graph, observables=filled.observables)
    circuit = compiled.generate_stim_circuit(k=distance_k, manhattan_radius=2,
                                             do_not_use_database=True)
    coords = circuit.get_final_qubit_coordinates()

    rounds, gates = [], {}   # gates: qubit -> [(gate, partner, is_control)] since its last reset
    for inst in circuit.flattened():
        targets = [t.value for t in inst.targets_copy() if t.is_qubit_target]
        if inst.name in ("R", "RX", "RY"):
            for q in targets:
                gates[q] = []
        elif inst.name in ("CX", "CZ"):
            for c, t in zip(targets[::2], targets[1::2]):
                gates.setdefault(c, []).append((inst.name, t, True))
                gates.setdefault(t, []).append((inst.name, c, False))
        elif inst.name in ("M", "MX", "MY"):
            rounds.append({q: list(gates.get(q, [])) for q in targets})
    # Syndrome qubits are measured in every round, data qubits once at the end.
    measured = {}
    for r in rounds:
        for q in r:
            measured[q] = measured.get(q, 0) + 1
    syndrome = {q for q, n in measured.items() if n > 2}
    best = max(rounds, key=lambda r: sum(1 for q in r if q in syndrome))
    plaquettes = []
    for q, ops in best.items():
        if q not in syndrome or not ops:
            continue
        x_type = any(g == "CX" and is_control for g, _p, is_control in ops)
        plaquettes.append({"ancilla": q, "type": "X" if x_type else "Z",
                           "data": sorted({p for _g, p, _c in ops})})
    data_qubits = sorted({d for pl in plaquettes for d in pl["data"]})
    used = data_qubits + [pl["ancilla"] for pl in plaquettes]
    return {
        "qubits": {str(q): list(coords[q]) for q in used},
        "plaquettes": plaquettes,
        "data": data_qubits,
        "num_qubits": circuit.num_qubits,
        "num_detectors": circuit.num_detectors,
        "num_ticks": circuit.num_ticks,
        "distance": 2 * distance_k + 1,
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
    args.out.write_text(json.dumps(result, indent=1))      # keep panel (c) even if tqec fails
    result["surface_code"] = surface_code_slice(bgraph)
    args.out.write_text(json.dumps(result, indent=1))
    sc = result["surface_code"]
    print(f"{len(result['pipe_diagram']['nodes'])} nodes, {len(result['pipe_diagram']['pipes'])} pipes; "
          f"stim (d={sc['distance']}): {sc['num_qubits']} qubits, {sc['num_detectors']} detectors, "
          f"{sc['num_ticks']} ticks; drawn round: {len(sc['plaquettes'])} stabilizers")


if __name__ == "__main__":
    main()
