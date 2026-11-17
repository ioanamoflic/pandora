"""Compact figure of the ZX rewrite rules used by PandoraZX (DAC paper).

    python benchmarking/dac_fig_rules.py --out <paper>/figures

(a) spider fusion, (b) identity removal (graph-like form), (c) local
complementation, (d) pivoting. Same visual conventions as Fig. 1: green Z
spiders, blue dashed Hadamard edges; short stubs stand for the connections to
the rest of the diagram.
"""

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle

from dac_fig1 import COLUMN_WIDTH_IN, HADAMARD_EDGE, INK, MUTED, Z_FILL

R = 0.12          # spider radius (data units)
XSPAN = 3.9       # data units per panel width: one common scale for all panels
STUB = 0.2        # length of the stubs to the rest of the diagram
LABEL = 6.5       # phase label font size


def edge(ax, p, q, hadamard=False):
    style = dict(color=HADAMARD_EDGE, lw=0.9, ls=(0, (2.5, 1.5))) if hadamard else dict(color=INK, lw=0.8)
    ax.plot([p[0], q[0]], [p[1], q[1]], zorder=1, **style)


def stub(ax, p, dx, dy, hadamard=False):
    edge(ax, p, (p[0] + dx * STUB, p[1] + dy * STUB), hadamard)


def spider(ax, p, label="", where="above"):
    ax.add_patch(Circle(p, R, fc=Z_FILL, ec=INK, lw=0.7, zorder=3))
    if label:
        dx, dy, ha, va = {"above": (0, R + 0.04, "center", "bottom"),
                          "below": (0, -R - 0.04, "center", "top"),
                          "left": (-R - 0.04, 0, "right", "center"),
                          "right": (R + 0.04, 0, "left", "center")}[where]
        ax.text(p[0] + dx, p[1] + dy, label, ha=ha, va=va, fontsize=LABEL, zorder=4)


def equals(ax, x, y=0.0):
    ax.text(x, y, "$=$", ha="center", va="center", fontsize=9, color=MUTED)


def spider_fusion(ax):
    a, b = (0.0, 0.0), (0.55, 0.0)
    edge(ax, a, b)
    for dy in (0.7, -0.7):
        stub(ax, a, -0.7, dy)
        stub(ax, b, 0.7, dy)
    spider(ax, a, r"$\alpha$")
    spider(ax, b, r"$\beta$")
    equals(ax, 1.1)
    c = (1.75, 0.0)
    for dx in (-0.7, 0.7):
        for dy in (0.7, -0.7):
            stub(ax, c, dx, dy)
    spider(ax, c, r"$\alpha{+}\beta$")


def identity_removal(ax):
    a, m, b = (0.0, 0.0), (0.45, 0.0), (0.9, 0.0)
    edge(ax, a, m, hadamard=True)
    edge(ax, m, b, hadamard=True)
    for p, dx in ((a, -1), (b, 1)):
        stub(ax, p, dx * 0.7, 0.7)
        stub(ax, p, dx * 0.7, -0.7)
    spider(ax, a, r"$\alpha$")
    spider(ax, m)
    spider(ax, b, r"$\beta$")
    equals(ax, 1.35)
    c, d = (1.8, 0.0), (2.4, 0.0)
    edge(ax, c, d)
    for p, dx in ((c, -1), (d, 1)):
        stub(ax, p, dx * 0.7, 0.7)
        stub(ax, p, dx * 0.7, -0.7)
    spider(ax, c, r"$\alpha$")
    spider(ax, d, r"$\beta$")


def local_complementation(ax):
    centre = (0.45, 0.05)
    nbrs = [(0.0, 0.45), (0.9, 0.45), (0.45, -0.5)]
    out = [(-1, 0.4), (1, 0.4), (0, -1)]
    for n, (dx, dy) in zip(nbrs, out):
        edge(ax, centre, n, hadamard=True)
        stub(ax, n, dx, dy)
    spider(ax, centre, r"$\pm\frac{\pi}{2}$", "right")
    for n, lab, where in zip(nbrs, (r"$\alpha_1$", r"$\alpha_2$", r"$\alpha_3$"), ("above", "above", "left")):
        spider(ax, n, lab, where)
    equals(ax, 1.3)
    shift = 1.75
    tri = [(x + shift, y) for x, y in nbrs]
    for i in range(3):
        edge(ax, tri[i], tri[(i + 1) % 3], hadamard=True)
    for n, (dx, dy) in zip(tri, out):
        stub(ax, n, dx, dy)
    for n, lab, where in zip(tri, (r"$\alpha_1{\mp}\frac{\pi}{2}$", r"$\alpha_2{\mp}\frac{\pi}{2}$",
                                   r"$\alpha_3{\mp}\frac{\pi}{2}$"), ("above", "above", "left")):
        spider(ax, n, lab, where)


