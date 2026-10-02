"""Plot the audited eight-step courtship capture at a measured 100-Mbps link."""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


HERE = Path(__file__).resolve().parent
audit = json.loads((HERE.parent / "15_Ethernet_Runtime_Deployment" / "reports" / "expanded_bit_100m_audit_v1.json").read_text(encoding="utf-8"))
if audit["status"] != "PASS":
    raise RuntimeError("Plot requires a passing independent audit")
plt.rcParams.update({"font.family": "Arial", "font.size": 11, "axes.spines.top": False, "axes.spines.right": False})
fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.4))
steps = [row["timestep"] for row in audit["per_step"]]
cpu = [row["cpu_spikes"] for row in audit["per_step"]]
board = [row["board_spikes"] for row in audit["per_step"]]
axes[0].plot(steps, cpu, color="#008577", linewidth=2, label="Fixed CPU")
axes[0].scatter(steps, board, facecolors="none", edgecolors="#263F5B", s=70, linewidths=1.7, label="AXKU115")
axes[0].set(xlabel="Model timestep", ylabel="Whole-network spikes", title="A  Exact per-step count agreement", xticks=steps)
axes[0].legend(frameon=False)
axes[1].bar(steps, [row["cycles"] for row in audit["per_step"]], color="#263F5B", width=0.65)
axes[1].axhline(audit["period_cycles"], color="#B3573F", linestyle="--", label="1-ms deadline at 200 MHz")
axes[1].set(xlabel="Model timestep", ylabel="Core cycles", title="B  Deadline met at every step", xticks=steps, ylim=(0, 225000))
axes[1].legend(frameon=False, loc="lower right", fontsize=9)
axes[1].annotate("199,699 cycles\n301-cycle margin", xy=(3, 199699), xytext=(3.3, 163000), fontsize=9,
                 arrowprops={"arrowstyle": "->", "color": "#586873"})
for ax in axes:
    ax.grid(axis="y", alpha=.2)
    ax.set_axisbelow(True)
fig.suptitle("Expanded-event runtime at measured 100 Mbps", fontsize=15, fontweight="bold", y=.98)
fig.text(.5, .895, "One programming operation  |  20/20 STATUS replies  |  Full courtship UDP image upload", ha="center", fontsize=10)
fig.text(.5, .025, "2,475 exact ordered events  |  Epoch 1  |  Checksum 45AEAAAE  |  Zero bad FCS, missed steps or faults", ha="center", fontsize=10)
fig.subplots_adjust(left=.075, right=.985, top=.77, bottom=.18, wspace=.28)
output = HERE / "figures" / "figure10_100m_board_validation.png"
fig.savefig(output, dpi=220, facecolor="white")
plt.close(fig)
print(output)
