"""Figures and summary table for the PandoraZX DAC paper.

Usage:
    python benchmarking/dac_figures.py --csv <results.csv> --out <paper>/figures

Reads the CSV written by zx_benchmarks.ipynb and writes
    dac_runtime.pdf   full_reduce runtime per family (1 x 4 panels)
    dac_quality.pdf   spider and edge change per family (2 x 4 bar panels)
    dac_basic.pdf     basic_simp runtime per family (2 x 2 panels, one column)
and prints the numbers used in the paper text and in Table I.

All measured points are plotted; the sweep stopping rule is applied by the
notebook while measuring. --limit only draws the dashed time-limit line and
should match BACKEND_TIME_LIMIT_S of the run that produced the CSV
(90 s for the thesis CSV, 240 s for the newer runs).
"""

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.ticker import (FixedLocator, FuncFormatter, LogLocator, MultipleLocator,
                               NullFormatter, NullLocator)

FAMILIES = [
    ("Adder_before", "Binary adder"),
    ("gf2^En Mult", r"GF$(2^n)$ multiplier"),
    ("VBE Adder", "VBE adder"),
    ("IQP", "IQP"),
]
BACKENDS = ["pandora", "pyzx", "quizx"]
LABEL = {"pandora": "PandoraZX", "pyzx": "PyZX", "quizx": "QuiZX"}
# PandoraZX in the dark purple that highlights it in Fig. 1; PyZX light red and
# QuiZX light green. The red and green differ in lightness, so they stay apart
# under red-green colour blindness (OKLab dE 10); markers add a colour-free cue.
# STROKE is a deeper shade of each hue for marker and bar outlines.
COLOR = {"pandora": "#6b4fbb", "pyzx": "#e57373", "quizx": "#8fd18f"}
STROKE = {"pandora": "#6b4fbb", "pyzx": "#c94f4f", "quizx": "#4f9a4f"}
MARKER = {"pandora": "o", "pyzx": "D", "quizx": "s"}
INK, MUTED, GRID = "#0b0b0b", "#52514e", "#e4e3df"

TEXT_WIDTH_IN = 7.16  # IEEEtran two-column \textwidth
COLUMN_WIDTH_IN = 3.5  # IEEEtran \columnwidth


def style():
    plt.rcParams.update({
        "font.family": "serif",
        "font.serif": ["Times New Roman", "Nimbus Roman", "STIXGeneral", "DejaVu Serif"],
        "mathtext.fontset": "stix",
        "font.size": 7.5,
        "axes.titlesize": 8,
        "axes.labelsize": 7.5,
        "xtick.labelsize": 6.5,
        "ytick.labelsize": 6.5,
        "legend.fontsize": 7.5,
        "axes.edgecolor": MUTED,
        "axes.labelcolor": INK,
        "xtick.color": MUTED,
        "ytick.color": MUTED,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.linewidth": 0.6,
        "xtick.major.width": 0.6,
        "ytick.major.width": 0.6,
        "lines.linewidth": 1.2,
        "lines.markersize": 3.2,
        "pdf.fonttype": 42,  # no Type 3 fonts (IEEE PDF eXpress)
        "ps.fonttype": 42,
    })


