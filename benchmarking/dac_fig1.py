"""Fig. 1 of the PandoraZX DAC paper: the compilation flow on a small example.

    (a) input circuit  ->  (b) ZX diagram after PandoraZX full_reduce
    ->  (c) TopoLS 3D pipe diagram  ->  (d) tqec surface-code circuit

Usage:
    python benchmarking/dac_fig1.py --out <paper>/figures [--database pandorazx_fig]
        [--topols benchmarking/dac_fig1_topols.json]

With --database, the example circuit is simplified by PandoraZX in that
(scratch) PostgreSQL database and the result is cached in
dac_fig1_pandorazx.json; without it, the cached diagram is used.
Panels (c) and (d) are drawn from the TopoLS/tqec output of
dac_fig1_topols.py when given; otherwise only (a) and (b) are drawn.
"""

import argparse
import asyncio
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pyzx as zx
from matplotlib.patches import Circle, FancyArrowPatch, Rectangle

HERE = Path(__file__).resolve().parent
CACHE = HERE / "dac_fig1_pandorazx.json"
COLUMN_WIDTH_IN = 3.5

# The example: 12 gates on 3 qubits with four T gates (randomly generated,
# seed 203). It was chosen because the PandoraZX result keeps a two-qubit
# interaction for the layout step and can be drawn without edge crossings.
GATES = [("CNOT", 1, 0), ("CNOT", 2, 1), ("T", 2), ("CNOT", 0, 1), ("T", 2),
         ("S", 0), ("CNOT", 2, 1), ("T", 2), ("CNOT", 0, 1), ("HAD", 1),
         ("S", 1), ("T", 1)]

INK, MUTED = "#0b0b0b", "#52514e"
Z_FILL, X_FILL = "#ccffcc", "#ff8888"      # usual ZX colours (PyZX)
HADAMARD_EDGE = "#2a78d6"
T_FILL = "#fde9b6"


def example_circuit() -> zx.Circuit:
    c = zx.Circuit(3)
    for name, *args in GATES:
        c.add_gate(name, *args)
    return c


def pandorazx_graph(database: str | None):
    if database is None:
        return zx.Graph.from_json(CACHE.read_text())

    import qiskit.qasm2
    from qiskit.circuit.library import SwapGate
    from pandora.db.core import PandoraDB
    from pandora.db.repository import GateRepository
    from pandora.db.service import PandoraService

    config = json.loads((HERE.parent / "default_config.json").read_text())
    config["database"] = database
    qc = qiskit.qasm2.loads(example_circuit().to_qasm(), custom_instructions=[
        qiskit.qasm2.CustomInstruction("swap", 0, 2, SwapGate, builtin=True)])

    async def run():
        db = PandoraDB(config)
        await db.connect()
        try:
            service = PandoraService(db=db, repo=GateRepository(db))
            await service.build_circuit(qc)
            await service.convert_linked_circuit_to_zx()
            await service.simplify_zx_full()
            return await service.export_to_pyzx()
        finally:
            await db.close()

    graph = asyncio.run(run())
    CACHE.write_text(graph.to_json())
    return graph


# --------------------------------------------------------------------- (a)
def draw_circuit(ax):
    n = 3
    last = [-1] * n
    placed = []
    for name, *qs in GATES:
        lo, hi = min(qs), max(qs)
        col = max(last[lo:hi + 1]) + 1
        for q in range(lo, hi + 1):
            last[q] = col
        placed.append((name, qs, col))
    width = max(last) + 1
    for q in range(n):
        ax.plot([-0.6, width - 0.4], [-q, -q], color=INK, lw=0.7, zorder=1)
        ax.text(-0.75, -q, f"$q_{q}$", ha="right", va="center", fontsize=7)
    for name, qs, col in placed:
        if name == "CNOT":
            c, t = qs
            tip = -t + (0.2 if t < c else -0.2)        # through the target circle
            ax.plot([col, col], [-c, tip], color=INK, lw=0.7, zorder=2)
            ax.add_patch(Circle((col, -c), 0.09, color=INK, zorder=3))
            ax.add_patch(Circle((col, -t), 0.2, fill=False, ec=INK, lw=0.7, zorder=3))
            ax.plot([col - 0.2, col + 0.2], [-t, -t], color=INK, lw=0.7, zorder=3)
        else:
            label = {"HAD": "H", "T": "T", "S": "S"}[name]
            fill = T_FILL if name == "T" else "white"
            ax.add_patch(Rectangle((col - 0.27, -qs[0] - 0.27), 0.54, 0.54,
                                   fc=fill, ec=INK, lw=0.7, zorder=3))
            ax.text(col, -qs[0], label, ha="center", va="center", fontsize=6.5, zorder=4)
    ax.set_xlim(-1.2, width - 0.2)
    ax.set_ylim(-n + 0.4, 0.6)


