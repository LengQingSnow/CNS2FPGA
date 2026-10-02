"""Audit a 4,308-step runtime board capture and compare older per-step counts.

The older dedicated-board capture is a paired implementation comparator, not
an independent CPU reference. Run Step 9's ``compare-groups`` separately for
the fixed-point CPU response-window comparison.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path


COMPARE_FIELDS = ("total", "aPN1", "vPN1", "pC1", "pIP10", "pMP2", "event_count", "flags")


def registers(path: Path) -> dict[str, int]:
    with path.open(newline="", encoding="ascii") as stream:
        return {row["name"]: int(row["hex32"], 16) for row in csv.DictReader(stream)}


def words(path: Path) -> list[int]:
    with path.open(encoding="ascii") as stream:
        values = [line.strip() for line in stream if line.strip()]
    if any(len(value) != 8 for value in values):
        raise ValueError("Malformed summary word")
    return [int(value, 16) for value in values]


def rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as stream:
        return list(csv.DictReader(stream))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture-dir", required=True, type=Path)
    parser.add_argument("--counts", required=True, type=Path,
                        help="new capture parsed by Step 9 parse-dump")
    parser.add_argument("--reference-counts", required=True, type=Path,
                        help="older dedicated-board per-step counts")
    parser.add_argument("--expected-epoch", required=True, type=int)
    args = parser.parse_args()
    captured = registers(args.capture_dir / "registers.csv")
    summary_path = args.capture_dir / "summary_words.hex"
    raw = words(summary_path)
    new, old = rows(args.counts), rows(args.reference_counts)
    steps = 4308
    required = {
        "ID": 0x434E5352,
        "STATUS": 2,
        "IMAGE_STATUS": 1,
        "IMAGE_CHECKSUM": 0x45AEAAAE,
        "IMAGE_EPOCH": args.expected_epoch,
        "ACTIVE_NEURONS": 6279,
        "ACTIVE_SYNAPSES": 350185,
        "LENGTH": steps,
        "COMPLETED_STEPS": steps,
        "MISSED_STEPS": 0,
    }
    for name, expected in required.items():
        actual = captured[name]
        if actual != expected:
            raise AssertionError(f"{name}: {actual:#x} != {expected:#x}")
    if len(raw) != steps * 8 or len(new) != steps or len(old) != steps:
        raise AssertionError("Capture/reference timestep count mismatch")
    if captured["MAX_LATENCY"] > 200_000 or captured["PERIOD_CYCLES"] != 200_000:
        raise AssertionError("One-millisecond deadline violated")
    differing_cycles = 0
    max_cycle_delta = 0
    for step, (current, reference) in enumerate(zip(new, old)):
        if int(current["timestep"]) != step or int(reference["timestep"]) != step:
            raise AssertionError(f"Noncontiguous timestep at {step}")
        for field in COMPARE_FIELDS:
            if int(current[field]) != int(reference[field]):
                raise AssertionError(
                    f"Step {step}, {field}: {current[field]} != {reference[field]}"
                )
        if int(current["flags"]) != 0 or int(current["deadline_miss"]) != 0:
            raise AssertionError(f"Step {step} has fault/deadline flag")
        if int(current["cycles"]) > 200_000:
            raise AssertionError(f"Step {step} exceeds deadline")
        delta = int(current["cycles"]) - int(reference["cycles"])
        if delta:
            differing_cycles += 1
            max_cycle_delta = max(max_cycle_delta, abs(delta))
    result = {
        "status": "PASS",
        "steps": steps,
        "epoch": args.expected_epoch,
        "checksum": "45AEAAAE",
        "full_per_step_count_fields_compared": len(COMPARE_FIELDS) * steps,
        "cycle_different_steps": differing_cycles,
        "max_absolute_cycle_delta": max_cycle_delta,
        "max_latency_cycles": captured["MAX_LATENCY"],
        "missed_steps": 0,
        "summary_sha256": hashlib.sha256(summary_path.read_bytes()).hexdigest().upper(),
    }
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
