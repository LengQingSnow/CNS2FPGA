"""Recheck the archived 100-Mbps courtship trial without connecting to a board."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import shutil
from pathlib import Path


STEP = Path(__file__).resolve().parents[1]
PROJECT = STEP.parents[1]
RAW = STEP / "reports" / "expanded_bit_100m_20261001"
REFERENCE = PROJECT / "code" / "8_RTL Bit-Exact Co-Simulation" / "sim" / "reference" / "full_network_8step_v1"
BIT_SHA = "D4C9378D461147062FA5DC590CB3647D241C789B01CC6255F38DA16CB21990DF"
OUTPUT = STEP / "reports" / "expanded_bit_100m_audit_v1.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def words(path: Path) -> list[int]:
    values = path.read_text(encoding="ascii").split()
    if any(not re.fullmatch(r"[0-9A-Fa-f]{8}", value) for value in values):
        raise ValueError(f"Malformed word in {path}")
    return [int(value, 16) for value in values]


def import_local() -> None:
    """Copy immutable capture bytes and make narrowly selected public log excerpts."""
    source = STEP / "build" / "new_bit_100m_smoke8_20261001"
    (RAW / "board").mkdir(parents=True, exist_ok=True)
    (RAW / "logs").mkdir(exist_ok=True)
    for name in ("registers.csv", "event_words.hex", "summary_words.hex"):
        target = RAW / "board" / name
        if target.exists() and target.read_bytes() != (source / name).read_bytes():
            raise RuntimeError(f"Refusing to replace a different capture: {target}")
        shutil.copy2(source / name, target)
    excerpts = {
        "status_repeat.log": ("new_bit_100m_status_repeat_20261001.log", r"^(ITER=|PASS_COUNT=)"),
        "upload.log": ("new_bit_100m_courtship_upload_20261001.log", r"^(PREFLIGHT |ETHERNET_IMAGE_COMMIT_PASS )"),
        "ready.log": ("new_bit_100m_post_upload_status_seq_20261001.log", r"^ETHERNET_STATUS_PASS "),
        "diag.log": ("new_bit_100m_post_trial_diag_20261001.log", r"^ETH_DIAG_(ID|STATUS|RX_COUNTS|TX_COUNTS|ERROR_COUNTS|RX_CLOCK_[AB]|RX_CLOCK_CHANGED)="),
        "link.log": ("new_bit_100m_set_speed_20261001.log", r"^AB_SPEED_"),
        "restore.log": ("new_bit_100m_host_restore_20261001.log", r"^(ETHERNET_ADDRESS_RESTORED|AB_SPEED_|AB_HOST_RESTORED)"),
        "program.log": ("new_bit_100m_program_20261001.log", r"^RUNTIME_ETH_PROGRAM_PASS"),
    }
    for name, (original, pattern) in excerpts.items():
        path = STEP / "reports" / original
        lines = [line for line in path.read_text(encoding="utf-8", errors="replace").splitlines()
                 if re.search(pattern, line)]
        if not lines:
            raise RuntimeError(f"No evidence lines in {path}")
        if name == "program.log":
            lines = ["RUNTIME_ETH_PROGRAM_PASS" for _ in lines]
        text = f"# Selected public excerpt; complete original log retained locally.\n# Original SHA-256: {sha(path)}\n" + "\n".join(lines) + "\n"
        (RAW / "logs" / name).write_text(text, encoding="utf-8")


def audit() -> dict:
    board = RAW / "board"
    with (board / "registers.csv").open(newline="", encoding="ascii") as stream:
        reg = {row["name"]: int(row["hex32"], 16) for row in csv.DictReader(stream)}
    required = {"ID": 0x434E5352, "STATUS": 2, "LENGTH": 8, "PERIOD_CYCLES": 200000,
                "COMPLETED_STEPS": 8, "GLOBAL_EVENT_COUNT": 2475, "MISSED_STEPS": 0,
                "IMAGE_STATUS": 1, "IMAGE_CHECKSUM": 0x45AEAAAE, "IMAGE_EPOCH": 1,
                "ACTIVE_NEURONS": 6279, "ACTIVE_SYNAPSES": 350185}
    for key, expected in required.items():
        if reg.get(key) != expected:
            raise AssertionError(f"{key}: {reg.get(key)} != {expected}")
    summary, events = words(board / "summary_words.hex"), words(board / "event_words.hex")
    bits = (REFERENCE / "expected_spike.mem").read_text(encoding="ascii").split()
    if len(summary) != 64 or len(events) != 2475 or len(bits) != 8 * 6279 or set(bits) != {"0", "1"}:
        raise AssertionError("Unexpected capture/reference size or spike encoding")
    expected = [(i // 6279, i % 6279) for i, bit in enumerate(bits) if bit == "1"]
    observed, per_step, offset = [], [], 0
    with (REFERENCE / "reference_summary.csv").open(newline="", encoding="ascii") as stream:
        cpu = list(csv.DictReader(stream))
    if len(cpu) != 8:
        raise AssertionError("CPU summary length differs")
    for step in range(8):
        row = summary[step * 8:(step + 1) * 8]
        count, start, total, flags = row[5] >> 16, row[6], row[2] & 0xFFFF, row[5] & 0xFFFF
        if start != offset or count != total or flags or row[0] > 200000:
            raise AssertionError(f"Bad event range, flags or deadline at step {step}")
        slice_words = events[start:start + count]
        if len(slice_words) != count or any(word >= 6279 for word in slice_words):
            raise AssertionError(f"Invalid event words at step {step}")
        observed.extend((step, word) for word in slice_words)
        if int(cpu[step]["timestep"]) != step or int(cpu[step]["spikes"]) != total:
            raise AssertionError(f"CPU count differs at step {step}")
        per_step.append({"timestep": step, "cpu_spikes": total, "board_spikes": total,
                         "cycles": row[0], "event_start": start, "flags": flags})
        offset += count
    if observed != expected or offset != len(events) or reg["MAX_LATENCY"] != max(row["cycles"] for row in per_step):
        raise AssertionError("Ordered events or maximum latency differ")
    logs = {path.stem: path.read_text(encoding="utf-8") for path in (RAW / "logs").glob("*.log")}
    probes = re.findall(r"ITER=(\d+) ETHERNET_STATUS_PASS .*attempt=(\d+) rtt_ms=([\d.]+)", logs["status_repeat"])
    if [int(p[0]) for p in probes] != list(range(1, 21)) or any(p[1] != "1" for p in probes):
        raise AssertionError("STATUS campaign differs from 20 first-attempt replies")
    if "words=738044 packets=11538 checksum=45AEAAAE" not in logs["upload"] or "ETHERNET_IMAGE_COMMIT_PASS words=738044 checksum=45AEAAAE" not in logs["upload"]:
        raise AssertionError("Upload identity differs")
    if "image_status=0x00000001" not in logs["ready"] or logs["program"].count("RUNTIME_ETH_PROGRAM_PASS") != 1:
        raise AssertionError("Image-ready or single-program evidence missing")
    if "setting=4 status=Up actual=100 Mbps" not in logs["link"] or "AB_HOST_RESTORED setting=6 ip=192.168.0.3/24 actual_link=100 Mbps" not in logs["restore"]:
        raise AssertionError("Measured link/host restoration evidence differs")
    diagnostic = {name: int(value, 16) for name, value in re.findall(r"ETH_DIAG_(\w+)=([0-9A-Fa-f]+)", logs["diag"])}
    if diagnostic["ID"] != 0x434E5352 or (diagnostic["STATUS"] >> 16) & 3 != 1 or diagnostic["ERROR_COUNTS"] != 0 or diagnostic["RX_COUNTS"] == 0:
        raise AssertionError("MAC link mode or receive error counters differ")
    bit = PROJECT / "hardware" / "bitstreams" / "cns2fpga_runtime_eth_long_events_200mhz.bit"
    if not bit.is_file():
        bit = STEP / "build" / "runtime_eth_long_events_retry_200mhz" / "cns2fpga_runtime_eth_long_events_retry_200mhz.bit"
    if sha(bit) != BIT_SHA:
        raise AssertionError("Bitstream hash differs")
    return {"schema": "cns2fpga.100m_board_audit.v1", "status": "PASS", "test_date": "2026-10-01",
            "board": "ALINX AXKU115 V1.0", "bitstream_sha256": BIT_SHA,
            "actual_link_mbps": 100, "core_frequency_hz": 200000000,
            "programming_operations_in_recorded_session": 1,
            "status_probes_passed": len(probes), "status_probes_total": 20,
            "status_rtt_ms": [float(p[2]) for p in probes],
            "upload_words": 738044, "upload_protocol_packets": 11538,
            "image_checksum": "45AEAAAE", "image_epoch": 1, "steps": 8,
            "ordered_events_compared": len(expected), "event_mismatches": 0,
            "max_latency_cycles": reg["MAX_LATENCY"], "period_cycles": 200000,
            "deadline_margin_cycles": 200000 - reg["MAX_LATENCY"], "missed_steps": 0,
            "fault_flags": 0, "bad_fcs_after_trial": diagnostic["ERROR_COUNTS"] & 0xFFFF,
            "good_rx_counter_after_trial": diagnostic["RX_COUNTS"] >> 16,
            "udp_rx_counter_after_trial": diagnostic["RX_COUNTS"] & 0xFFFF,
            "capture_sha256": {name: sha(board / name) for name in ("registers.csv", "event_words.hex", "summary_words.hex")},
            "cpu_reference_sha256": {name: sha(REFERENCE / name) for name in ("reference_summary.csv", "expected_spike.mem")},
            "per_step": per_step,
            "limits": "One measured 100-Mbps programming session and one eight-step trial; not a cold-boot reliability estimate. Prior 1-Gbps receive failures remain unresolved; cable capability is a hypothesis and further 1-Gbps tests are deferred."}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--import-local", action="store_true", help="archive the existing development capture and public log excerpts")
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    if args.import_local:
        import_local()
    result = audit()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"100M_AUDIT_PASS steps=8 ordered_events=2475 STATUS=20/20 bad_fcs=0 output={args.output}")


if __name__ == "__main__":
    main()