def pivoting(ax):
    a, u, v, c, b = (0.0, 0.0), (0.42, 0.0), (0.84, 0.0), (1.26, 0.0), (0.63, 0.48)
    for p, q in ((a, u), (u, v), (v, c), (u, b), (v, b)):
        edge(ax, p, q, hadamard=True)
    stub(ax, a, -1, 0)
    stub(ax, c, 1, 0)
    stub(ax, b, -0.6, 0.8)
    spider(ax, u, r"$j\pi$", "below")
    spider(ax, v, r"$k\pi$", "below")
    spider(ax, a, r"$\alpha$", "below")
    spider(ax, c, r"$\gamma$", "below")
    spider(ax, b, r"$\beta$", "right")
    equals(ax, 1.62)
    shift = 1.98
    a2, c2, b2 = (shift, 0.0), (shift + 0.84, 0.0), (shift + 0.42, 0.48)
    for p, q in ((a2, c2), (a2, b2), (b2, c2)):
        edge(ax, p, q, hadamard=True)
    stub(ax, a2, -1, 0)
    stub(ax, c2, 1, 0)
    stub(ax, b2, -0.6, 0.8)
    spider(ax, a2, r"$\alpha{+}k\pi$", "below")
    spider(ax, c2, r"$\gamma{+}j\pi$", "below")
    spider(ax, b2, r"$\beta{+}(j{+}k{+}1)\pi$", "right")


def build(out: Path):
    plt.rcParams.update({
        "font.family": "serif",
        "font.serif": ["Times New Roman", "Nimbus Roman", "STIXGeneral", "DejaVu Serif"],
        "mathtext.fontset": "stix", "font.size": 7.5,
        "pdf.fonttype": 42, "ps.fonttype": 42,
    })
    # Row heights in inches, fitted to the content at the common scale.
    title_h, gap, top_h, bottom_h = 0.13, 0.05, 0.40, 0.84
    fig_h = title_h + top_h + gap + title_h + bottom_h
    fig = plt.figure(figsize=(COLUMN_WIDTH_IN, fig_h))
    top_y = (bottom_h + title_h + gap) / fig_h
    panels = [("(a) Spider fusion", spider_fusion, (0.0, top_y, 0.47, top_h / fig_h)),
              ("(b) Identity removal", identity_removal, (0.53, top_y, 0.47, top_h / fig_h)),
              ("(c) Local complementation", local_complementation, (0.0, 0.0, 0.47, bottom_h / fig_h)),
              ("(d) Pivoting", pivoting, (0.53, 0.0, 0.47, bottom_h / fig_h))]
    for title, draw, rect in panels:
        ax = fig.add_axes(rect)
        ax.set_aspect("equal")
        ax.axis("off")
        draw(ax)
        ax.autoscale_view()
        x0, y0, w, h = rect
        (lx, hx), (ly, hy) = ax.get_xlim(), ax.get_ylim()
        cx, cy = (lx + hx) / 2, (ly + hy) / 2
        yspan = XSPAN * (h * fig.get_figheight()) / (w * fig.get_figwidth())
        ax.set_xlim(cx - XSPAN / 2, cx + XSPAN / 2)
        ax.set_ylim(cy - yspan / 2, cy + yspan / 2)
        fig.text(x0 + w / 2, y0 + h + 0.015 / fig_h, title, ha="center", va="bottom", fontsize=7.5)
    fig.savefig(out, bbox_inches="tight", pad_inches=0.01)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=Path(__file__).with_name("zx_benchmark_plots"))
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    build(args.out / "dac_rules.pdf")
    print(f"Wrote {args.out / 'dac_rules.pdf'}")


if __name__ == "__main__":
    main()
