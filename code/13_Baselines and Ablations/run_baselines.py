"""Reproducible type-level hand map, synthetic wiring and width baselines."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
CODE = HERE.parent
VISUAL = CODE / "12_Visual-to-Steering Circuit"
sys.path.insert(0, str(CODE / "3_CPU Floating-Point Golden Model" / "src"))
sys.path.insert(0, str(CODE / "5_Fixed-Point Quantization Analysis" / "src"))
from cns2fpga_golden.model import FloatLIFNetwork
from cns2fpga_golden.stimulus import build_conditions
from cns2fpga_fixed.fixed_lif import FixedFormat, FixedLIFNetwork


def events(result) -> set[tuple[int, int]]:
    return set(zip(result.spike_times.tolist(), result.spike_neurons.tolist()))


def f1(a: set, b: set) -> float:
    return 2 * len(a & b) / (len(a) + len(b)) if a or b else 1.0


def manual_graph(neurons: pd.DataFrame, real: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Hand-written 4-type schematic, not inferred individual MaleCNS edges."""
    type_pairs = [("LC10a", "AOTU019"), ("LC10a", "AOTU025"),
                  ("AOTU019", "DNa02"), ("AOTU025", "DNa02")]
    by_index = neurons.set_index("neuron_index")
    real = real.copy()
    real["pre_type"] = real.pre_index.map(by_index.type)
    real["post_type"] = real.post_index.map(by_index.type)
    rows = []
    for pre_type, post_type in type_pairs:
        observed = real.loc[(real.pre_type == pre_type) & (real.post_type == post_type), "synapse_count"]
        if observed.empty:
            raise ValueError(f"No real edges for manual pair {pre_type}->{post_type}")
        count = max(1, int(np.median(observed)))
        for pre in neurons.loc[neurons.type == pre_type, "neuron_index"]:
            sign = int(by_index.loc[pre, "nt_model_sign"])
            for post in neurons.loc[neurons.type == post_type, "neuron_index"]:
                rows.append((int(pre), int(post), count, sign))
    synthetic = pd.DataFrame(rows, columns=["pre_index", "post_index", "synapse_count", "nt_model_sign"])
    synthetic = synthetic.sort_values(["pre_index", "post_index"]).reset_index(drop=True)
    edge_counts = np.bincount(synthetic.pre_index, minlength=len(neurons))
    offsets = pd.DataFrame({"neuron_index": np.arange(len(neurons)),
                            "edge_start": np.r_[0, np.cumsum(edge_counts)[:-1]], "edge_count": edge_counts})
    rules = pd.DataFrame([{"pre_type": a, "post_type": b,
                           "uniform_synapse_count": int(synthetic.loc[
                               (synthetic.pre_index.map(by_index.type) == a) &
                               (synthetic.post_index.map(by_index.type) == b), "synapse_count"].iloc[0])}
                          for a, b in type_pairs])
    return synthetic, offsets, rules


