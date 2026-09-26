"""Regenerate the three locked noise inputs and compare every board timestep."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from run_robustness import OUT, BOARD_CAPTURE_SOURCE, GROUPS, LEVELS, intervention, setup


def main() -> int:
    output = OUT
    lock = json.loads((output / "protocol_lock.json").read_text(encoding="utf-8"))
    _, _, _, groups, _, fixed, current, _, _ = setup()
    rows = []
    for level in LEVELS:
        name = f"input_noise_{level:02d}_r0"
        case = next(item for item in lock["cases"] if item["name"] == name)
        parameters, artifact = intervention(case, current, groups, fixed.n, len(fixed.synapses))
        if artifact["selection_sha256"] != case["selection_sha256"]:
            raise RuntimeError(f"Noise waveform does not match protocol lock: {name}")
        result = fixed.simulate(parameters["external_current"], groups["auditory_input"], groups)
        local_capture = output / "captures" / f"{name}_parsed" / "counts.csv"
        capture = local_capture if local_capture.is_file() else BOARD_CAPTURE_SOURCE / "captures" / f"{name}_parsed" / "counts.csv"
        board = pd.read_csv(capture)
        expected = {group: result.group_activity[group] for group in ("aPN1", *GROUPS)}
        expected["total"] = np.bincount(result.spike_times, minlength=len(current))
        for group, series in expected.items():
            actual = board[group].to_numpy(dtype=np.int64)
            differences = np.flatnonzero(actual != series)
            rows.append({"case": name, "level_pct": level, "group": group,
                         "timesteps": len(actual), "mismatch_steps": len(differences),
                         "first_mismatch": int(differences[0]) if len(differences) else "",
                         "fixed_total_spikes": int(series.sum()),
                         "fpga_total_spikes": int(actual.sum()),
                         "counts_csv_sha256": hashlib.sha256(capture.read_bytes()).hexdigest()})
    frame = pd.DataFrame(rows)
    frame.to_csv(output / "fpga_noise_per_step_verification.csv", index=False)
    passed = bool(frame.mismatch_steps.eq(0).all())
    (output / "fpga_noise_per_step_verification.json").write_text(
        json.dumps({"pass": passed, "trials": len(LEVELS), "groups_per_trial": len(expected),
                    "neuron_group_timesteps_compared": int(frame.timesteps.sum()),
                    "mismatch_steps": int(frame.mismatch_steps.sum())}, indent=2) + "\n",
        encoding="utf-8")
    print(f"Board noise per-step verification: {'PASS' if passed else 'FAIL'}, mismatches={int(frame.mismatch_steps.sum())}")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
