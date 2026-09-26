"""Execute all configured floating-point LIF Golden-Model conditions."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
import scipy

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from cns2fpga_golden.analysis import (
    choose_trace_indices,
    condition_summary,
    plot_condition,
    plot_summary,
    population_table,
    select_groups,
    trace_table,
)
from cns2fpga_golden.model import FloatLIFNetwork
from cns2fpga_golden.stimulus import build_conditions


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output-dir", type=Path)
    return parser.parse_args()


def report_text(config: dict, groups: dict[str, np.ndarray], summary: pd.DataFrame,
                elapsed_seconds: float) -> str:
    group_rows = "\n".join(f"| {name} | {len(indices):,} |" for name, indices in groups.items())
    result_columns = ["condition", "total_network_spikes"] + [
        f"{name}_mean_rate_hz" for name in groups
    ]
    result_header = "| " + " | ".join(result_columns) + " |"
    result_separator = "| " + " | ".join(["---"] + ["---:"] * (len(result_columns) - 1)) + " |"
    result_rows = []
    for _, row in summary.iterrows():
        values = [str(row["condition"]), f"{int(row['total_network_spikes']):,}"]
        values.extend(f"{float(row[column]):.3f}" for column in result_columns[2:])
        result_rows.append("| " + " | ".join(values) + " |")
    model = config["model"]
    return f"""# {config['name']} report

This is a computational LIF reference model, not a biological-behavior validation.

## Frozen execution semantics

- dt: {model['dt_ms']} ms
- duration: {model['duration_ms']} ms
- membrane time constant: {model['tau_membrane_ms']} ms
- threshold/reset: {model['threshold']} / {model['reset_voltage']}
- refractory period: {model['refractory_ms']} ms
- weight mode: `{model['weight_mode']}`
- propagation backend: `{model['propagation_backend']}`
- recurrent gain: {model['recurrent_gain']}
- noise standard deviation: {model['noise_std']}
- random seed: {model['random_seed']}

## Observed populations

| Group | Neurons |
| --- | ---: |
{group_rows}

## Condition summary

{result_header}
{result_separator}
{chr(10).join(result_rows)}

Runtime: {elapsed_seconds:.3f} seconds.
"""


def main() -> None:
    args = parse_args()
    config_path = args.config.resolve()
    config = json.loads(config_path.read_text(encoding="utf-8"))
    ir_paths = {name: (config_path.parent / value).resolve() for name, value in config["ir"].items()}
    missing = [str(path) for path in ir_paths.values() if not path.is_file()]
    if missing:
        raise FileNotFoundError("Missing step-2 IR files:\n" + "\n".join(missing))
    output = (args.output_dir or ROOT / "outputs" / config["name"]).resolve()
    output.mkdir(parents=True, exist_ok=True)

    neurons = pd.read_csv(ir_paths["neuron_table"])
    synapses = pd.read_csv(ir_paths["synapse_table"])
    offsets = pd.read_csv(ir_paths["offset_table"])
    network = FloatLIFNetwork(neurons, synapses, offsets, config["model"])
    groups = select_groups(neurons, config["observations"])
    input_indices = groups["auditory_input"]
    if not len(input_indices):
        raise ValueError("The auditory_input observation group is empty")
    traces = choose_trace_indices(groups, int(config["max_trace_neurons_per_group"]))
    conditions = build_conditions(config["stimulus"], config["model"])
    summaries: list[dict] = []
    started = time.perf_counter()

    for condition in conditions:
        condition_dir = output / condition.name
        condition_dir.mkdir(parents=True, exist_ok=True)
        result = network.simulate(condition.current, input_indices, groups, traces)
        np.savez_compressed(
            condition_dir / "spikes.npz",
            timestep=result.spike_times,
            neuron_index=result.spike_neurons,
            dt_ms=np.array([config["model"]["dt_ms"]], dtype=np.float64),
        )
        population = population_table(result, groups, float(config["model"]["dt_ms"]))
        population.to_csv(condition_dir / "population_activity.csv", index=False)
        trace_table(result, neurons, float(config["model"]["dt_ms"])).to_csv(
            condition_dir / "membrane_traces.csv", index=False
        )
        plot_condition(
            condition_dir, condition, result, population, neurons, groups,
            float(config["model"]["dt_ms"]),
        )
        summaries.append(
            condition_summary(
                condition, result, groups, float(config["model"]["duration_ms"])
            )
        )

    elapsed = time.perf_counter() - started
    summary = pd.DataFrame(summaries)
    summary.to_csv(output / "summary.csv", index=False)
    parameter = conditions[0].parameter_name
    plot_summary(output, summary, list(groups), parameter)
    provenance = {
        "config": config,
        "input_sha256": {name: file_sha256(path) for name, path in ir_paths.items()},
        "config_sha256": file_sha256(config_path),
        "group_sizes": {name: int(len(indices)) for name, indices in groups.items()},
        "runtime_seconds": elapsed,
        "numpy_version": np.__version__,
        "scipy_version": scipy.__version__,
        "matplotlib_version": matplotlib.__version__,
    }
    (output / "run_metadata.json").write_text(json.dumps(provenance, indent=2), encoding="utf-8")
    report = report_text(config, groups, summary, elapsed)
    (output / "report.md").write_text(report, encoding="utf-8")
    print(report)
    print(f"Wrote Golden-Model outputs to {output}")


if __name__ == "__main__":
    main()