# --------------------------------------------------------------------- (b)
def phase_label(phase) -> str:
    if phase == 0:
        return ""
    if phase == 1:
        return r"$\pi$"
    num = "" if phase.numerator == 1 else str(phase.numerator)
    return rf"${num}\pi/{phase.denominator}$"


# Positions of the interior spiders: each on its qubit row, so the diagram
# reads like a circuit and has no edge crossings (inputs at x=0, outputs at x=3).
SPIDER_POS = {4: (0.9, 0.0), 6: (2.1, 0.0), 3: (0.9, -1.0), 7: (2.1, -1.0), 5: (1.5, -2.0)}


def zx_layout(g):
    pos = {v: (0.0, -g.qubit(v)) for v in g.inputs()}
    pos.update({v: (3.0, -g.qubit(v)) for v in g.outputs()})
    pos.update(SPIDER_POS)
    return pos


def draw_zx(ax, g):
    pos = zx_layout(g)
    for e in g.edges():
        s, t = g.edge_st(e)
        (x0, y0), (x1, y1) = pos[s], pos[t]
        if g.edge_type(e) == zx.EdgeType.HADAMARD:
            ax.plot([x0, x1], [y0, y1], color=HADAMARD_EDGE, lw=0.9, ls=(0, (2.5, 1.5)), zorder=1)
        else:
            ax.plot([x0, x1], [y0, y1], color=INK, lw=0.8, zorder=1)
    for v in g.vertices():
        x, y = pos[v]
        ty = g.type(v)
        if ty == zx.VertexType.BOUNDARY:
            ax.add_patch(Circle((x, y), 0.05, color=INK, zorder=2))
            continue
        fill = Z_FILL if ty == zx.VertexType.Z else X_FILL
        ax.add_patch(Circle((x, y), 0.17, fc=fill, ec=INK, lw=0.7, zorder=3))
        label = phase_label(g.phase(v))
        if label:
            ax.text(x, y + 0.25, label, ha="center", va="bottom", fontsize=6.5, zorder=4)
    ax.set_xlim(-0.4, 3.4)
    ax.set_ylim(-2.6, 0.75)


# --------------------------------------------------------------- (c), (d)
# tqec colours: X boundaries red, Z boundaries blue, Y green, Hadamard yellow.
BASIS_COLOR = {"X": "#ff7f7f", "Z": "#7396ff", "Y": "#63c676"}
COLLAR = "#ffff65"
PORT = "#bdbdbd"
SPECIAL = {"S": "#63c676", "T": "#c597e6"}
COS30, SIN30 = 0.8660254, 0.5


def iso(x, y, z):
    """Isometric projection with time (z) pointing up."""
    return ((x - y) * COS30, (x + y) * SIN30 + z)


def box_faces(center, half):
    """The three visible faces (-x, -y, +z) of an axis-aligned box."""
    (cx, cy, cz), (hx, hy, hz) = center, half
    x0, x1, y0, y1, z0, z1 = cx - hx, cx + hx, cy - hy, cy + hy, cz - hz, cz + hz
    return {
        "x": [(x0, y0, z0), (x0, y1, z0), (x0, y1, z1), (x0, y0, z1)],
        "y": [(x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1)],
        "z": [(x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)],
    }


def node_colors(node):
    other, kind = node.get("other"), node.get("tqec")
    if isinstance(other, dict) and other.get("type") in ("input", "output"):
        return {a: PORT for a in "xyz"}
    if other in SPECIAL:
        return {a: SPECIAL[other] for a in "xyz"}
    if kind:
        return {a: BASIS_COLOR[kind[i]] for i, a in enumerate("xyz")}
    return None


