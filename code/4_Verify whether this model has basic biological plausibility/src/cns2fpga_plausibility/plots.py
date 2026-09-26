"""Static figures for the plausibility audit."""

from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


COLORS = {"PASS": "#2e7d32", "FAIL": "#c62828", "WARN": "#ef6c00"}


def plot_tuning(output: Path, summary: pd.DataFrame) -> None:
    fig, axes = plt.subplots(2, 1, figsize=(9, 8), sharex=True, constrained_layout=True)
    for group in ["aPN1", "vPN1", "pC1"]:
        axes[0].plot(summary.ipi_ms, summary[f"{group}_mean_rate_hz"], marker="o", linewidth=2, label=group)
    for group in ["pIP10", "pMP2"]:
        axes[1].plot(summary.ipi_ms, summary[f"{group}_mean_rate_hz"], marker="o", linewidth=2, label=group)
    for ax in axes:
        ax.axvspan(35, 65, color="#43a047", alpha=0.12, label="reported pC1 high-response band")
        ax.axvline(35, color="#1b5e20", linestyle="--", linewidth=1, label="conspecific IPI ~35 ms")
        ax.set_ylabel("Mean firing rate (Hz)")
        ax.legend(fontsize=8)
    axes[0].set_title("Literature-mapped ascending pathway")
    axes[1].set_title("Selected downstream courtship-output proxies")
    axes[1].set_xlabel("Inter-pulse interval (ms)")
    fig.suptitle("Model IPI tuning versus qualitative experimental constraints", fontsize=15)
    fig.savefig(output / "ipi_tuning_audit.png", dpi=180)
    plt.close(fig)


def plot_ablation(output: Path, ablations: pd.DataFrame) -> None:
    ordered = ablations.sort_values(["kind", "replicate"])
    fig, ax = plt.subplots(figsize=(9, 5.2), constrained_layout=True)
    random = ordered[ordered.kind.eq("random_control")]
    if len(random):
        ax.scatter(np.repeat(0, len(random)), random.output_drop_percent,
                   alpha=0.65, color="#78909c", label="matched random ablations")
    targets = ordered[~ordered.kind.eq("random_control")]
    positions = np.arange(1, len(targets) + 1)
    ax.bar(positions, targets.output_drop_percent, color=["#5e35b1", "#00838f"][:len(targets)])
    ax.set_xticks([0, *positions], ["random", *targets.label.tolist()])
    ax.axhline(0, color="black", linewidth=0.8)
    ax.set(ylabel="pIP10+pMP2 mean-rate drop (%)", title="Preferred-IPI in-silico ablation")
    ax.legend(loc="best", fontsize=8)
    fig.savefig(output / "ablation_audit.png", dpi=180)
    plt.close(fig)


def plot_dashboard(output: Path, checks: pd.DataFrame, nt_summary: pd.DataFrame) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.6), constrained_layout=True)
    counts = checks.status.value_counts().reindex(["PASS", "FAIL", "WARN"], fill_value=0)
    axes[0].bar(counts.index, counts.values, color=[COLORS[x] for x in counts.index])
    axes[0].set(ylabel="Check count", title="Validation outcomes")
    axes[0].bar_label(axes[0].containers[0])
    signs = nt_summary.set_index("consensus_nt")
    labels = [x for x in ["acetylcholine", "gaba", "glutamate", "unclear"] if x in signs.index]
    values = [int(signs.loc[x, "neurons"]) for x in labels]
    axes[1].bar(labels, values, color="#546e7a")
    axes[1].tick_params(axis="x", rotation=30)
    axes[1].set(ylabel="Neurons", title="Neurotransmitter composition")
    fig.savefig(output / "validation_dashboard.png", dpi=180)
    plt.close(fig)
