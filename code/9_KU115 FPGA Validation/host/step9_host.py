"""Prepare locked Step 9 stimuli and compare captured FPGA results offline.

No JTAG access is performed here. A board transport can consume the two-word
little-endian stimulus stream and emit the documented CSV capture formats.
"""

from __future__ import annotations

import argparse
import contextlib
import csv
import hashlib
import io
import json
import math
from pathlib import Path
import shutil
import struct
import sys
import tempfile


WORKSPACE = Path(__file__).resolve().parents[3]
CODE = WORKSPACE / "code"
STEP8 = CODE / "8_RTL Bit-Exact Co-Simulation"
REFERENCE = STEP8 / "sim" / "reference" / "full_network_8step_v1"
SMOKE_CONFIG = STEP8 / "configs" / "full_network_8step_v1.json"
V1_CONFIG = CODE / "4_Verify whether this model has basic biological plausibility" / "configs" / "courtship_song_equal_pulse_v1.json"
FIXED_CONFIG = CODE / "5_Fixed-Point Quantization Analysis" / "configs" / "courtship_song_fixed_point_v6_final.json"
FIXED_POPULATION = CODE / "5_Fixed-Point Quantization Analysis" / "outputs" / "courtship_song_fixed_point_v6_final" / "population_comparison.csv"
STATE_BITS = 34
STATE_FRAC = 24
NEURONS = 6279
DT_MS = 1


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def quantize_current(value: float) -> int:
    """Match Step 5's round-to-nearest, ties-away-from-zero conversion."""
    value = float(value)
    if not math.isfinite(value):
        raise ValueError("Current must be finite")
    scaled = value * (1 << STATE_FRAC)
    raw = math.floor(abs(scaled) + 0.5)
    raw = -raw if scaled < 0 else raw
    if not -(1 << (STATE_BITS - 1)) <= raw < (1 << (STATE_BITS - 1)):
        raise ValueError(f"Current {value} is outside signed {STATE_BITS}-bit range")
    return raw


def encode_words(raw: int) -> tuple[int, int]:
    twos = raw & ((1 << STATE_BITS) - 1)
    return twos & 0xFFFFFFFF, (twos >> 32) & 0x3


def assert_locked_format() -> None:
    config = load_json(FIXED_CONFIG)
    fmt = next(item for item in config["formats"] if item["name"] == "safe_wf24")
    if fmt["state_bits"] != STATE_BITS or fmt["state_frac"] != STATE_FRAC:
        raise ValueError("Locked safe_wf24 format changed")
    reference = load_json(REFERENCE / "reference_manifest.json")
    if reference["neurons"] != NEURONS or reference["fixed_format"] != fmt:
        raise ValueError("Step 8 reference no longer matches the locked format/network")
    hashes = load_json(REFERENCE / "artifact_sha256.json")
    for name in ("stimulus.mem", "expected_spike.mem"):
        if sha256(REFERENCE / name) != hashes[name]:
            raise ValueError(f"Step 8 reference file changed: {name}")


def exact_steps(value: float, field: str) -> int:
    integer = round(float(value) / DT_MS)
    if not math.isfinite(float(value)) or integer < 0 or not math.isclose(integer * DT_MS, value, abs_tol=1e-9):
        raise ValueError(f"{field} must be a nonnegative integer multiple of {DT_MS} ms")
    return integer


def smoke_trial() -> tuple[str, list[float], dict]:
    config = load_json(SMOKE_CONFIG)
    values = [float(v) for v in config["stimulus"]]
    if len(values) != 8:
        raise ValueError("Locked smoke reference is not 8 steps")
    return "smoke8", values, {"profile": "smoke8", "reference": "full_network_8step_v1"}