def main() -> None:
    output = HERE / "outputs" / "baseline_v0"
    output.mkdir(parents=True, exist_ok=True)
    ir = VISUAL / "outputs" / "visual_to_steering_v0"
    neurons = pd.read_csv(ir / "neuron_table.csv")
    real = pd.read_csv(ir / "synapse_table.csv")
    offsets = pd.read_csv(ir / "offset_table.csv")
    config_path = VISUAL / "configs" / "visual_lif_v0.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    model = config["model"]
    formats_path = CODE / "5_Fixed-Point Quantization Analysis" / "configs" / "courtship_song_fixed_point_v6_final.json"
    formats = json.loads(formats_path.read_text(encoding="utf-8"))["formats"]
    manual, manual_offsets, rules = manual_graph(neurons, real)
    rules.to_csv(output / "manual_rules.csv", index=False)
    manual.to_csv(output / "manual_synapse_table.csv", index=False)
    manual_offsets.to_csv(output / "manual_offset_table.csv", index=False)
    real_pairs = set(zip(real.pre_index, real.post_index))
    manual_pairs = set(zip(manual.pre_index, manual.post_index))
    structural = {"automatic_neurons": len(neurons), "automatic_edges": len(real),
                  "manual_neurons": len(neurons), "manual_edges": len(manual),
                  "manual_edges_overlapping_real": len(real_pairs & manual_pairs),
                  "edge_jaccard": len(real_pairs & manual_pairs) / len(real_pairs | manual_pairs),
                  "automatic_synapses": int(real.synapse_count.sum()),
                  "manual_synapses": int(manual.synapse_count.sum())}
    (output / "structural_comparison.json").write_text(json.dumps(structural, indent=2), encoding="utf-8")
    inputs = neurons.index[neurons.is_input_anchor.astype(bool)].to_numpy(np.int64)
    groups = {name: neurons.index[neurons.type.eq(name)].to_numpy(np.int64)
              for name in ("LC10a", "AOTU019", "AOTU025", "DNa02")}
    real_float = FloatLIFNetwork(neurons, real, offsets, model)
    manual_float = FloatLIFNetwork(neurons, manual, manual_offsets, model)
    fixed_nets = {item["name"]: FixedLIFNetwork(neurons, real, offsets, model, FixedFormat.from_dict(item))
                  for item in formats}
    rows = []
    width_rows: list[dict] = []
    conditions = build_conditions(config["stimulus"], model)
    from cns2fpga_golden.stimulus import StimulusCondition
    for amplitude in (0.08, 0.12, 0.2, 0.4, 0.8, 1.2):
        current = np.zeros(250, dtype=np.float64)
        current[20:220] = amplitude
        conditions.append(StimulusCondition(f"sustained_{amplitude:g}", "amplitude", amplitude, current))
    groups["DNa02_L"] = neurons.index[neurons.instance.eq("DNa02_L")].to_numpy(np.int64)
    groups["DNa02_R"] = neurons.index[neurons.instance.eq("DNa02_R")].to_numpy(np.int64)
    for condition in conditions:
      for side in ("bilateral", "L", "R"):
        selected_inputs = inputs if side == "bilateral" else np.intersect1d(
            inputs, neurons.index[neurons.somaSide.eq(side)].to_numpy(np.int64))
        reference = real_float.simulate(condition.current, selected_inputs, groups, np.empty(0, np.int64))
        baseline = manual_float.simulate(condition.current, selected_inputs, groups, np.empty(0, np.int64))
        row = {"condition": condition.name, "stimulated_side": side,
               "reference_spikes": len(events(reference)),
               "manual_spikes": len(events(baseline)), "manual_event_f1": f1(events(reference), events(baseline))}
        for group in groups:
            row[f"reference_{group}"] = int(reference.group_activity[group].sum())
            row[f"manual_{group}"] = int(baseline.group_activity[group].sum())
        rows.append(row)
        for name, net in fixed_nets.items():
            result = net.simulate(condition.current, selected_inputs, groups)
            width_row = {"condition": condition.name, "stimulated_side": side, "format": name,
                         "reference_spikes": len(events(reference)), "fixed_spikes": len(events(result)),
                         "event_f1": f1(events(reference), events(result)),
                         "state_saturations": result.state_saturation_events,
                         "accumulator_saturations": result.accumulator_saturation_events}
            for group in groups:
                width_row[f"reference_{group}"] = int(reference.group_activity[group].sum())
                width_row[f"fixed_{group}"] = int(result.group_activity[group].sum())
            width_rows.append(width_row)
    pd.DataFrame(rows).to_csv(output / "manual_vs_automatic.csv", index=False)
    pd.DataFrame(width_rows).to_csv(output / "width_ablation.csv", index=False)
    tracked = [Path(__file__), config_path, formats_path, ir / "neuron_table.csv", ir / "synapse_table.csv", ir / "offset_table.csv"]
    (output / "manifest.json").write_text(json.dumps({"input_and_source_sha256": {
        str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in tracked},
        "manual_graph_definition": "four complete bipartite type pairs; median real synapse count per type pair",
        "formats": [item["name"] for item in formats]}, indent=2), encoding="utf-8")
    print(json.dumps(structural, indent=2))
    print(pd.DataFrame(rows).to_string(index=False))
    print(pd.DataFrame(width_rows)[["condition", "format", "event_f1", "state_saturations", "accumulator_saturations"]].to_string(index=False))


if __name__ == "__main__":
    main()