def draw_pipe_diagram(ax, diagram, cube=0.4):
    nodes = {tuple(n["position"]): n for n in diagram["nodes"]}
    items = []   # (depth key, polygon, colour)
    half = cube / 2
    for pos, node in nodes.items():
        colors = node_colors(node)
        if colors is None:
            continue
        for axis, face in box_faces(pos, (half, half, half)).items():
            items.append(((-(pos[0] + pos[1]), pos[2]), face, colors[axis]))
    def basis_colors(kind):
        return {a: BASIS_COLOR[kind[i]] for i, a in enumerate("xyz")}

    def add_box(center, dims, colors, lift=0.0):
        for face_axis, face in box_faces(center, dims).items():
            items.append(((-(center[0] + center[1]), center[2] + lift), face, colors[face_axis]))

    for a, b in diagram["pipes"]:
        a, b = tuple(a), tuple(b)
        ta = nodes[a].get("tqec") if a in nodes else None
        tb = nodes[b].get("tqec") if b in nodes else None
        if not (ta or tb):
            continue
        axis = next(i for i in range(3) if a[i] != b[i])
        perpendicular = [k for i, k in enumerate("xyz") if i != axis]
        mid = tuple((a[i] + b[i]) / 2 for i in range(3))
        length = (1 - cube) / 2
        if ta and tb and any(ta["xyz".index(k)] != tb["xyz".index(k)] for k in perpendicular):
            # Hadamard on the pipe (TopoLS rule): two half pipes and a yellow collar.
            for end, kind in ((a, ta), (b, tb)):
                # each half spans from the cube face of `end` to the pipe midpoint
                face = end[axis] + (half if mid[axis] > end[axis] else -half)
                center = tuple((face + mid[axis]) / 2 if i == axis else mid[i] for i in range(3))
                dims = [half] * 3
                dims[axis] = length / 2
                add_box(center, dims, basis_colors(kind))
            band = [half * 1.08] * 3
            band[axis] = 0.04
            add_box(mid, band, {k: COLLAR for k in "xyz"}, lift=1e-3)
        else:
            dims = [half] * 3
            dims[axis] = length
            add_box(mid, dims, basis_colors(ta or tb))
    for _key, face, color in sorted(items, key=lambda t: t[0]):
        pts = [iso(*p) for p in face]
        ax.fill([p[0] for p in pts], [p[1] for p in pts], fc=color, ec=INK, lw=0.3)
    ax.autoscale_view()


def draw_surface_code(ax, sc):
    """Stabilizer plaquettes of one measurement round, coloured by type."""
    import math
    pos = {int(q): tuple(c) for q, c in sc["qubits"].items()}
    for pl in sc["plaquettes"]:
        ax0, ay0 = pos[pl["ancilla"]]
        corners = sorted((pos[d] for d in pl["data"]),
                         key=lambda c: math.atan2(c[1] - ay0, c[0] - ax0))
        if len(corners) == 2:                     # boundary stabilizer: half disc
            corners = corners + [(ax0, ay0)]
        ax.fill([c[0] for c in corners], [-c[1] for c in corners],
                fc=BASIS_COLOR[pl["type"]], ec=INK, lw=0.2)
    ax.scatter([pos[d][0] for d in sc["data"]], [-pos[d][1] for d in sc["data"]],
               s=0.4, c=INK, lw=0, zorder=3)
    ax.autoscale_view()


# Panel backgrounds: one very light purple, so every mark keeps its contrast.
PANEL_FILL = dict.fromkeys("abcd", "#f7f3fc")
PANEL_EDGE = "#c9b9e4"
ARROW = "#52514e"
# The panel this paper is about: strong border, shadow and bold title.
FOCUS = "b"
FOCUS_EDGE = "#6b4fbb"
FOCUS_SHADOW = "#d6cdea"


