"""Stream ordered fixed-point CPU spikes for the locked 4,308-step trials.

This is an independent reference, not a reconstruction from FPGA group counts.
The per-step totals are checked against the earlier dedicated-board capture.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd


CODE = Path(__file__).resolve().parents[2]
STEP8 = CODE / "8_RTL Bit-Exact Co-Simulation"
sys.path.insert(0, str(STEP8 / "src"))
from reference_stepper import ReferenceStepper


def run(ipi: int, output: Path) -> dict:
    config = json.loads((STEP8 / "configs" / "full_network_8step_v1.json").read_text(encoding="utf-8"))
    base = STEP8 / "configs"
    resolved = lambda key: (base / config[key]).resolve()
    ir = resolved("source_ir")
    golden = json.loads(resolved("golden_config").read_text(encoding="utf-8"))
    fixed_config = json.loads(resolved("fixed_config").read_text(encoding="utf-8"))
    fmt = next(item for item in fixed_config["formats"] if item["name"] == config["fixed_format"])
    sys.path.insert(0, str(resolved("fixed_src")))
    import cns2fpga_fixed.fixed_lif as fixed_ops

    neurons = pd.read_csv(ir / "neuron_table.csv")
    synapses = pd.read_csv(ir / "synapse_table.csv")
    offsets = pd.read_csv(ir / "offset_table.csv")
    indices = neurons.loc[neurons.is_input_anchor.astype(bool), "neuron_index"].to_numpy(np.int64)
    stepper = ReferenceStepper(neurons, synapses, offsets, golden["model"], fmt, fixed_ops)
    trial = CODE / "9_KU115 FPGA Validation" / "host" / "trials" / f"ipi_{ipi}"
    stimulus = trial / "stimulus.mem"
    old_counts = CODE / "9_KU115 FPGA Validation" / "host" / "captures" / f"ipi_{ipi}_summary_parsed" / "counts.csv"
    with old_counts.open(newline="", encoding="utf-8-sig") as stream:
        expected = [int(row["total"]) for row in csv.DictReader(stream)]
    raw = [int(line.strip(), 16) for line in stimulus.read_text(encoding="ascii").splitlines() if line.strip()]
    if len(raw) != 4308 or len(expected) != len(raw):
        raise ValueError("Locked trial/reference must contain 4308 steps")
    output.mkdir(parents=True, exist_ok=False)
    event_path = output / "expected_events.csv"
    count_path = output / "expected_counts.csv"
    total = 0
    with event_path.open("w", newline="", encoding="ascii") as event_stream, count_path.open("w", newline="", encoding="ascii") as count_stream:
        events = csv.writer(event_stream)
        counts = csv.writer(count_stream)
        events.writerow(("timestep", "neuron_index"))
        counts.writerow(("timestep", "total"))
        for timestep, value in enumerate(raw):
            signed = value - (1 << 34) if value & (1 << 33) else value
            spikes = np.flatnonzero(stepper.step(signed / (1 << 24), indices)["spikes"])
            count = len(spikes)
            if count != expected[timestep]:
                raise AssertionError(f"CPU/dedicated-board count mismatch at step {timestep}: {count} != {expected[timestep]}")
            counts.writerow((timestep, count))
            events.writerows((timestep, int(neuron)) for neuron in spikes)
            total += count
            if timestep % 500 == 499:
                print(f"CPU_REFERENCE_PROGRESS ipi={ipi} steps={timestep + 1}/4308 events={total}", flush=True)
    result = {
        "status": "PASS", "ipi_ms": ipi, "steps": len(raw), "neurons": len(neurons),
        "ordered_events": total,
        "stimulus_sha256": hashlib.sha256(stimulus.read_bytes()).hexdigest().upper(),
        "events_sha256": hashlib.sha256(event_path.read_bytes()).hexdigest().upper(),
        "counts_sha256": hashlib.sha256(count_path.read_bytes()).hexdigest().upper(),
    }
    (output / "reference_manifest.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ipi-ms", type=int, required=True, choices=(15, 35, 65))
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.ipi_ms, args.output_dir), indent=2), flush=True)
