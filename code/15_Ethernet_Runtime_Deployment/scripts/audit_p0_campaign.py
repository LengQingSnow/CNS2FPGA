"""Independently audit the physical P0 JTAG and Ethernet captures.

This script is offline: it never connects to, resets, or programs the board.
It re-runs the frozen trial validators, checks repeat-file identity, and
records exact scope and provenance in a compact JSON report.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
import sys
from pathlib import Path


CODE = Path(__file__).resolve().parents[2]
STEP9 = CODE / "9_KU115 FPGA Validation"
STEP12 = CODE / "12_Visual-to-Steering Circuit"
STEP14 = CODE / "14_Runtime Reconfigurable Deployment"
STEP15 = CODE / "15_Ethernet_Runtime_Deployment"
VISUAL_TRIAL = STEP12 / "outputs" / "visual_left_board_v0" / "trial"
SMOKE_TRIAL = STEP9 / "host" / "trials" / "smoke8"
BIT = STEP15 / "build" / "runtime_eth_portfilter_200mhz" / "cns2fpga_runtime_eth_portfilter_200mhz.bit"
BIT_SHA256 = "581354A62C8C7AEB134F300E7EA1928D8B681B996807710C61E307B33530D8F8"
JTAG_BIT = STEP14 / "build" / "runtime_jtag_200mhz" / "cns2fpga_runtime_jtag_200mhz.bit"
JTAG_BIT_SHA256 = "95F9B50EE03804DDC211828A9FBD3B3171B45BC3FFB79F9F3B2407F0D3190E52"
IPIS = (15, 35, 65)
FIELDS = ("total", "aPN1", "vPN1", "pC1", "pIP10", "pMP2", "event_count", "flags")


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest().upper()


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def run(*args: object) -> str:
    command = [sys.executable, *(str(arg) for arg in args)]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode:
        raise AssertionError(f"Validator failed: {' '.join(command)}\n{result.stdout}\n{result.stderr}")
    return result.stdout


def registers(capture: Path) -> dict[str, int]:
    with (capture / "registers.csv").open(newline="", encoding="ascii") as handle:
        return {row["name"]: int(row["hex32"], 16) for row in csv.DictReader(handle)}


def count_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def repeat_summary(first: Path, second: Path) -> dict[str, object]:
    a = [int(line, 16) for line in first.read_text(encoding="ascii").splitlines() if line]
    b = [int(line, 16) for line in second.read_text(encoding="ascii").splitlines() if line]
    check(len(a) == len(b) and len(a) % 8 == 0, "Repeat summary lengths differ")
    differences = []
    for step in range(len(a) // 8):
        check(a[step * 8 + 1:step * 8 + 8] == b[step * 8 + 1:step * 8 + 8],
              f"Repeat non-cycle summary mismatch at step {step}: {first} vs {second}")
        differences.append(abs(a[step * 8] - b[step * 8]))
    return {"steps": len(differences), "noncycle_words_equal": 7 * len(differences),
            "cycle_different_steps": sum(delta != 0 for delta in differences),
            "max_absolute_cycle_delta": max(differences, default=0),
            "whole_file_byte_identical": digest(first) == digest(second)}


def audit_short(capture: Path, kind: str, epoch: int) -> dict[str, object]:
    if kind == "visual":
        args = [
            "--reference-summary", VISUAL_TRIAL / "expected_counts.csv",
            "--expected-checksum", "6C233D31", "--expected-epoch", epoch,
            "--expected-neurons", 226, "--expected-synapses", 1730,
            "--expected-events", VISUAL_TRIAL / "expected_events.csv",
        ]
        steps, events = 250, 560
    elif kind == "courtship":
        args = [
            "--reference-summary", SMOKE_TRIAL / "reference_summary.csv",
            "--expected-checksum", "45AEAAAE", "--expected-epoch", epoch,
            "--expected-neurons", 6279, "--expected-synapses", 350185,
            "--expected-spike-mem", SMOKE_TRIAL / "expected_spike.mem",
        ]
        steps, events = 8, 2475
    else:
        raise ValueError(kind)
    run(STEP14 / "host" / "verify_runtime_capture.py", "--capture-dir", capture, *args)
    reg = registers(capture)
    check(reg["LENGTH"] == reg["COMPLETED_STEPS"] == steps, f"{capture}: steps")
    check(reg["GLOBAL_EVENT_COUNT"] == events, f"{capture}: events")
    check(reg["MISSED_STEPS"] == 0 and reg["MAX_LATENCY"] <= 200_000, f"{capture}: deadline")
    event_file = capture / "event_words.hex"
    summary_file = capture / "summary_words.hex"
    check(len(event_file.read_text(encoding="ascii").splitlines()) == events, f"{capture}: event lines")
    check(len(summary_file.read_text(encoding="ascii").splitlines()) == steps * 8,
          f"{capture}: summary lines")
    return {
        "steps": steps, "ordered_events": events, "epoch": reg["IMAGE_EPOCH"],
        "checksum": f"{reg['IMAGE_CHECKSUM']:08X}",
        "max_latency_cycles": reg["MAX_LATENCY"], "missed_steps": reg["MISSED_STEPS"],
        "event_sha256": digest(event_file), "summary_sha256": digest(summary_file),
        "fixed_cpu_event_and_count_check": "PASS",
    }


def audit_long(capture: Path, parsed: Path, ipi: int) -> dict[str, object]:
    reference = STEP9 / "host" / "captures" / f"ipi_{ipi}_summary_parsed" / "counts.csv"
    group_result = json.loads(run(STEP9 / "host" / "step9_host.py", "compare-groups",
                                  "--counts", parsed / "counts.csv", "--ipi-ms", ipi))
    check(group_result["pass"] is True, f"{capture}: group mismatch")
    run(STEP15 / "host" / "verify_long_runtime_capture.py", "--capture-dir", capture,
        "--counts", parsed / "counts.csv", "--reference-counts", reference,
        "--expected-epoch", 2)
    new, old = count_rows(parsed / "counts.csv"), count_rows(reference)
    check(len(new) == len(old) == 4308, f"{capture}: long row count")
    changed_cycles = sum(int(a["cycles"]) != int(b["cycles"]) for a, b in zip(new, old))
    max_delta = max(abs(int(a["cycles"]) - int(b["cycles"])) for a, b in zip(new, old))
    reg = registers(capture)
    return {
        "steps": 4308, "epoch": reg["IMAGE_EPOCH"], "checksum": f"{reg['IMAGE_CHECKSUM']:08X}",
        "per_step_noncycle_fields_equal_to_dedicated": len(FIELDS) * 4308,
        "response_window_ms": group_result["response_window_ms"],
        "fixed_cpu_response_window_groups": group_result["fixed_response_spikes"],
        "board_response_window_groups": group_result["board_response_spikes"],
        "individual_events_captured": False,
        "cycles_different_from_dedicated_steps": changed_cycles,
        "max_absolute_cycle_delta": max_delta,
        "max_latency_cycles": reg["MAX_LATENCY"], "missed_steps": reg["MISSED_STEPS"],
        "summary_sha256": digest(capture / "summary_words.hex"),
        "counts_sha256": digest(parsed / "counts.csv"),
    }


def audit(root: Path, log: Path, jtag_root: Path, jtag_fault_root: Path) -> dict[str, object]:
    ethernet_bit = BIT if BIT.is_file() else CODE.parent / "hardware" / "bitstreams" / "cns2fpga_runtime_eth_200mhz.bit"
    jtag_bit = JTAG_BIT if JTAG_BIT.is_file() else CODE.parent / "hardware" / "bitstreams" / "cns2fpga_runtime_jtag_200mhz.bit"
    check(digest(ethernet_bit) == BIT_SHA256, "Ethernet bitstream SHA-256 changed")
    check(digest(jtag_bit) == JTAG_BIT_SHA256, "JTAG bitstream SHA-256 changed")
    campaign = json.loads((root / "campaign_summary.json").read_text(encoding="utf-8-sig"))
    check(isinstance(campaign, list) and len(campaign) == 2, "Need two completed sessions")
    transcript = log.read_text(encoding="utf-8", errors="replace")
    check(transcript.count("RUNTIME_ETH_PROGRAM_PASS") == 2, "Expected exactly two bit programs")
    check("ETHERNET_P0_CAMPAIGN_PASS sessions=2" in transcript, "Campaign did not pass")
    sessions = []
    for session in (1, 2):
        folder = root / f"session_{session}"
        campaign_item = campaign[session - 1]
        check(campaign_item["session"] == session and campaign_item["status"] == "PASS",
              f"Session {session} summary")
        check(campaign_item["bit_sha256"] == BIT_SHA256, f"Session {session} bit hash")
        check(campaign_item["program_operations"] == 1, f"Session {session} programming count")
        check(f"ETHERNET_P0_SESSION_PASS session={session}" in transcript, f"Session {session} pass marker")
        for marker in ("P0_UDP_HOST_INTERRUPTED_PASS", "P0_UDP_INCOMPLETE_REJECT_PASS",
                       "P0_UDP_BAD_POST_REJECT_PASS"):
            check(transcript.count(marker) == 2, f"Fault marker {marker}")
        item = {
            "session": session, "program_operations": 1,
            "visual_upload_seconds": campaign_item["visual_upload_seconds"],
            "courtship_upload_seconds": campaign_item["courtship_upload_seconds"],
            "visual": audit_short(folder / "visual_250", "visual", 1),
            "courtship_smoke8": audit_short(folder / "courtship_smoke8", "courtship", 2),
            "long_courtship": {},
            "visual_recovered": audit_short(folder / "visual_recovered_250", "visual", 3),
            "faults": {"host_interrupted": "PASS", "incomplete_commit_rejected": "PASS",
                       "bad_image_post_rejected": "PASS", "valid_reload_after_fault": "PASS"},
        }
        for ipi in IPIS:
            item["long_courtship"][str(ipi)] = audit_long(folder / f"courtship_ipi_{ipi}",
                                                            folder / f"courtship_ipi_{ipi}_parsed", ipi)
        sessions.append(item)
    first, second = sessions
    repeat = {}
    for key, folder_name in (("visual", "visual_250"),
                             ("courtship_smoke8", "courtship_smoke8"),
                             ("visual_recovered", "visual_recovered_250")):
        check(first[key]["event_sha256"] == second[key]["event_sha256"], f"Repeat events {key}")
        repeat[key] = repeat_summary(root / "session_1" / folder_name / "summary_words.hex",
                                     root / "session_2" / folder_name / "summary_words.hex")
    for ipi in IPIS:
        a = first["long_courtship"][str(ipi)]
        b = second["long_courtship"][str(ipi)]
        repeat[f"courtship_ipi_{ipi}"] = repeat_summary(
            root / "session_1" / f"courtship_ipi_{ipi}" / "summary_words.hex",
            root / "session_2" / f"courtship_ipi_{ipi}" / "summary_words.hex")
        check(a["board_response_window_groups"] == b["board_response_window_groups"],
              f"Repeat long group counts {ipi}")
    jtag_visual = audit_short(jtag_root / "visual", "visual", 1)
    jtag_courtship = audit_short(jtag_root / "courtship", "courtship", 2)
    transcript_path = jtag_root / "transcript.log"
    if not transcript_path.is_file():
        transcript_path = jtag_root.parent / "p0_jtag_20260930_transcript.log"
    jtag_transcript = transcript_path.read_text(errors="replace")
    check("TWO_IMAGE_BOARD_DEMO_PASS" in jtag_transcript,
          "JTAG two-image demo pass marker missing")
    check(jtag_visual["event_sha256"] == first["visual"]["event_sha256"], "JTAG visual event mismatch")
    check(jtag_courtship["event_sha256"] == first["courtship_smoke8"]["event_sha256"],
          "JTAG courtship event mismatch")
    interrupted = (jtag_fault_root / "interrupt.log").read_text(errors="replace")
    rejected = (jtag_fault_root / "reject.log").read_text(errors="replace")
    check("P0_JTAG_INTERRUPTED_PASS" in interrupted, "JTAG interrupt missing")
    check("P0_JTAG_INCOMPLETE_REJECT_PASS" in rejected, "JTAG incomplete reject missing")
    check("P0_JTAG_BAD_POST_REJECT_PASS" in rejected, "JTAG bad post reject missing")
    jtag_recovered = audit_short(jtag_fault_root / "visual_recovered", "visual", 4)
    check(jtag_recovered["event_sha256"] == jtag_visual["event_sha256"],
          "JTAG recovery events mismatch")
    return {
        "schema": "cns2fpga.p0_board_audit.v1", "status": "PASS", "bit_sha256": BIT_SHA256,
        "date": "2026-09-30", "ethernet_sessions": sessions,
        "repeat_output_comparison": repeat,
        "jtag": {"bit_sha256": JTAG_BIT_SHA256, "program_operations": 1,
                 "visual": jtag_visual, "courtship_smoke8": jtag_courtship,
                 "visual_recovered": jtag_recovered,
                 "faults": {"host_interrupted": "PASS", "incomplete_commit_rejected": "PASS",
                            "bad_image_post_rejected": "PASS", "valid_reload_after_fault": "PASS"}},
        "scope": "Physical board output counters/events and diagnostics; not internal neuron state, power, or biological validation.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign-root", type=Path, required=True)
    parser.add_argument("--campaign-log", type=Path, required=True)
    parser.add_argument("--jtag-root", type=Path, required=True)
    parser.add_argument("--jtag-fault-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.campaign_root, args.campaign_log, args.jtag_root, args.jtag_fault_root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "sessions": len(result["ethernet_sessions"]),
                      "output": str(args.output)}, indent=2))


if __name__ == "__main__":
    main()
