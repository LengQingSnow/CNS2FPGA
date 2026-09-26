"""Create a compact scientific workflow figure for the manuscript draft."""

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

HERE = Path(__file__).resolve().parent


def box(ax, x, y, title, detail, color):
    patch = FancyBboxPatch((x, y), 2.15, 0.9, boxstyle="round,pad=0.08,rounding_size=0.08",
                           linewidth=1.3, edgecolor=color, facecolor="white")
    ax.add_patch(patch)
    ax.text(x + 1.075, y + 0.57, title, ha="center", va="center", fontsize=10, fontweight="bold", color=color)
    ax.text(x + 1.075, y + 0.25, detail, ha="center", va="center", fontsize=7.5, color="#263238")


def arrow(ax, a, b):
    ax.add_patch(FancyArrowPatch(a, b, arrowstyle="-|>", mutation_scale=14,
                                 linewidth=1.5, color="#455A64"))


def main():
    output = HERE / "figures"
    output.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(11.5, 4.1))
    ax.set_xlim(0, 11.5)
    ax.set_ylim(0, 4.1)
    ax.axis("off")
    box(ax, 0.2, 2.55, "MaleCNS v1.0", "annotations + weighted edges", "#00695C")
    box(ax, 3.1, 2.55, "Circuit extractor", "selectors, paths, CSR IR", "#00695C")
    box(ax, 6.0, 2.55, "Connectome compiler", "safe_wf24 + .mem files", "#00695C")
    box(ax, 8.9, 2.55, "FPGA engine", "time-multiplexed neurons", "#00695C")
    for x in (2.42, 5.32, 8.22):
        arrow(ax, (x, 3.0), (x + 0.55, 3.0))
    box(ax, 3.1, 0.7, "Float CPU", "scientific reference", "#1565C0")
    box(ax, 6.0, 0.7, "Fixed CPU", "quantization reference", "#1565C0")
    box(ax, 8.9, 0.7, "Measurements", "RTL state + KU115 events", "#C62828")
    arrow(ax, (4.18, 2.52), (4.18, 1.72))
    arrow(ax, (7.08, 2.52), (7.08, 1.72))
    arrow(ax, (9.98, 2.52), (9.98, 1.72))
    arrow(ax, (5.4, 1.15), (5.85, 1.15))
    arrow(ax, (8.3, 1.15), (8.75, 1.15))
    ax.text(5.63, 0.55, "quantization", ha="center", fontsize=7, color="#455A64")
    ax.text(8.53, 0.55, "execution fidelity", ha="center", fontsize=7, color="#455A64")
    fig.tight_layout(pad=0.2)
    fig.savefig(output / "pipeline.png", dpi=200, facecolor="white")
    plt.close(fig)


if __name__ == "__main__":
    main()
