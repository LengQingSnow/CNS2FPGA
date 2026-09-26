"""Compare full-length float and fixed execution on the extracted visual pathway."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
CODE = HERE.parent
sys.path.insert(0, str(CODE / "3_CPU Floating-Point Golden Model" / "src"))
sys.path.insert(0, str(CODE / "5_Fixed-Point Quantization Analysis" / "src"))
from cns2fpga_golden.model import FloatLIFNetwork
from cns2fpga_golden.stimulus import build_conditions
from cns2fpga_fixed.fixed_lif import FixedFormat, FixedLIFNetwork


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    config_path = HERE / "configs" / "visual_lif_v0.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    ir = HERE / "outputs" / "visual_to_steering_v0"
    neurons = pd.read_csv(ir / "neuron_table.csv")
    synapses = pd.read_csv(ir / "synapse_table.csv")
    offsets = pd.read_csv(ir / "offset_table.csv")
    model = config["model"]
    fixed_config_path = CODE / "5_Fixed-Point Quantization Analysis" / "configs" / "courtship_song_fixed_point_v6_final.json"
    fixed_config = json.loads(fixed_config_path.read_text(encoding="utf-8"))
    fmt = FixedFormat.from_dict(next(item for item in fixed_config["formats"] if item["name"] == "safe_wf24"))
    float_net = FloatLIFNetwork(neurons, synapses, offsets, model)
    fixed_net = FixedLIFNetwork(neurons, synapses, offsets, model, fmt)
    groups = {name: neurons.index[neurons.type.eq(name)].to_numpy(np.int64)
              for name in ("LC10a", "AOTU019", "AOTU025", "DNa02")}
    groups["DNa02_L"] = neurons.index[neurons.instance.eq("DNa02_L")].to_numpy(np.int64)
    groups["DNa02_R"] = neurons.index[neurons.instance.eq("DNa02_R")].to_numpy(np.int64)
    inputs = neurons.index[neurons.is_input_anchor.astype(bool)].to_numpy(np.int64)
    assert len(inputs) == 220 and all(len(groups[key]) == 1 for key in ("DNa02_L", "DNa02_R"))
    output = HERE / "outputs" / "visual_experiment_v0"
    output.mkdir(parents=True, exist_ok=True)
    rows = []
    activity_rows = []
    for condition in build_conditions(config["stimulus"], model):
      for stimulated_side in ("bilateral", "L", "R"):
        selected_inputs = inputs if stimulated_side == "bilateral" else np.intersect1d(
            inputs, neurons.index[neurons.somaSide.eq(stimulated_side)].to_numpy(np.int64))
        flt = float_net.simulate(condition.current, selected_inputs, groups, np.empty(0, np.int64))
        fixed = fixed_net.simulate(condition.current, selected_inputs, groups)
        float_events = set(zip(flt.spike_times.tolist(), flt.spike_neurons.tolist()))
        fixed_events = set(zip(fixed.spike_times.tolist(), fixed.spike_neurons.tolist()))
        overlap = len(float_events & fixed_events)
        f1 = 2 * overlap / (len(float_events) + len(fixed_events)) if float_events or fixed_events else 1.0
        row = {"condition": condition.name, "stimulated_side": stimulated_side,
               "input_neurons": len(selected_inputs), "ipi_ms": condition.parameter_value,
               "float_total_spikes": len(float_events), "fixed_total_spikes": len(fixed_events),
               "event_f1": f1, "state_saturations": fixed.state_saturation_events,
               "accumulator_saturations": fixed.accumulator_saturation_events}
        for name in groups:
            row[f"float_{name}_spikes"] = int(flt.group_activity[name].sum())
            row[f"fixed_{name}_spikes"] = int(fixed.group_activity[name].sum())
            for timestep, (f, q) in enumerate(zip(flt.group_activity[name], fixed.group_activity[name])):
                activity_rows.append({"condition": condition.name, "stimulated_side": stimulated_side,
                                      "timestep": timestep,
                                      "group": name, "float_spikes": int(f), "fixed_spikes": int(q)})
        rows.append(row)
    pd.DataFrame(rows).to_csv(output / "summary.csv", index=False)
    pd.DataFrame(activity_rows).to_csv(output / "activity.csv", index=False)
    manifest = {"input_sha256": {str(path): sha256(path) for path in
                [config_path, fixed_config_path, ir / "neuron_table.csv", ir / "synapse_table.csv", ir / "offset_table.csv"]},
                "format": fmt.as_dict(), "group_sizes": {key: len(value) for key, value in groups.items()},
                "cases": len(rows)}
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(pd.DataFrame(rows).to_string(index=False))


if __name__ == "__main__":
    main()
