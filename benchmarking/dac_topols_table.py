"""TopoLS comparison, step 3: summary CSV, LaTeX table and numbers for the paper.

    python benchmarking/dac_topols_table.py <work dir> [--out benchmarking/dac_topols_results.csv]

Reads prepare.json and topols_r*.json from the work dir written by
dac_topols_prepare.py and dac_topols_run.py. Volumes are averaged over the
TopoLS seeds that were run. The inputs and TopoLS results of the paper
(seeds 0-2) are in benchmarking/dac_topols_inputs, so the paper's CSV and table
can be reproduced with

    python benchmarking/dac_topols_table.py benchmarking/dac_topols_inputs
"""

import csv
import json
import sys
from pathlib import Path

import numpy as np

work = Path(sys.argv[1])
out = Path(sys.argv[sys.argv.index("--out") + 1]) if "--out" in sys.argv else \
    Path(__file__).with_name("dac_topols_results.csv")
prep = json.loads((work / "prepare.json").read_text())
runs = {p.stem.removeprefix("topols_r"): json.loads(p.read_text()) for p in sorted(work.glob("topols_r*.json"))}
VERSIONS = ("orig", "pyzx", "pandora")

rows = []
for name, info in prep.items():
    row = {"circuit": name, "qubits": info["qubits"], "seeds": len(runs)}
    for v in VERSIONS:
        vols = [r[f"{name}__{v}"]["volume"] for r in runs.values() if "volume" in r.get(f"{name}__{v}", {})]
        row[f"volume_{v}"] = float(np.mean(vols))
        row[f"volume_{v}_min"], row[f"volume_{v}_max"] = min(vols), max(vols)
        row[f"cnot_{v}"] = info[v]["twoq"]
        row[f"t_{v}"] = info[v]["t"]
    row["spiders_pyzx"], row["edges_pyzx"] = info["diagram"]["pyzx"]
    row["spiders_pandora"], row["edges_pandora"] = info["diagram"]["pandora"]
    row["delta_pct"] = 100 * (row["volume_pandora"] / row["volume_pyzx"] - 1)
    rows.append(row)
with out.open("w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)


def tex_name(n):
    if n.startswith("gf2^E"):
        return f"GF$(2^{{{n.removeprefix('gf2^E').removesuffix('_mult')}}})$"
    return n.replace("_", r"\_")


lines = [r"\begin{tabular}{@{}lrrrrrrrrrrr@{}}", r"\toprule",
         r" & & \multicolumn{2}{c}{Spiders} & \multicolumn{2}{c}{Edges} & \multicolumn{2}{c}{CNOTs}"
         r" & \multicolumn{3}{c}{TopoLS volume} & \\",
         r"\cmidrule(lr){3-4}\cmidrule(lr){5-6}\cmidrule(lr){7-8}\cmidrule(lr){9-11}",
         r"Circuit & $n$ & PyZX & PZX & PyZX & PZX & PyZX & PZX & Orig. & PyZX & PZX & $\Delta$ \\", r"\midrule"]
for r in rows:
    vols = {v: r[f"volume_{v}"] for v in VERSIONS}
    best = min(vols.values())
    cell = {v: (rf"\textbf{{{vols[v]:,.0f}}}" if vols[v] == best else f"{vols[v]:,.0f}").replace(",", "{,}")
            for v in VERSIONS}
    lines.append(f"{tex_name(r['circuit'])} & {r['qubits']} & {r['spiders_pyzx']} & {r['spiders_pandora']} & "
                 f"{r['edges_pyzx']} & {r['edges_pandora']} & {r['cnot_pyzx']} & {r['cnot_pandora']} & "
                 f"{cell['orig']} & {cell['pyzx']} & {cell['pandora']} & ${r['delta_pct']:+.0f}\\%$ \\\\")
lines += [r"\bottomrule", r"\end{tabular}"]
print("\n".join(lines))

d = np.array([r["delta_pct"] for r in rows])
wins = [r["circuit"] for r in rows if r["delta_pct"] < 0]
losses = [r["circuit"] for r in rows if r["delta_pct"] > 0]
beats_orig = [r["circuit"] for r in rows if r["volume_pandora"] < r["volume_orig"]]
print(f"\nseeds: {sorted(runs)}")
print(f"PandoraZX < PyZX on {len(wins)}/{len(rows)} (by {-d[d < 0].max():.0f}-{-d[d < 0].min():.0f}%): {wins}")
print(f"PandoraZX > PyZX on {len(losses)}: {losses} (by {d[d > 0].min():.0f}-{d[d > 0].max():.0f}%)")
print(f"mean change vs PyZX: {d.mean():+.1f}%; median {np.median(d):+.1f}%")
print(f"PandoraZX < original on {len(beats_orig)}/{len(rows)}")
print(f"PZX fewer CNOTs than PyZX on {sum(r['cnot_pandora'] < r['cnot_pyzx'] for r in rows)}/{len(rows)}; "
      f"same T count on {sum(r['t_pandora'] == r['t_pyzx'] for r in rows)}/{len(rows)}")
for r in rows:
    spread = max((r[f'volume_{v}_max'] - r[f'volume_{v}_min']) / r[f'volume_{v}'] for v in VERSIONS)
    if spread > 0:
        print(f"  {r['circuit']}: volume spread across seeds up to {100 * spread:.0f}%")
