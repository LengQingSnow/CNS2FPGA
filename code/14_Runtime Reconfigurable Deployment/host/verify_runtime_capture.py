"""Check a runtime-JTAG capture against a fixed-CPU step-count reference."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


def read_registers(path: Path) -> dict[str, int]:
    with path.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    if not rows or any(set(row) != {"name", "hex32"} for row in rows):
        raise ValueError(f"Invalid register capture: {path}")
    return {row["name"]: int(row["hex32"], 16) for row in rows}


def read_words(path: Path) -> list[int]:
    with path.open(encoding="utf-8") as stream:
        lines = [line.strip() for line in stream if line.strip()]
    if any(len(line) != 8 for line in lines):
        raise ValueError(f"Malformed hex word in {path}")
    return [int(line, 16) for line in lines]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture-dir", type=Path, required=True)
    parser.add_argument("--reference-summary", type=Path, required=True)
    parser.add_argument("--expected-checksum", required=True)
    parser.add_argument("--expected-epoch", type=int, required=True)
    parser.add_argument("--expected-neurons", type=int, required=True)
    parser.add_argument("--expected-synapses", type=int, required=True)
    event_reference = parser.add_mutually_exclusive_group()
    event_reference.add_argument("--expected-events", type=Path)
    event_reference.add_argument("--expected-spike-mem", type=Path)
    args = parser.parse_args()

    registers = read_registers(args.capture_dir / "registers.csv")
    with args.reference_summary.open(newline="", encoding="utf-8") as stream:
        reference = list(csv.DictReader(stream))
    if not reference:
        raise ValueError(f"Empty reference: {args.reference_summary}")
    count_column = "spikes" if "spikes" in reference[0] else "total"
    if count_column not in reference[0]:
        raise ValueError("Reference needs a 'spikes' or 'total' count column")
    words = read_words(args.capture_dir / "summary_words.hex")
    steps = len(reference)
    if len(words) != 8 * steps:
        raise AssertionError(f"Summary length {len(words)} != {8 * steps}")

    required = {
        "ID": 0x434E5352,
        "IMAGE_STATUS": 1,
        "IMAGE_CHECKSUM": int(args.expected_checksum, 16),
        "IMAGE_EPOCH": args.expected_epoch,
        "ACTIVE_NEURONS": args.expected_neurons,
        "ACTIVE_SYNAPSES": args.expected_synapses,
        "COMPLETED_STEPS": steps,
        "MISSED_STEPS": 0,
    }
    for name, expected in required.items():
        actual = registers[name]
        if actual != expected:
            raise AssertionError(f"{name}: {actual:#x} != {expected:#x}")
    if registers["STATUS"] & 0x1F != 0x2:
        raise AssertionError(f"Trial status not cleanly done: {registers['STATUS']:#x}")
    if registers["MAX_LATENCY"] > 200_000:
        raise AssertionError(f"Exceeded 1 ms at 200 MHz: {registers['MAX_LATENCY']}")

    mismatches: list[str] = []
    for index, row in enumerate(reference):
        if int(row["timestep"]) != index:
            raise ValueError(f"Reference timestep not contiguous at {index}")
        observed = words[index * 8 + 2] & 0xFFFF
        expected = int(row[count_column])
        if observed != expected:
            mismatches.append(f"step {index}: observed {observed}, expected {expected}")
        flags = words[index * 8 + 5] & 0xF
        if flags:
            mismatches.append(f"step {index}: fault/deadline flags {flags:#x}")

    compared_events = 0
    if args.expected_events or args.expected_spike_mem:
        events = read_words(args.capture_dir / "event_words.hex")
        observed_events: list[tuple[int, int]] = []
        for index in range(steps):
            start = words[index * 8 + 6]
            count = words[index * 8 + 5] >> 16
            if start + count > len(events):
                mismatches.append(f"step {index}: event slice out of range")
                break
            observed_events.extend((index, word & 0x1FFF) for word in events[start : start + count])
        if args.expected_events:
            with args.expected_events.open(newline="", encoding="utf-8") as stream:
                expected_rows = list(csv.DictReader(stream))
            expected_pairs = [
                (int(row["timestep"]), int(row["neuron_index"]))
                for row in expected_rows
            ]
        else:
            with args.expected_spike_mem.open(encoding="utf-8") as stream:
                spike_bits = [line.strip() for line in stream if line.strip()]
            expected_bit_count = steps * args.expected_neurons
            if len(spike_bits) != expected_bit_count or any(bit not in {"0", "1"} for bit in spike_bits):
                raise ValueError(f"Expected {expected_bit_count} binary spike bits")
            expected_pairs = [
                (index // args.expected_neurons, index % args.expected_neurons)
                for index, bit in enumerate(spike_bits) if bit == "1"
            ]
        compared_events = len(expected_pairs)
        if observed_events != expected_pairs:
            mismatches.append(
                f"ordered events differ: observed {len(observed_events)}, expected {len(expected_pairs)}"
            )
    if mismatches:
        raise AssertionError("; ".join(mismatches[:12]))
    result = {
        "status": "PASS",
        "steps": steps,
        "image_epoch": args.expected_epoch,
        "image_checksum": args.expected_checksum.upper(),
        "max_latency_cycles": registers["MAX_LATENCY"],
        "ordered_events_compared": compared_events,
    }
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
