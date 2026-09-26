"""Generate a print-readable pipeline schematic for Figure 1."""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch


out = Path(__file__).resolve().parent / "figures" / "pipeline_paper.png"
fig, ax = plt.subplots(figsize=(9.0, 4.4), dpi=240)
ax.set_xlim(0, 9)
ax.set_ylim(0, 4.4)
ax.axis("off")


def box(x, y, title, detail, color):
    patch = FancyBboxPatch((x, y), 2.45, 1.05, boxstyle="round,pad=0.10,rounding_size=0.08",
                           linewidth=1.8, edgecolor=color, facecolor="white")
    ax.add_patch(patch)
    ax.text(x + 1.225, y + 0.66, title, ha="center", va="center", fontsize=13,
            weight="bold", color=color)
    ax.text(x + 1.225, y + 0.29, detail, ha="center", va="center", fontsize=9.8,
            color="#2E3C43")


def arrow(start, end, label=None):
    ax.add_patch(FancyArrowPatch(start, end, arrowstyle="-|>", mutation_scale=16,
                                 linewidth=1.7, color="#455A64"))
    if label:
        mx = (start[0] + end[0]) / 2
        my = (start[1] + end[1]) / 2
        ax.text(mx, my + 0.13, label, ha="center", va="bottom", fontsize=8.5,
                color="#455A64")


xs = (0.15, 3.27, 6.39)
box(xs[0], 2.75, "MaleCNS v1.0", "annotations and edge weights", "#00695C")
box(xs[1], 2.75, "Graph extraction", "selectors, paths and sparse IR", "#00695C")
box(xs[2], 2.75, "Memory compiler", "fixed-point words and hashes", "#00695C")
arrow((2.72, 3.28), (3.20, 3.28))
arrow((5.84, 3.28), (6.32, 3.28))
box(xs[0], 0.45, "Float CPU", "model reference", "#1E64A4")
box(xs[1], 0.45, "Fixed CPU", "quantization reference", "#1E64A4")
box(xs[2], 0.45, "FPGA engine", "events and counters", "#B4232C")
arrow((2.72, 0.98), (3.20, 0.98), "quantize")
arrow((5.84, 0.98), (6.32, 0.98), "verify")
arrow((4.50, 2.67), (1.37, 1.57))
arrow((7.61, 2.67), (4.50, 1.57))
arrow((7.61, 2.67), (7.61, 1.57))
fig.tight_layout(pad=0.15)
fig.savefig(out, dpi=240, facecolor="white")
print(out)
