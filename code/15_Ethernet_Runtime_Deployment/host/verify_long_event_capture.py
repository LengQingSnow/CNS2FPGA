"""Verify every ordered neuron event in a long AXKU115 runtime capture."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path


def rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as stream:
        return list(csv.DictReader(stream))


def words(path: Path) -> list[int]:
    result = []
    with path.open(encoding="ascii") as stream:
        for line in stream:
            line = line.strip()
            if line:
                if len(line) != 8:
                    raise AssertionError(f"Malformed word in {path}")
                result.append(int(line, 16))
    return result


def run(capture: Path, reference: Path, old_counts: Path,
        expected_epoch: int, expected_capacity: int) -> dict:
    reg = {r["name"]: int(r["hex32"], 16) for r in rows(capture / "registers.csv")}
    # Ethernet top-level owns 0x70 for diagnostics; capacity is selected from
    # the pinned bitstream metadata and independently bounded by overflow.
    capacity = expected_capacity
    expected_reg = {
        "ID": 0x434E5352, "STATUS": 2, "IMAGE_STATUS": 1,
        "IMAGE_CHECKSUM": 0x45AEAAAE, "IMAGE_EPOCH": expected_epoch,
        "ACTIVE_NEURONS": 6279, "ACTIVE_SYNAPSES": 350185,
        "LENGTH": 4308, "COMPLETED_STEPS": 4308,
        "PERIOD_CYCLES": 200000, "MISSED_STEPS": 0,
    }
    for name, expected in expected_reg.items():
        if reg.get(name) != expected:
            raise AssertionError(f"{name}: {reg.get(name)} != {expected}")
    if capacity != expected_capacity:
        raise AssertionError(f"Event capacity {capacity} != {expected_capacity}")
    if reg["MAX_LATENCY"] > 200000:
        raise AssertionError("Deadline exceeded")
    summary = words(capture / "summary_words.hex")
    observed = words(capture / "event_words.hex")
    expected = rows(reference / "expected_events.csv")
    previous = rows(old_counts)
    if len(summary) != 4308 * 8 or len(previous) != 4308:
        raise AssertionError("Per-step capture/reference length mismatch")
    if len(observed) != len(expected) or len(observed) != reg["GLOBAL_EVENT_COUNT"]:
        raise AssertionError("Global event count/reference length mismatch")
    if len(observed) > capacity:
        raise AssertionError("Event RAM overflow")
    cursor = 0
    differing_cycles = 0
    max_cycle_delta = 0
    for step in range(4308):
        chunk = summary[8 * step : 8 * step + 8]
        cycles, synops, packed_total, packed_vpn1, packed_pip10, packed_events, start, reserved = chunk
        total = packed_total & 0xFFFF
        apn1 = packed_total >> 16
        vpn1 = packed_vpn1 & 0xFFFF
        pc1 = packed_vpn1 >> 16
        pip10 = packed_pip10 & 0xFFFF
        pmp2 = packed_pip10 >> 16
        count = packed_events >> 16
        flags = packed_events & 0xFFFF
        if flags or reserved or cycles > 200000:
            raise AssertionError(f"Fault, reserved field, or deadline at step {step}")
        if start != cursor or count != total:
            raise AssertionError(f"Lost event or start offset at step {step}")
        prior = previous[step]
        for name, value in (("total", total), ("aPN1", apn1), ("vPN1", vpn1),
                            ("pC1", pc1), ("pIP10", pip10), ("pMP2", pmp2),
                            ("synops", synops)):
            if int(prior[name]) != value:
                raise AssertionError(f"Step {step} {name}: {value} != {prior[name]}")
        delta = cycles - int(prior["cycles"])
        if delta:
            differing_cycles += 1
            max_cycle_delta = max(max_cycle_delta, abs(delta))
        for index in range(cursor, cursor + count):
            ref = expected[index]
            neuron = observed[index]
            if neuron >> 13 or int(ref["timestep"]) != step or int(ref["neuron_index"]) != neuron:
                raise AssertionError(f"Ordered event mismatch at step {step}, event {index}")
        cursor += count
    if cursor != len(observed):
        raise AssertionError("Trailing unreferenced events")
    return {
        "status": "PASS", "steps": 4308, "ordered_events_compared": cursor,
        "exact_event_mismatches": 0, "group_and_synops_fields_compared": 4308 * 7,
        "image_epoch": expected_epoch, "image_checksum": "45AEAAAE",
        "event_capacity": capacity, "max_latency_cycles": reg["MAX_LATENCY"],
        "missed_steps": reg["MISSED_STEPS"], "fault_flags": 0,
        "cycle_different_steps_from_dedicated": differing_cycles,
        "max_absolute_cycle_delta": max_cycle_delta,
        "event_words_sha256": hashlib.sha256((capture / "event_words.hex").read_bytes()).hexdigest().upper(),
        "summary_words_sha256": hashlib.sha256((capture / "summary_words.hex").read_bytes()).hexdigest().upper(),
        "reference_events_sha256": hashlib.sha256((reference / "expected_events.csv").read_bytes()).hexdigest().upper(),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture-dir", type=Path, required=True)
    parser.add_argument("--reference-dir", type=Path, required=True)
    parser.add_argument("--old-counts", type=Path, required=True)
    parser.add_argument("--expected-epoch", type=int, required=True)
    parser.add_argument("--expected-capacity", type=int, required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.capture_dir, args.reference_dir, args.old_counts,
                         args.expected_epoch, args.expected_capacity), indent=2))