def ipi_trials(selected: int | None) -> list[tuple[str, list[float], dict]]:
    protocol = load_json(V1_CONFIG)["protocol"]
    ipis = [exact_steps(v, "IPI") for v in protocol["ipi_ms"]]
    if selected is not None and selected not in ipis:
        raise ValueError(f"IPI must be one of {ipis}")
    start = exact_steps(protocol["start_ms"], "start")
    width = exact_steps(protocol["pulse_width_ms"], "pulse width")
    tail = exact_steps(protocol["tail_ms"], "tail")
    count = int(protocol["pulse_count"])
    if count != 40 or width != 3 or start != 100 or tail != 500:
        raise ValueError("Locked Step 4 IPI protocol changed; review before using hardware")
    duration = start + (count - 1) * max(ipis) + width + tail
    if duration != 4308:
        raise ValueError("Locked trial duration changed")
    result = []
    for ipi in ipis:
        if selected is not None and ipi != selected:
            continue
        onsets = [start + n * ipi for n in range(count)]
        current = [0.0] * duration
        for onset in onsets:
            current[onset:onset + width] = [float(protocol["amplitude"])] * width
        meta = {
            "profile": "ipi_v1", "ipi_ms": ipi, "pulse_count": count,
            "pulse_width_ms": width, "pulse_onsets_ms": onsets,
            "response_start_ms": start, "train_end_ms": onsets[-1] + width,
            "response_end_ms": onsets[-1] + width + tail,
            "amplitude": float(protocol["amplitude"]),
        }
        result.append((f"ipi_{ipi:02d}", current, meta))
    return result


def write_trial(base: Path, name: str, values: list[float], details: dict) -> dict:
    target = base / name
    if target.exists() and any(target.iterdir()):
        raise FileExistsError(f"Refusing to overwrite nonempty trial directory: {target}")
    target.mkdir(parents=True, exist_ok=True)
    raw_values = [quantize_current(value) for value in values]
    with (target / "stimulus.mem").open("w", encoding="ascii", newline="\n") as mem, \
            (target / "stimulus_words.bin").open("wb") as binary, \
            (target / "stimulus_words.csv").open("w", encoding="ascii", newline="") as csv_file:
        writer = csv.writer(csv_file, lineterminator="\n")
        writer.writerow(("timestep", "raw34_hex", "low32_hex", "high2_hex"))
        for step, raw in enumerate(raw_values):
            low, high = encode_words(raw)
            mem.write(f"{raw & ((1 << STATE_BITS) - 1):09X}\n")
            binary.write(struct.pack("<II", low, high))
            writer.writerow((step, f"{raw & ((1 << STATE_BITS) - 1):09X}", f"{low:08X}", f"{high:01X}"))
    if details["profile"] == "smoke8":
        if sha256(target / "stimulus.mem") != sha256(REFERENCE / "stimulus.mem"):
            raise ValueError("Generated 8-step stimulus differs from the locked Step 8 bytes")
        shutil.copyfile(REFERENCE / "expected_spike.mem", target / "expected_spike.mem")
        shutil.copyfile(REFERENCE / "reference_summary.csv", target / "reference_summary.csv")
    metadata = {
        "schema": "cns2fpga.step9.stimulus", "schema_version": 1,
        "trial": name, "network_neurons": NEURONS, "dt_ms": DT_MS,
        "timesteps": len(values), "input_current_encoding": {
            "signed": True, "bits": STATE_BITS, "frac_bits": STATE_FRAC,
            "rounding": "nearest_ties_away_from_zero",
            "word_order": "low32_then_high2", "binary_word_endianness": "little",
            "binary_words_per_timestep": 2,
        },
        "details": details,
        "source_sha256": {str(path.relative_to(WORKSPACE)): sha256(path) for path in
                          (SMOKE_CONFIG, V1_CONFIG, FIXED_CONFIG, REFERENCE / "reference_manifest.json")},
        "artifact_sha256": {path.name: sha256(path) for path in target.iterdir() if path.is_file()},
    }
    (target / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"trial": name, "timesteps": len(values), "directory": str(target),
            "stimulus_sha256": metadata["artifact_sha256"]["stimulus.mem"]}