def load(csv_path: Path, mode: str = "full") -> pd.DataFrame:
    df = pd.read_csv(csv_path)
    df = df[(df["mode"] == mode) & df["family"].isin([f for f, _ in FAMILIES])]
    for col in ["gates", "simplify_s", "edges_before", "edges_after",
                "spiders_before", "spiders_after"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(subset=["gates", "simplify_s"])
    df = (df.groupby(["family", "circuit", "gates", "backend"], as_index=False)
            .agg(time=("simplify_s", "mean"),
                 sb=("spiders_before", "mean"), sa=("spiders_after", "mean"),
                 eb=("edges_before", "mean"), ea=("edges_after", "mean")))
    df["spider_pct"] = 100 * (df.sa - df.sb) / df.sb
    df["edge_ratio"] = df.ea / df.eb
    return df


def gate_axis(ax):
    ax.set_xscale("log")
    ax.xaxis.set_major_locator(LogLocator(base=10))
    ax.xaxis.set_minor_formatter(NullFormatter())
    ax.grid(True, which="major", color=GRID, linewidth=0.5)
    ax.set_axisbelow(True)


def series(ax, data, y):
    for b in BACKENDS:
        d = data[data.backend == b].sort_values("gates")
        if not d.empty:
            ax.plot(d.gates, d[y], color=COLOR[b], marker=MARKER[b],
                    label=LABEL[b], markeredgecolor=STROKE[b], markeredgewidth=0.5)


def legend(fig, axes):
    handles, labels = axes.flat[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=len(handles), frameon=False,
               bbox_to_anchor=(0.5, 1.02), handlelength=2.2, columnspacing=2.0)


def runtime_figure(df, limit, out: Path):
    fig, axes = plt.subplots(1, 4, figsize=(TEXT_WIDTH_IN, 1.75))
    for ax, (fam, title) in zip(axes, FAMILIES):
        data = df[df.family == fam]
        ax.axhline(limit, color=MUTED, linestyle=(0, (3, 2)), linewidth=0.7)
        series(ax, data, "time")
        gate_axis(ax)
        ax.set_yscale("log")
        ax.yaxis.set_major_locator(LogLocator(base=100, numticks=12))
        ax.yaxis.set_minor_locator(NullLocator())
        ax.set_title(title)
        ax.set_xlabel("Gates")
    axes[0].set_ylabel("Simplification time (s)")
    lo = df.time[df.time > 0].min()
    hi = df.time.max()
    for ax in axes:
        ax.set_ylim(lo / 2, hi * 3)
    axes[0].text(axes[0].get_xlim()[0] * 1.3, limit * 1.25, f"{limit:g} s limit",
                 color=MUTED, fontsize=6.5, va="bottom")
    legend(fig, axes)
    fig.tight_layout(rect=(0, 0, 1, 0.9), w_pad=0.8)
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)


def basic_figure(df, limit, out: Path):
    fig, axes = plt.subplots(2, 2, figsize=(COLUMN_WIDTH_IN, 2.9))
    lo = df.time[df.time > 0].min()
    hi = df.time.max()
    for ax, (fam, title) in zip(axes.flat, FAMILIES):
        ax.axhline(limit, color=MUTED, linestyle=(0, (3, 2)), linewidth=0.7)
        series(ax, df[df.family == fam], "time")
        gate_axis(ax)
        ax.set_yscale("log")
        ax.set_ylim(lo / 2, hi * 3)
        ax.yaxis.set_major_locator(LogLocator(base=100, numticks=12))
        ax.yaxis.set_minor_locator(NullLocator())
        ax.set_title(title)
    for ax in axes[1]:
        ax.set_xlabel("Gates")
    for ax in axes[:, 0]:
        ax.set_ylabel("basic_simp time (s)")
    legend(fig, axes)
    fig.tight_layout(rect=(0, 0, 1, 0.93), w_pad=0.6, h_pad=0.5)
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)


def pct_from_ratio(r, _pos=None):
    p = 100 * (r - 1)
    return "0" if abs(p) < 1e-9 else f"{p:+.0f}"


def gates_label(g):
    return f"{g:.0f}" if g < 1000 else (f"{g / 1000:.1f}k" if g < 10000 else f"{g / 1000:.0f}k")


def quality_sizes(data, n=6):
    """Up to n log-spaced sizes completed by PandoraZX and QuiZX, incl. both ends."""
    sizes = sorted(set(data[data.backend == "pandora"].gates) & set(data[data.backend == "quizx"].gates))
    idx = sorted(set(np.round(np.linspace(0, len(sizes) - 1, min(n, len(sizes)))).astype(int)))
    return [sizes[i] for i in idx]