def build_figure(g, out: Path, topols=None):
    from matplotlib.patches import FancyBboxPatch

    plt.rcParams.update({
        "font.family": "serif",
        "font.serif": ["Times New Roman", "Nimbus Roman", "STIXGeneral", "DejaVu Serif"],
        "mathtext.fontset": "stix", "font.size": 7.5,
        "pdf.fonttype": 42, "ps.fonttype": 42,
    })
    titles = {"a": "(a) Circuit, 12 gates", "b": "(b) After PandoraZX",
              "c": "(c) TopoLS pipe diagram", "d": "(d) tqec surface code"}
    gap_x, gap_y = 0.08, 0.08
    bw = (1 - gap_x) / 2
    if topols is None:
        # Two panels until the TopoLS/tqec output is available.
        fig_h = 1.45
        boxes = {"a": (0.0, 0.0, bw, 1.0), "b": (bw + gap_x, 0.0, bw, 1.0)}
        arrows = [((bw + 0.008, 0.5), (bw + gap_x - 0.008, 0.5))]
    else:
        # U-shaped flow: (a) top left -> (b) top right -> (c) bottom right -> (d) bottom left
        fig_h = 2.95
        bh = (1 - gap_y) / 2
        top = bh + gap_y
        boxes = {"a": (0.0, top, bw, bh), "b": (bw + gap_x, top, bw, bh),
                 "c": (bw + gap_x, 0.0, bw, bh), "d": (0.0, 0.0, bw, bh)}
        right_mid = bw + gap_x + bw / 2
        arrows = [((bw + 0.008, top + bh / 2), (bw + gap_x - 0.008, top + bh / 2)),   # a -> b
                  ((right_mid, top - 0.01), (right_mid, bh + 0.01)),                   # b -> c
                  ((bw + gap_x - 0.008, bh / 2), (bw + 0.008, bh / 2))]               # c -> d
    fig = plt.figure(figsize=(COLUMN_WIDTH_IN, fig_h))
    title_h = 0.105 / fig_h          # room for the title inside the box (inches -> figure units)
    pad_x, pad_y = 0.02, 0.05 / fig_h
    axes = {}
    box_style = dict(boxstyle="round,pad=0,rounding_size=0.025",
                     mutation_aspect=COLUMN_WIDTH_IN / fig_h, transform=fig.transFigure)
    for k, (x0, y0, w, h) in boxes.items():
        focus = k == FOCUS
        if focus:
            dx, dy = 0.012, 0.012 * COLUMN_WIDTH_IN / fig_h
            fig.patches.append(FancyBboxPatch((x0 + dx, y0 - dy), w, h, fc=FOCUS_SHADOW,
                                              ec="none", zorder=-2, **box_style))
        fig.patches.append(FancyBboxPatch(
            (x0, y0), w, h, fc=PANEL_FILL[k], ec=FOCUS_EDGE if focus else PANEL_EDGE,
            lw=1.6 if focus else 0.5, zorder=-1, **box_style))
        fig.text(x0 + w / 2, y0 + h - pad_y * 0.8, titles[k], ha="center", va="top",
                 fontsize=7.5, fontweight="bold" if focus else "normal")
        ax = fig.add_axes((x0 + pad_x, y0 + pad_y, w - 2 * pad_x, h - 2 * pad_y - title_h))
        ax.set_aspect("equal")
        ax.set_facecolor("none")
        ax.axis("off")
        axes[k] = ax
    draw_circuit(axes["a"])
    draw_zx(axes["b"], g)
    if topols is not None:
        draw_pipe_diagram(axes["c"], topols["pipe_diagram"])
        draw_surface_code(axes["d"], topols["surface_code"])
    arrow = dict(arrowstyle="-|>,head_length=5,head_width=2.8", color=ARROW, lw=1.4,
                 shrinkA=0, shrinkB=0)
    for start, end in arrows:
        fig.patches.append(FancyArrowPatch(start, end, transform=fig.transFigure, **arrow))
    fig.savefig(out, bbox_inches="tight", pad_inches=0.01)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=HERE / "zx_benchmark_plots")
    parser.add_argument("--database", default=None,
                        help="scratch PostgreSQL database for the PandoraZX run")
    parser.add_argument("--topols", type=Path, default=None,
                        help="JSON written by dac_fig1_topols.py (panels c and d)")
    args = parser.parse_args()

    circuit = example_circuit()
    g = pandorazx_graph(args.database)
    assert zx.compare_tensors(circuit, g, preserve_scalar=False)
    spiders = sum(1 for v in g.vertices() if g.type(v) != zx.VertexType.BOUNDARY)
    print(f"PandoraZX diagram: {spiders} spiders, {g.num_edges()} edges")
    args.out.mkdir(parents=True, exist_ok=True)
    topols = json.loads(args.topols.read_text()) if args.topols else None
    build_figure(g, args.out / "dac_pipeline.pdf", topols)
    print(f"Wrote {args.out / 'dac_pipeline.pdf'}")


if __name__ == "__main__":
    main()