def generate(args: argparse.Namespace) -> int:
    assert_locked_format()
    base = args.output_dir.resolve()
    trials = [smoke_trial()] if args.profile == "smoke8" else ipi_trials(args.ipi_ms)
    collision = [str(base / name) for name, _, _ in trials if (base / name).exists() and any((base / name).iterdir())]
    if collision:
        raise FileExistsError("Refusing to overwrite: " + ", ".join(collision))
    result = [write_trial(base, *trial) for trial in trials]
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def read_events(path: Path, steps: int, neurons: int) -> list[tuple[int, int]]:
    events = []
    with path.open("r", encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        if not reader.fieldnames or not {"timestep", "neuron_index"}.issubset(reader.fieldnames):
            raise ValueError("Events CSV requires timestep,neuron_index columns")
        for line, row in enumerate(reader, start=2):
            step, neuron = int(row["timestep"]), int(row["neuron_index"])
            if not (0 <= step < steps and 0 <= neuron < neurons):
                raise ValueError(f"Event out of range at CSV line {line}: {step},{neuron}")
            events.append((step, neuron))
    return events


def expected_events(path: Path, steps: int, neurons: int) -> list[tuple[int, int]]:
    events = []
    count = 0
    with path.open("r", encoding="ascii") as source:
        for count, text in enumerate(source, start=1):
            value = text.strip()
            if value not in ("0", "1"):
                raise ValueError(f"Unexpected expected_spike.mem value at line {count}")
            if value == "1":
                events.append(((count - 1) // neurons, (count - 1) % neurons))
    if count != steps * neurons:
        raise ValueError(f"Expected {steps * neurons} spike bits, got {count}")
    return events


def compare_events(args: argparse.Namespace) -> int:
    assert_locked_format()
    expected = expected_events(args.expected_mem or REFERENCE / "expected_spike.mem", 8, NEURONS)
    actual = read_events(args.events, 8, NEURONS)
    first = next(((index, exp, got) for index, (exp, got) in enumerate(zip(expected, actual)) if exp != got), None)
    if first is None and len(expected) != len(actual):
        index = min(len(expected), len(actual))
        first = (index, expected[index] if index < len(expected) else None,
                 actual[index] if index < len(actual) else None)
    passed = first is None
    print(json.dumps({"pass": passed, "comparison": "ordered_event_sequence",
                      "expected_events": len(expected), "actual_events": len(actual),
                      "first_difference": first}, indent=2))
    return 0 if passed else 1


def compare_groups(args: argparse.Namespace) -> int:
    assert_locked_format()
    selected = ipi_trials(args.ipi_ms)
    if len(selected) != 1:
        raise ValueError("Specify one locked IPI")
    _, values, details = selected[0]
    with FIXED_POPULATION.open("r", encoding="utf-8-sig", newline="") as source:
        candidates = [row for row in csv.DictReader(source) if row["format_name"] == "safe_wf24"
                      and row["condition_id"] == "intact" and float(row["ipi_ms"]) == args.ipi_ms]
    expected = {row["group"]: int(float(row["fixed_response_spikes"])) for row in candidates}
    if set(expected) != {"vPN1", "pC1", "pIP10", "pMP2"}:
        raise ValueError("Missing locked fixed-point population reference groups")
    totals = {group: 0 for group in expected}
    diagnostic = ("state_saturation", "accumulator_saturation", "deadline_miss", "event_overflow")
    bad_flags = {name: 0 for name in diagnostic}
    with args.counts.open("r", encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        if not reader.fieldnames or not ({"timestep"} | set(expected)).issubset(reader.fieldnames):
            raise ValueError("Counts CSV requires timestep,vPN1,pC1,pIP10,pMP2 columns")
        line_count = 0
        for line_count, row in enumerate(reader, start=1):
            step = int(row["timestep"])
            if step != line_count - 1:
                raise ValueError(f"Counts must cover contiguous timesteps: row {line_count} has {step}")
            for group in expected:
                value = int(row[group])
                if value < 0:
                    raise ValueError(f"Negative count at timestep {step}, {group}")
                if details["response_start_ms"] <= step < details["response_end_ms"]:
                    totals[group] += value
            for flag in diagnostic:
                if flag in reader.fieldnames:
                    bad_flags[flag] += int(row[flag])
    if line_count != len(values):
        raise ValueError(f"Counts need {len(values)} timesteps; got {line_count}")
    passed = totals == expected and all(value == 0 for value in bad_flags.values())
    print(json.dumps({"pass": passed, "ipi_ms": args.ipi_ms,
                      "response_window_ms": [details["response_start_ms"], details["response_end_ms"]],
                      "fixed_response_spikes": expected, "board_response_spikes": totals,
                      "diagnostic_flag_sums": bad_flags}, indent=2))
    return 0 if passed else 1


def read_hex_words(path: Path) -> list[int]:
    words = []
    with path.open("r", encoding="ascii") as source:
        for line, text in enumerate(source, start=1):
            word = text.strip()
            if len(word) != 8 or any(c not in "0123456789abcdefABCDEF" for c in word):
                raise ValueError(f"Expected one 8-digit hex word at {path}:{line}")
            words.append(int(word, 16))
    return words


def decode_summary(words: list[int], timesteps: int, period_cycles: int) -> list[dict]:
    if len(words) != timesteps * 8:
        raise ValueError(f"Expected {timesteps * 8} summary words; got {len(words)}")
    rows = []
    for step in range(timesteps):
        cycles, synops, total_apn1, pc1_vpn1, pmp2_pip10, events_flags, event_start, reserved = words[step * 8:step * 8 + 8]
        if reserved != 0:
            raise ValueError(f"Summary reserved word must be zero at step {step}")
        total = total_apn1 & 0xFFFF
        row = {
            "timestep": step, "cycles": cycles, "synops": synops,
            "total": total, "aPN1": total_apn1 >> 16,
            "vPN1": pc1_vpn1 & 0xFFFF, "pC1": pc1_vpn1 >> 16,
            "pIP10": pmp2_pip10 & 0xFFFF, "pMP2": pmp2_pip10 >> 16,
            "event_count": events_flags >> 16, "flags": events_flags & 0xFFFF,
            "event_start": event_start,
            "state_saturation": events_flags & 0x1,
            "accumulator_saturation": (events_flags >> 1) & 0x1,
            "deadline_miss": int(bool((events_flags >> 2) & 0x1) or cycles > period_cycles),
            "event_overflow": (events_flags >> 3) & 0x1,
        }
        if any(row[group] > total for group in ("aPN1", "vPN1", "pC1", "pIP10", "pMP2")):
            raise ValueError(f"A group count exceeds total at step {step}")
        rows.append(row)
    return rows


def parse_dump(args: argparse.Namespace) -> int:
    summary = read_hex_words(args.summary_words)
    rows = decode_summary(summary, args.timesteps, args.period_cycles)
    target = args.output_dir.resolve()
    if target.exists() and any(target.iterdir()):
        raise FileExistsError(f"Refusing to overwrite nonempty capture directory: {target}")
    target.mkdir(parents=True, exist_ok=True)
    counts_path = target / "counts.csv"
    with counts_path.open("w", encoding="ascii", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    event_total = 0
    if args.event_words is not None:
        event_words = read_hex_words(args.event_words)
        # Captured events are stored in a global linear event buffer. The
        # per-step start/count pair is authoritative for reconstructing time.
        next_start = 0
        with (target / "events.csv").open("w", encoding="ascii", newline="") as stream:
            writer = csv.writer(stream, lineterminator="\n")
            writer.writerow(("timestep", "neuron_index"))
            for row in rows:
                start, count = row["event_start"], row["event_count"]
                if start != next_start or start + count > len(event_words):
                    raise ValueError(f"Invalid event span at step {row['timestep']}: {start}+{count}")
                for word in event_words[start:start + count]:
                    if word >= NEURONS:
                        raise ValueError(f"Event neuron index outside network: {word}")
                    writer.writerow((row["timestep"], word))
                next_start += count
            if next_start != len(event_words):
                raise ValueError(f"Unused trailing event words: {len(event_words) - next_start}")
            event_total = next_start
    result = {
        "schema": "cns2fpga.step9.capture", "schema_version": 1,
        "timesteps": args.timesteps, "period_cycles": args.period_cycles,
        "max_latency_cycles": max(row["cycles"] for row in rows),
        "deadline_miss_steps_by_cycle_count": sum(row["deadline_miss"] for row in rows),
        "event_words_parsed": event_total,
        "summary_words_sha256": sha256(args.summary_words),
        "event_words_sha256": sha256(args.event_words) if args.event_words else None,
        "counts_csv_sha256": sha256(counts_path),
    }
    (target / "capture_metadata.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output_dir": str(target), **result}, indent=2))
    return 0


def selftest(_: argparse.Namespace) -> int:
    assert_locked_format()
    assert encode_words(quantize_current(1.2)) == (0x01333333, 0)
    assert encode_words(quantize_current(-1.2)) == (0xFECCCCCD, 3)
    with tempfile.TemporaryDirectory(prefix="cns2fpga_host_") as folder:
        base = Path(folder)
        write_trial(base, *smoke_trial())
        for trial in ipi_trials(None):
            write_trial(base, *trial)
        for ipi in (15, 25, 35, 45, 55, 65, 75, 85, 95):
            meta = load_json(base / f"ipi_{ipi:02d}" / "metadata.json")
            raw = (base / f"ipi_{ipi:02d}" / "stimulus_words.bin").read_bytes()
            if meta["timesteps"] != 4308 or len(raw) != 4308 * 8:
                raise AssertionError("IPI file length mismatch")
            decoded = [struct.unpack_from("<II", raw, i * 8) for i in range(4308)]
            if sum(pair != (0, 0) for pair in decoded) != 120:
                raise AssertionError("IPI pulse count/width mismatch")
        expected = expected_events(base / "smoke8" / "expected_spike.mem", 8, NEURONS)
        event_path = base / "events.csv"
        with event_path.open("w", encoding="ascii", newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow(("timestep", "neuron_index"))
            writer.writerows(expected)
        if read_events(event_path, 8, NEURONS) != expected:
            raise AssertionError("Event parser roundtrip mismatch")
        synthetic = decode_summary([100, 200, (2 << 16) | 10, (4 << 16) | 3,
                                    (1 << 16) | 1, (10 << 16), 0, 0], 1, 195000)[0]
        if (synthetic["total"], synthetic["aPN1"], synthetic["vPN1"], synthetic["pC1"],
                synthetic["pIP10"], synthetic["pMP2"], synthetic["event_count"]) != (10, 2, 3, 4, 1, 1, 10):
            raise AssertionError("Summary decoding mismatch")
        summary_words = base / "summary_words.hex"
        summary_words.write_text("\n".join(f"{word:08X}" for word in
                                           (100, 200, (2 << 16) | 10, (4 << 16) | 3,
                                            (1 << 16) | 1, (1 << 16), 0, 0)) + "\n", encoding="ascii")
        event_words = base / "event_words.hex"
        event_words.write_text("0000002A\n", encoding="ascii")
        parsed = base / "parsed"
        with contextlib.redirect_stdout(io.StringIO()):
            parse_dump(argparse.Namespace(summary_words=summary_words, event_words=event_words,
                                          timesteps=1, period_cycles=195000, output_dir=parsed))
        if read_events(parsed / "events.csv", 1, NEURONS) != [(0, 42)]:
            raise AssertionError("AXI event dump parsing mismatch")
    print(json.dumps({"pass": True, "smoke8": "byte-identical to Step 8 stimulus.mem",
                      "ipi_trials": 9, "steps_per_ipi": 4308,
                      "events_in_smoke_reference": len(expected)}, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    make = sub.add_parser("generate", help="Generate immutable trial input files")
    make.add_argument("--profile", choices=("smoke8", "ipi"), required=True)
    make.add_argument("--ipi-ms", type=int, help="For IPI: select one; omit for all nine")
    make.add_argument("--output-dir", type=Path, required=True)
    make.set_defaults(action=generate)
    events = sub.add_parser("compare-events", help="Exact ordered Step 8 spike-event comparison")
    events.add_argument("--events", type=Path, required=True)
    events.add_argument("--expected-mem", type=Path)
    events.set_defaults(action=compare_events)
    groups = sub.add_parser("compare-groups", help="Compare IPI response-window group counts")
    groups.add_argument("--counts", type=Path, required=True)
    groups.add_argument("--ipi-ms", type=int, required=True)
    groups.set_defaults(action=compare_groups)
    capture = sub.add_parser("parse-dump", help="Decode board summary/event AXI word dumps")
    capture.add_argument("--summary-words", type=Path, required=True)
    capture.add_argument("--event-words", type=Path)
    capture.add_argument("--timesteps", type=int, required=True)
    capture.add_argument("--period-cycles", type=int, default=200000)
    capture.add_argument("--output-dir", type=Path, required=True)
    capture.set_defaults(action=parse_dump)
    sub.add_parser("selftest", help="Validate stimulus encoding and reference formats").set_defaults(action=selftest)
    args = parser.parse_args()
    if args.command == "generate" and args.profile == "smoke8" and args.ipi_ms is not None:
        parser.error("--ipi-ms applies only to --profile ipi")
    if args.command == "parse-dump" and (args.timesteps < 1 or args.period_cycles < 1):
        parser.error("--timesteps and --period-cycles must be positive")
    try:
        return args.action(args)
    except (ValueError, FileNotFoundError, FileExistsError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
