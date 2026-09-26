"""Plot discriminating visual-circuit baseline results from recorded CSVs."""

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

HERE = Path(__file__).resolve().parent
DATA = HERE / "outputs" / "baseline_v0"


def main() -> None:
    frame = pd.read_csv(DATA / "manual_vs_automatic.csv")
    pulse = frame.loc[frame.condition.str.startswith("pulse_ipi_")].copy()
    pulse["ipi_ms"] = pulse.condition.str.extract(r"pulse_ipi_(\d+)ms").astype(int)
    fig, axes = plt.subplots(1, 2, figsize=(8, 3.2), sharey=True)
    for axis, side in zip(axes, ("L", "R")):
        subset = pulse.loc[pulse.stimulated_side.eq(side)].sort_values("ipi_ms")
        axis.plot(subset.ipi_ms, subset[f"reference_DNa02_{side}"], "o-", label="MaleCNS automatic")
        axis.plot(subset.ipi_ms, subset[f"manual_DNa02_{side}"], "s--", label="manual type graph")
        axis.set(xlabel="Pulse interval (ms)", title=f"{side}-side LC10a input")
        axis.grid(alpha=0.3)
    axes[0].set_ylabel("Ipsilateral DNa02 spike count")
    axes[1].legend(frameon=False, fontsize=8)
    fig.tight_layout()
    fig.savefig(DATA / "lateralized_baseline.png", dpi=180)
    plt.close(fig)


if __name__ == "__main__":
    main()
