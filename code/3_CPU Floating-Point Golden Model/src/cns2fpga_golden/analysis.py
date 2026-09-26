"""Observation-group selection, result tables and publication-ready diagnostic plots."""

from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def select_groups(neurons: pd.DataFrame, definitions: list[dict]) -> dict[str, np.ndarray]:
    groups: dict[str, np.ndarray] = {}
    for definition in definitions:
        if "flag" in definition:
            values = neurons[definition["flag"]]
            mask = values if values.dtype == bool else values.astype(str).str.lower().eq("true")
        else:
            field = definition["field"]
            mask = neurons[field].fillna("").astype(str).str.contains(
                definition["regex"], case=False, regex=True
            )
        groups[definition["name"]] = neurons.loc[mask, "neuron_index"].to_numpy(dtype=np.int32)
    return groups


def choose_trace_indices(groups: dict[str, np.ndarray], maximum_per_group: int) -> np.ndarray:
    selected: list[int] = []
    for indices in groups.values():
        selected.extend(int(value) for value in indices[:maximum_per_group])
    return np.array(list(dict.fromkeys(selected)), dtype=np.int32)


def population_table(result, groups: dict[str, np.ndarray], dt_ms: float) -> pd.DataFrame:
    steps = len(next(iter(result.group_activity.values()))) if result.group_activity else 0
    table = pd.DataFrame({"time_ms": np.arange(steps, dtype=np.float64) * dt_ms})
    for name, counts in result.group_activity.items():
        table[f"{name}_spikes"] = counts
        size = max(1, len(groups[name]))
        table[f"{name}_fraction"] = counts / size
    return table


def trace_table(result, neurons: pd.DataFrame, dt_ms: float) -> pd.DataFrame:
    table = pd.DataFrame({"time_ms": np.arange(result.voltage_traces.shape[0]) * dt_ms})
    indexed = neurons.set_index("neuron_index")
    for column, neuron_index in enumerate(result.trace_indices):
        row = indexed.loc[int(neuron_index)]
        label = str(row.get("instance", "")) or str(row.get("type", ""))
        table[f"V_{int(neuron_index)}_{label}"] = result.voltage_traces[:, column]
    return table


def condition_summary(condition, result, groups: dict[str, np.ndarray], duration_ms: float) -> dict:
    duration_seconds = duration_ms / 1000.0
    summary = {
        "condition": condition.name,
        condition.parameter_name: condition.parameter_value,
        "total_network_spikes": int(len(result.spike_times)),
        "max_abs_voltage": result.max_abs_voltage,
    }
    for name, indices in groups.items():
        count = int(result.group_activity[name].sum())
        summary[f"{name}_neurons"] = int(len(indices))
        summary[f"{name}_spikes"] = count
        summary[f"{name}_mean_rate_hz"] = count / (len(indices) * duration_seconds) if len(indices) else 0.0
    return summary


def plot_condition(output: Path, condition, result, population: pd.DataFrame,
                   neurons: pd.DataFrame, groups: dict[str, np.ndarray], dt_ms: float) -> None:
    fig, axes = plt.subplots(3, 1, figsize=(11, 10), constrained_layout=True)
    times = np.arange(len(condition.current)) * dt_ms
    axes[0].plot(times, condition.current, color="black", linewidth=1.2)
    axes[0].set(ylabel="Input current", title=condition.name)

    # Plot selected biological groups only, keeping the raster legible.
    selected = np.concatenate([indices for indices in groups.values() if len(indices)]) if groups else np.empty(0, int)
    selected_set = set(int(value) for value in selected)
    keep = np.fromiter((int(value) in selected_set for value in result.spike_neurons), dtype=bool)
    axes[1].scatter(result.spike_times[keep] * dt_ms, result.spike_neurons[keep], s=4, marker=".")
    axes[1].set(ylabel="Neuron index", title="Observed-group spike raster")

    for name in groups:
        axes[2].plot(population.time_ms, population[f"{name}_fraction"], label=f"{name} (n={len(groups[name])})")
    axes[2].set(xlabel="Time (ms)", ylabel="Spiking fraction", title="Population activity")
    axes[2].legend(loc="upper right", fontsize=8)
    fig.savefig(output / "response.png", dpi=160)
    plt.close(fig)


def plot_summary(output: Path, summary: pd.DataFrame, group_names: list[str], parameter: str) -> None:
    fig, ax = plt.subplots(figsize=(9, 5), constrained_layout=True)
    for name in group_names:
        ax.plot(summary[parameter], summary[f"{name}_mean_rate_hz"], marker="o", label=name)
    ax.set(xlabel=parameter, ylabel="Mean firing rate (Hz)", title="Golden-model response curve")
    ax.legend()
    fig.savefig(output / "response_curve.png", dpi=180)
    plt.close(fig)
