"""Check physical visual-left capture against the locked fixed-point CPU oracle."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE / "outputs" / "visual_left_board_v0"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    trial = ROOT / "trial"
    capture = ROOT / "capture"
    parsed = ROOT / "parsed"
    bit = HERE / "build" / "visual_left_jtag_200mhz" / "cns2fpga_visual_left_jtag_200mhz.bit"
    metadata = json.loads((trial / "metadata.json").read_text(encoding="utf-8"))
    if sha256(trial / "stimulus.mem") != metadata["artifact_sha256"]["stimulus.mem"]:
        raise ValueError("Stimulus changed after lock")
    expected = pd.read_csv(trial / "expected_events.csv")
    actual = pd.read_csv(parsed / "events.csv")
    counts = pd.read_csv(parsed / "counts.csv")
    expected_counts = pd.read_csv(trial / "expected_counts.csv")
    neurons = pd.read_csv(HERE / "outputs" / "visual_left_input_ir_v0" / "neuron_table.csv")
    if len(expected) != len(actual) or not np.array_equal(expected.to_numpy(), actual.to_numpy()):
        raise AssertionError("Ordered CPU/FPGA spike events differ")
    if not np.array_equal(counts.total.to_numpy(), expected_counts.total.to_numpy()):
        raise AssertionError("CPU/FPGA per-timestep total spikes differ")
    if actual.neuron_index.max() >= len(neurons):
        raise AssertionError("Board event index outside visual graph")
    for side in ("L", "R"):
        index = int(neurons.loc[neurons.instance.eq(f"DNa02_{side}"), "neuron_index"].iloc[0])
        actual_group = np.bincount(actual.loc[actual.neuron_index.eq(index), "timestep"], minlength=len(counts))
        if not np.array_equal(actual_group, expected_counts[f"DNa02_{side}"].to_numpy()):
            raise AssertionError(f"DNa02_{side} timestep mismatch")
    flags = ["state_saturation", "accumulator_saturation", "deadline_miss", "event_overflow"]
    if any(int(counts[name].sum()) for name in flags):
        raise AssertionError("Board saturation, deadline miss or event overflow")
    registers = dict(zip(*[pd.read_csv(capture / "registers.csv")[key].tolist() for key in ("name", "hex32")]))
    if int(registers["ID"], 16) != 0x434E5339 or int(registers["COMPLETED_STEPS"], 16) != 250:
        raise AssertionError("Board ID or completed-step register mismatch")
    if int(registers["GLOBAL_EVENT_COUNT"], 16) != len(actual):
        raise AssertionError("Board event-count register mismatch")
    report = {"verdict": "PASS", "network_neurons": len(neurons), "graph_edges": 1730,
              "input_neurons": int(neurons.is_input_anchor.astype(bool).sum()),
              "timesteps": len(counts), "ordered_events_compared": len(actual),
              "per_timestep_total_compared": len(counts),
              "DNa02_L_spikes": int(expected_counts.DNa02_L.sum()),
              "DNa02_R_spikes": int(expected_counts.DNa02_R.sum()),
              "max_latency_cycles": int(counts.cycles.max()),
              "period_cycles": 200000, "diagnostic_sum": {name: int(counts[name].sum()) for name in flags},
              "bitstream_sha256": sha256(bit), "stimulus_sha256": sha256(trial / "stimulus.mem"),
              "capture_sha256": {name: sha256(capture / name) for name in
                                 ("registers.csv", "summary_words.hex", "event_words.hex")}}
    (ROOT / "verification.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
