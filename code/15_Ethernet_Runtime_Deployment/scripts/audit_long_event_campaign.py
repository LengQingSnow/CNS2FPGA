"""Independently recheck and curate the physical long-event board campaign."""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
from pathlib import Path


STEP15 = Path(__file__).resolve().parents[1]
CODE = STEP15.parent
BUILD = STEP15 / "build" / "long_events_20260930"
CAMPAIGN = BUILD / "new_bit_campaign_retry1"
REPORTS = STEP15 / "reports"
CURATED = REPORTS / "long_event_board_20260930"
AUDIT = REPORTS / "long_event_board_audit_v1.json"
BIT = STEP15 / "build" / "runtime_eth_long_events_retry_200mhz" / "cns2fpga_runtime_eth_long_events_retry_200mhz.bit"
sys.path.insert(0, str(STEP15 / "host"))
from verify_long_event_capture import run as verify


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def main() -> None:
    if AUDIT.exists() or CURATED.exists():
        raise FileExistsError("Refusing to overwrite existing long-event audit")
    campaign_status = json.loads((CAMPAIGN / "status.json").read_text(encoding="utf-8-sig"))
    if campaign_status["status"] != "PASS" or campaign_status["completed_ipi_ms"] != [15, 35, 65]:
        raise AssertionError("Board campaign is not complete")
    bit_hash = digest(BIT)
    if bit_hash != campaign_status["bit_sha256"] or bit_hash != "D4C9378D461147062FA5DC590CB3647D241C789B01CC6255F38DA16CB21990DF":
        raise AssertionError("Expanded-event bitstream hash mismatch")
    signoff = (REPORTS / "runtime_eth_long_events_retry_200mhz" / "run_status.txt").read_text(encoding="ascii")
    for token in ("timing_met=1", "hold_met=1", "unrouted_nets=0", "partially_routed_nets=0",
                  "drc_error_count=0", "drc_critical_count=0"):
        if token not in signoff:
            raise AssertionError(f"Physical signoff missing {token}")
    old = verify(BUILD / "old_bit_ipi_15", BUILD / "cpu_ipi_15",
                 CODE / "9_KU115 FPGA Validation" / "host" / "captures" / "ipi_15_summary_parsed" / "counts.csv",
                 4, 65536)
    if digest(BUILD / "old_bit_ipi_15" / "event_words.hex") != old["event_words_sha256"]:
        raise AssertionError("Old-bit capture hash mismatch")
    captures = {}
    for ipi, expected in ((15, 40868), (35, 74765), (65, 99349)):
        capture = CAMPAIGN / f"ipi_{ipi}_capture"
        reference = BUILD / f"cpu_ipi_{ipi}"
        old_counts = CODE / "9_KU115 FPGA Validation" / "host" / "captures" / f"ipi_{ipi}_summary_parsed" / "counts.csv"
        result = verify(capture, reference, old_counts, 1, 131072)
        if result["status"] != "PASS" or result["ordered_events_compared"] != expected:
            raise AssertionError(f"IPI {ipi} event verification incomplete")
        original = json.loads((CAMPAIGN / f"ipi_{ipi}_verification.json").read_text(encoding="utf-8-sig"))
        if result != original:
            raise AssertionError(f"IPI {ipi} detached result differs from independent rerun")
        manifest = json.loads((reference / "reference_manifest.json").read_text(encoding="utf-8"))
        if manifest["ordered_events"] != expected or manifest["events_sha256"] != result["reference_events_sha256"]:
            raise AssertionError(f"IPI {ipi} CPU reference hash mismatch")
        captures[str(ipi)] = result
    if captures["15"]["event_words_sha256"] != old["event_words_sha256"]:
        raise AssertionError("Old/new IPI 15 event words differ")
    first_status = json.loads((BUILD / "new_bit_campaign" / "status.json").read_text(encoding="utf-8-sig"))
    if first_status["status"] != "FAIL" or first_status["phase"] != "UPLOAD_COURTSHIP":
        raise AssertionError("First-program Ethernet failure evidence missing")
    result = {
        "schema": "cns2fpga.long_event_board_audit.v1",
        "status": "PASS",
        "date": "2026-09-30",
        "board": "ALINX AXKU115 v1.0",
        "bitstream_sha256": bit_hash,
        "bitstream_programming_note": "First program had no UDP ACK and bad RX FCS; the same bitstream was reprogrammed and STATUS/upload passed. The successful campaign reused that programmed bitstream without further reprogramming.",
        "first_program_attempt_status": first_status["status"],
        "successful_campaign_programming_skipped": campaign_status["programming_skipped"],
        "source_image_checksum": "45AEAAAE",
        "image_epoch": 1,
        "event_capacity_rtl": 131072,
        "old_capacity": 65536,
        "routed_setup_slack_ns": 0.008,
        "routed_hold_slack_ns": 0.030,
        "routed_brams36": 618,
        "prior_runtime_brams36": 592,
        "ordered_events_total": sum(x[1] for x in ((15,40868),(35,74765),(65,99349))),
        "old_bit_ipi_15": old,
        "new_bit_conditions": captures,
        "comparison_scope": "Exact ordered neuron ID and timestep for all events, seven per-step output/synops fields against dedicated board, zero fault/deadline flags; internal voltage/current/refractory states were not read back.",
    }
    CURATED.mkdir(parents=True)
    copied = {}
    for ipi in (15, 35, 65):
        for source, rel in (
            *((CAMPAIGN / f"ipi_{ipi}_capture" / name, f"ipi_{ipi}/board/{name}")
              for name in ("registers.csv", "summary_words.hex", "event_words.hex")),
            *((BUILD / f"cpu_ipi_{ipi}" / name, f"ipi_{ipi}/cpu/{name}")
              for name in ("expected_events.csv", "expected_counts.csv", "reference_manifest.json")),
            (CAMPAIGN / f"ipi_{ipi}_verification.json", f"ipi_{ipi}/verification.json"),
        ):
            target = CURATED / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            copied[rel] = digest(target)
    for name in ("registers.csv", "summary_words.hex", "event_words.hex"):
        source = BUILD / "old_bit_ipi_15" / name
        target = CURATED / "old_bit_ipi_15" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        copied[str(target.relative_to(CURATED)).replace("\\", "/")] = digest(target)
    for source, rel in (
        (CAMPAIGN / "status.json", "campaign_status.json"),
        (BUILD / "new_bit_campaign" / "status.json", "first_program_attempt_status.json"),
        (REPORTS / "runtime_eth_long_events_retry_200mhz" / "run_status.txt", "physical_signoff.txt"),
    ):
        target = CURATED / rel
        shutil.copy2(source, target)
        copied[rel] = digest(target)
    result["curated_artifact_sha256"] = copied
    AUDIT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "PASS", "audit": str(AUDIT), "curated_files": len(copied),
                      "total_events": result["ordered_events_total"]}, indent=2))


if __name__ == "__main__":
    main()
