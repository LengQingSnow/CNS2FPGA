"""Reconstruct the September 2026 Ethernet deployment result from raw captures.

This is deliberately offline: it never talks to or changes the FPGA.  It fails
if any of the observed counters, event order, image checksums, or bitstream
identity disagree with the pinned experiment.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
from pathlib import Path


HERE = Path(__file__).resolve().parent
STEP15 = HERE.parent
CODE = STEP15.parent
ROOT = CODE.parent
CAPTURE = STEP15 / "reports" / "courtship_trial_20260928"
TRIAL = CODE / "9_KU115 FPGA Validation" / "host" / "trials" / "smoke8"
BIT = STEP15 / "build" / "runtime_eth_portfilter_200mhz" / "cns2fpga_runtime_eth_portfilter_200mhz.bit"
PUBLISHED_BIT = ROOT / "hardware" / "bitstreams" / "cns2fpga_runtime_eth_200mhz.bit"
VISUAL_LOG = STEP15 / "reports" / "visual_upload" / "visual_upload_20260928_072611.log"
COURTSHIP_LOG = STEP15 / "reports" / "courtship_upload" / "courtship_upload_20260928_072927.log"
ROUTE = STEP15 / "reports" / "runtime_eth_portfilter_200mhz" / "run_status.txt"
UTIL = STEP15 / "reports" / "runtime_eth_portfilter_200mhz" / "post_route_utilization.rpt"
OUT = STEP15 / "reports" / "deployment_evidence_v1.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def words(path: Path) -> list[int]:
    return [int(line, 16) for line in path.read_text().splitlines() if line.strip()]


def main() -> None:
    bit_source = BIT if BIT.is_file() else PUBLISHED_BIT
    bit_sha = sha256(bit_source)
    assert bit_sha == "581354A62C8C7AEB134F300E7EA1928D8B681B996807710C61E307B33530D8F8"
    visual = VISUAL_LOG.read_text(encoding="utf-8-sig", errors="replace")
    courtship = COURTSHIP_LOG.read_text(encoding="utf-8-sig", errors="replace")
    assert "PREFLIGHT neurons=226 synapses=1730 words=4816 packets=81 checksum=6C233D31" in visual
    assert "ETHERNET_IMAGE_COMMIT_PASS words=4816 checksum=6C233D31" in visual
    assert "PREFLIGHT neurons=6279 synapses=350185 words=738044 packets=11538 checksum=45AEAAAE" in courtship
    assert "ETHERNET_IMAGE_COMMIT_PASS words=738044 checksum=45AEAAAE" in courtship
    assert "ETHERNET_STATUS_PASS" in courtship and "COURTSHIP_UDP_BOARD_TEST_PASS" in courtship
    assert "LINK_SPEED=100 Mbps" in courtship
    # The visual wrapper's extra STATUS used the wrong sequence number and
    # printed FAIL.  Only its uploader COMMIT is claimed here; a later probe
    # independently established STATUS=1 before the courtship load.
    assert "VISUAL_UDP_BOARD_TEST_FAIL" in visual
    probe = (STEP15 / "reports" / "ethernet_probe" / "capture.log").read_text(
        encoding="utf-8-sig", errors="replace"
    )
    assert "ETHERNET_STATUS_PASS" in probe and "image_status=0x00000001" in probe

    with (CAPTURE / "registers.csv").open(newline="", encoding="utf-8") as stream:
        registers = {row["name"]: int(row["hex32"], 16) for row in csv.DictReader(stream)}
    required = {
        "ID": 0x434E5352,
        "STATUS": 2,
        "IMAGE_STATUS": 1,
        "IMAGE_CHECKSUM": 0x45AEAAAE,
        "IMAGE_EPOCH": 2,
        "ACTIVE_NEURONS": 6279,
        "ACTIVE_SYNAPSES": 350185,
        "COMPLETED_STEPS": 8,
        "GLOBAL_EVENT_COUNT": 2475,
        "MISSED_STEPS": 0,
        "MAX_LATENCY": 199699,
    }
    for key, expected in required.items():
        assert registers[key] == expected, (key, registers[key], expected)
    assert registers["MAX_LATENCY"] <= 200000
    with (TRIAL / "reference_summary.csv").open(newline="", encoding="utf-8") as stream:
        reference = list(csv.DictReader(stream))
    summary = words(CAPTURE / "summary_words.hex")
    event_memory = words(CAPTURE / "event_words.hex")
    spike_bits = (TRIAL / "expected_spike.mem").read_text().splitlines()
    assert len(reference) == 8 and len(summary) == 64 and len(spike_bits) == 8 * 6279
    expected_events = [
        (i // 6279, i % 6279) for i, bit in enumerate(spike_bits) if bit == "1"
    ]
    observed_events: list[tuple[int, int]] = []
    step_counts = []
    for step, row in enumerate(reference):
        assert int(row["timestep"]) == step
        observed = summary[step * 8 + 2] & 0xFFFF
        expected = int(row["spikes"])
        flags_and_count = summary[step * 8 + 5]
        count = flags_and_count >> 16
        flags = flags_and_count & 0xF
        start = summary[step * 8 + 6]
        assert observed == expected and flags == 0 and count == observed
        assert start + count <= len(event_memory)
        observed_events.extend((step, w & 0x1FFF) for w in event_memory[start:start + count])
        step_counts.append({"step": step, "cpu_fixed": expected, "fpga": observed})
    assert observed_events == expected_events and len(observed_events) == 2475

    route = dict(line.split("=", 1) for line in ROUTE.read_text().splitlines() if "=" in line)
    assert route["part"] == "xcku115-flva1517-2-i"
    assert route["core_clock_mhz"] == "200.000"
    assert route["timing_met"] == route["hold_met"] == "1"
    assert route["unrouted_nets"] == route["partially_routed_nets"] == route["drc_error_count"] == "0"
    utilization = UTIL.read_text()
    def used(label: str) -> int:
        match = re.search(r"^\|\s*" + re.escape(label) + r"\s*\|\s*(\d+)\s*\|", utilization, re.M)
        assert match, label
        return int(match.group(1))

    evidence = {
        "schema": "cns2fpga.ethernet_deployment_evidence.v1",
        "board": "ALINX AXKU115 V1.0",
        "bitstream": {"path": str(BIT.relative_to(ROOT)).replace("\\", "/"), "sha256": bit_sha,
                      "part": route["part"], "core_clock_mhz": 200,
                      "setup_wns_ns": float(route["wns_ns"]), "hold_whs_ns": float(route["whs_ns"]),
                      "unrouted_nets": 0, "drc_errors": 0,
                      "lut": used("CLB LUTs"), "flip_flops": used("CLB Registers"),
                      "ramb36": used("RAMB36/FIFO*"), "ramb18": used("RAMB18"), "dsp": used("DSPs")},
        "link": {"protocol": "UDP/IPv4 over RGMII", "measured_negotiated_mbps": 100,
                 "note": "This run negotiated 100 Mbps; 1 Gbps was seen in earlier diagnostic transmission, not in this upload run."},
        "images_in_order": [
            {"name": "visual_left_hw_ir_v0", "neurons": 226, "synapses": 1730,
             "words": 4816, "packets": 81, "checksum_hex": "6C233D31",
             "commit": "PASS", "independent_status": "PASS after corrected sequence-number probe",
             "new_bit_execution_trial": "not run"},
            {"name": "courtship_song", "neurons": 6279, "synapses": 350185,
             "words": 738044, "packets": 11538, "checksum_hex": "45AEAAAE",
             "commit": "PASS", "independent_status": "PASS", "image_epoch": 2,
             "new_bit_execution_trial": "8-step smoke8"},
        ],
        "fpga_reprogramming_between_images": False,
        "courtship_trial": {"steps": 8, "reference": "fixed-point CPU smoke8",
                            "step_counts": step_counts, "ordered_events_compared": 2475,
                            "ordered_event_mismatches": 0, "step_count_mismatches": 0,
                            "max_latency_cycles": 199699, "max_latency_us": 998.495,
                            "deadline_cycles": 200000, "deadline_margin_cycles": 301,
                            "missed_steps": 0, "summary_fault_flags": 0,
                            "image_checksum_hex": "45AEAAAE", "image_epoch": 2},
        "raw_evidence": {"visual_upload_log": str(VISUAL_LOG.relative_to(ROOT)).replace("\\", "/"),
                         "courtship_upload_log": str(COURTSHIP_LOG.relative_to(ROOT)).replace("\\", "/"),
                         "capture_directory": str(CAPTURE.relative_to(ROOT)).replace("\\", "/"),
                         "reference_directory": str(TRIAL.relative_to(ROOT)).replace("\\", "/"),
                         "route_status": str(ROUTE.relative_to(ROOT)).replace("\\", "/"),
                         "utilization_report": str(UTIL.relative_to(ROOT)).replace("\\", "/")},
        "limitations": ["Only courtship smoke8 was executed after the two UDP uploads on the new bitstream.",
                        "The visual 250-step event result and long courtship stimulus suite belong to earlier dedicated/JTAG implementations.",
                        "No host-inclusive transfer throughput benchmark, power measurement, or independent repeat-board trial was performed."],
    }
    OUT.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(OUT)


if __name__ == "__main__":
    main()