def quality_figure(df, out: Path):
    """Share of spiders remaining (top) and edge change (bottom) after full_reduce, as bars."""
    from matplotlib.patches import Patch

    fig, axes = plt.subplots(2, 4, figsize=(TEXT_WIDTH_IN, 3.0))
    # Ticks at round percentages, placed on a log scale of edges_after / edges_before.
    ratio_ticks = [1 + p / 100 for p in (-80, -50, 0, 100, 500, 1000, 5000)]
    rmin = df.edge_ratio.min() / 1.3
    rmax = df.edge_ratio.max() * 1.3
    width = 0.27
    for col, (fam, title) in enumerate(FAMILIES):
        data = df[df.family == fam]
        sizes = quality_sizes(data)
        top, bottom = axes[0, col], axes[1, col]
        for i, b in enumerate(BACKENDS):
            d = data[data.backend == b].set_index("gates")
            xs = [j + (i - 1) * width for j, g in enumerate(sizes) if g in d.index]
            gs = [g for g in sizes if g in d.index]
            top.bar(xs, [100 + d.spider_pct[g] for g in gs], width=width, color=COLOR[b],
                    edgecolor=STROKE[b], linewidth=0.4)
            ratios = [d.edge_ratio[g] for g in gs]
            bottom.bar(xs, [r - 1 for r in ratios], bottom=1, width=width, color=COLOR[b],
                       edgecolor=STROKE[b], linewidth=0.4)
        for ax in (top, bottom):
            ax.set_xticks(range(len(sizes)), [gates_label(g) for g in sizes], fontsize=6)
            ax.set_xlim(-0.6, len(sizes) - 0.4)
            ax.grid(True, axis="y", color=GRID, linewidth=0.5)
            ax.set_axisbelow(True)
            ax.tick_params(axis="x", length=0)
        top.axhline(0, color=MUTED, linewidth=0.7)
        top.set_title(title)
        top.set_ylim(0, 50)
        top.yaxis.set_major_locator(MultipleLocator(10))

        bottom.axhline(1.0, color=MUTED, linewidth=0.7)
        bottom.set_yscale("log")
        bottom.set_ylim(rmin, rmax)
        bottom.yaxis.set_major_locator(FixedLocator(ratio_ticks))
        bottom.yaxis.set_major_formatter(FuncFormatter(pct_from_ratio))
        bottom.yaxis.set_minor_locator(NullLocator())
        bottom.set_xlabel("Gates")
    axes[0, 0].set_ylabel("Spiders remaining (%)")
    axes[1, 0].set_ylabel("Edge change (%)")
    handles = [Patch(facecolor=COLOR[b], edgecolor=STROKE[b], linewidth=0.4, label=LABEL[b])
               for b in BACKENDS]
    fig.legend(handles=handles, loc="upper center", ncol=3, frameon=False,
               bbox_to_anchor=(0.5, 1.02), handlelength=1.2, columnspacing=2.0)
    fig.tight_layout(rect=(0, 0, 1, 0.94), w_pad=0.8, h_pad=0.6)
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)


def report(df):
    """Print the numbers quoted in the paper."""
    pd.set_option("display.width", 200)
    for fam, title in FAMILIES:
        d = df[df.family == fam]
        t = d.pivot_table(index="gates", columns="backend", values="time")
        print(f"\n== {title}: time (s)\n{t.round(2).to_string()}")
        both = t[["pandora", "quizx"]].dropna()
        if not both.empty:
            g = both.index.max()
            row = d[d.gates == g].set_index("backend")
            circuit = row.circuit.iloc[0]
            print(f"Table I row (largest circuit done by PandoraZX and QuiZX): {circuit}, {g:,} gates")
            for b in ["pandora", "quizx"]:
                print(f"  {LABEL[b]:9s} time {row.time[b]:9.2f} s  "
                      f"spiders {row.spider_pct[b]:+6.1f}%  edges {100 * (row.edge_ratio[b] - 1):+8.1f}%")
        py = t[["pandora", "pyzx"]].dropna()
        if not py.empty:
            g = py.index.max()
            print(f"  vs PyZX at {g:,} gates: PyZX {py.loc[g, 'pyzx']:.1f} s, "
                  f"PandoraZX {py.loc[g, 'pandora']:.1f} s ({py.loc[g, 'pyzx'] / py.loc[g, 'pandora']:.1f}x)")
            faster = py[py.pandora < py.pyzx]
            if not faster.empty:
                print(f"  PandoraZX faster than PyZX from {faster.index.min():,} gates")
        q = t[["pandora", "quizx"]].dropna()
        faster = q[q.pandora < q.quizx]
        if not faster.empty:
            print(f"  PandoraZX faster than QuiZX from {faster.index.min():,} gates")


def main():
    here = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--csv", type=Path, default=here / "zx_benchmark_results.csv")
    parser.add_argument("--out", type=Path, default=here / "zx_benchmark_plots")
    parser.add_argument("--limit", type=float, default=240.0,
                        help="time limit of the run, in seconds (dashed line only)")
    args = parser.parse_args()

    style()
    df = load(args.csv)
    args.out.mkdir(parents=True, exist_ok=True)
    runtime_figure(df, args.limit, args.out / "dac_runtime.pdf")
    quality_figure(df, args.out / "dac_quality.pdf")
    basic_figure(load(args.csv, "basic"), args.limit, args.out / "dac_basic.pdf")
    report(df)
    print(f"\nWrote dac_runtime.pdf, dac_quality.pdf and dac_basic.pdf to {args.out}")


if __name__ == "__main__":
    main()
