"""Lock a 250-ms left-LC10a stimulus and its CPU fixed-event oracle."""

from __future__ import annotations

import csv
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
from cns2fpga_golden.stimulus import build_conditions
from cns2fpga_fixed.fixed_lif import FixedFormat, FixedLIFNetwork, quantize


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    output = HERE / "outputs" / "visual_left_board_v0" / "trial"
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(f"Refusing to overwrite locked trial: {output}")
    output.mkdir(parents=True)
    ir = HERE / "outputs" / "visual_left_input_ir_v0"
    config_path = HERE / "configs" / "visual_lif_v0.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    format_path = CODE / "5_Fixed-Point Quantization Analysis" / "configs" / "courtship_song_fixed_point_v6_final.json"
    fmt = FixedFormat.from_dict(next(item for item in json.loads(format_path.read_text(encoding="utf-8"))["formats"]
                                     if item["name"] == "safe_wf24"))
    condition = next(item for item in build_conditions(config["stimulus"], config["model"])
                     if item.name == "pulse_ipi_40ms")
    neurons = pd.read_csv(ir / "neuron_table.csv")
    synapses = pd.read_csv(ir / "synapse_table.csv")
    offsets = pd.read_csv(ir / "offset_table.csv")
    inputs = neurons.index[neurons.is_input_anchor.astype(bool)].to_numpy(np.int64)
    groups = {key: neurons.index[neurons.instance.eq(key)].to_numpy(np.int64)
              for key in ("DNa02_L", "DNa02_R")}
    fixed = FixedLIFNetwork(neurons, synapses, offsets, config["model"], fmt).simulate(
        condition.current, inputs, groups)
    if fixed.state_saturation_events or fixed.accumulator_saturation_events:
        raise RuntimeError("CPU fixed oracle saturated")
    quantized = quantize(condition.current, fmt.state_frac)
    with (output / "stimulus.mem").open("w", encoding="ascii", newline="\n") as stream:
        for value in quantized:
            stream.write(f"{int(value) & ((1 << fmt.state_bits) - 1):09X}\n")
    with (output / "expected_events.csv").open("w", encoding="ascii", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(("timestep", "neuron_index"))
        writer.writerows(zip(fixed.spike_times.tolist(), fixed.spike_neurons.tolist()))
    with (output / "expected_counts.csv").open("w", encoding="ascii", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(("timestep", "total", "DNa02_L", "DNa02_R"))
        counts = np.bincount(fixed.spike_times, minlength=len(condition.current))
        for step in range(len(condition.current)):
            writer.writerow((step, int(counts[step]), int(fixed.group_activity["DNa02_L"][step]),
                             int(fixed.group_activity["DNa02_R"][step])))
    source_files = [Path(__file__), config_path, format_path, ir / "neuron_table.csv",
                    ir / "synapse_table.csv", ir / "offset_table.csv",
                    HERE / "outputs" / "visual_left_hw_ir_v0" / "protocol_lock.json"]
    metadata = {"schema": "cns2fpga.step9.stimulus", "schema_version": 1,
                "trial": "visual_left_ipi_40ms", "network_neurons": len(neurons),
                "dt_ms": 1, "timesteps": len(condition.current),
                "input_current_encoding": {"signed": True, "bits": fmt.state_bits,
                    "frac_bits": fmt.state_frac, "rounding": "nearest_ties_away_from_zero",
                    "word_order": "low32_then_high2", "binary_word_endianness": "little",
                    "binary_words_per_timestep": 2},
                "details": {"input_side": "L", "input_neurons": len(inputs), "ipi_ms": 40,
                    "pulse_width_ms": 3, "amplitude": 1.2, "expected_events": len(fixed.spike_times)},
                "source_sha256": {str(path): sha256(path) for path in source_files},
                "artifact_sha256": {path.name: sha256(path) for path in output.iterdir() if path.is_file()}}
    (output / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"timesteps": metadata["timesteps"], "events": metadata["details"]["expected_events"],
                      "DNa02_L": int(fixed.group_activity["DNa02_L"].sum()),
                      "DNa02_R": int(fixed.group_activity["DNa02_R"].sum())}, indent=2))


if __name__ == "__main__":
    main()
