"""Compare the dedicated courtship bitstream and Ethernet runtime smoke8 captures.

Offline and read-only with respect to the board.  The output records what was
observed, without attributing cycle differences to any particular RTL path.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
STEP15 = HERE.parent
CODE = STEP15.parent
PROJECT = CODE.parent
OLD_CAPTURE = CODE / "9_KU115 FPGA Validation" / "host" / "captures" / "smoke8_events"
NEW_CAPTURE = STEP15 / "reports" / "courtship_trial_20260928"
OLD_RESOURCES = CODE / "10_Complete Courtship-Song Circuit Experiment" / "outputs" / "courtship_song_v1" / "resource_timing.json"
NEW_EVIDENCE = STEP15 / "reports" / "deployment_evidence_v1.json"
OUT = STEP15 / "reports" / "old_new_board_comparison_v1.json"


def read_words(path: Path) -> list[int]:
    lines = path.read_text(encoding="ascii").splitlines()
    assert all(len(line.strip()) == 8 for line in lines)
    return [int(line, 16) for line in lines]


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def relative(path: Path) -> str:
    return str(path.relative_to(PROJECT)).replace("\\", "/")


def main() -> None:
    old = read_words(OLD_CAPTURE / "summary_words.hex")
    new = read_words(NEW_CAPTURE / "summary_words.hex")
    assert len(old) == len(new) == 64
    old_events = OLD_CAPTURE / "event_words.hex"
    new_events = NEW_CAPTURE / "event_words.hex"
    old_event_words = read_words(old_events)
    new_event_words = read_words(new_events)
    assert len(old_event_words) == len(new_event_words) == 2475
    assert old_event_words == new_event_words
    assert digest(old_events) == digest(new_events)

    old_resources = json.loads(OLD_RESOURCES.read_text(encoding="utf-8"))
    new_evidence = json.loads(NEW_EVIDENCE.read_text(encoding="utf-8"))
    latest = new_evidence["bitstream"]
    trial = new_evidence["courtship_trial"]
    assert old_resources["clock_mhz"] == latest["core_clock_mhz"] == 200
    assert trial["steps"] == 8 and trial["ordered_events_compared"] == 2475
    rows = []
    for step in range(8):
        a = old[step*8:step*8+8]
        b = new[step*8:step*8+8]
        assert a[1:] == b[1:], (step, a, b)
        spike_count = a[2] & 0xFFFF
        assert spike_count == trial["step_counts"][step]["cpu_fixed"]
        assert spike_count == trial["step_counts"][step]["fpga"]
        delta = b[0] - a[0]
        assert delta == spike_count, (step, delta, spike_count)
        rows.append({"step": step, "spikes_both": spike_count,
                     "dedicated_cycles": a[0], "ethernet_runtime_cycles": b[0],
                     "cycle_delta": delta, "other_seven_summary_words_identical": True})

    resources = {
        "lut": [old_resources["lut"], latest["lut"]],
        "flip_flops": [old_resources["ff"], latest["flip_flops"]],
        "ramb36": [old_resources["ramb36e2"], latest["ramb36"]],
        "ramb18": [old_resources["ramb18e2"], latest["ramb18"]],
        "dsp": [old_resources["dsp48e2"], latest["dsp"]],
        "setup_wns_ns": [old_resources["setup_wns_ns"], latest["setup_wns_ns"]],
        "hold_whs_ns": [old_resources["hold_whs_ns"], latest["hold_whs_ns"]],
    }
    assert max(r["dedicated_cycles"] for r in rows) == 199063
    assert max(r["ethernet_runtime_cycles"] for r in rows) == 199699
    result = {
        "schema": "cns2fpga.old_new_board_comparison.v1",
        "scope": "Same 8-step courtship smoke8 stimulus on the AXKU115 at 200 MHz; dedicated bitstream versus Ethernet runtime bitstream after UDP image load.",
        "bitstreams": {
            "dedicated_courtship_sha256": old_resources["bitstream_sha256"].upper(),
            "ethernet_runtime_sha256": latest["sha256"],
        },
        "ordered_event_words": {"count_each": 2475,
                                "byte_identical": True,
                                "sha256_each": digest(old_events)},
        "step_comparison": rows,
        "summary_words_per_step": 8,
        "summary_differing_word_indices_each_step": [0],
        "max_latency_cycles": {"dedicated": 199063, "ethernet_runtime": 199699,
                               "delta": 636},
        "deadline_margin_cycles": {"dedicated": 937, "ethernet_runtime": 301},
        "resource_comparison_order": ["dedicated_courtship", "ethernet_runtime"],
        "resource_comparison": resources,
        "interpretation_limits": [
            "The cycle delta equals each step's spike count in this capture; this is an observed numerical relationship, not a proven causal attribution to a particular RTL stage.",
            "Graph and stimulus outputs are unchanged in smoke8, but the bitstream and hardware timing/resources differ.",
            "The new bitstream has no visual execution trial or rerun of the 13 long courtship conditions, so this comparison cannot assert their equality.",
            "This is one paired short trial, not a distribution of repeated measurements.",
        ],
        "sources": {
            "dedicated_summary": relative(OLD_CAPTURE / "summary_words.hex"),
            "ethernet_runtime_summary": relative(NEW_CAPTURE / "summary_words.hex"),
            "dedicated_events": relative(old_events),
            "ethernet_runtime_events": relative(new_events),
            "dedicated_resource_timing": relative(OLD_RESOURCES),
            "ethernet_deployment_evidence": relative(NEW_EVIDENCE),
        },
    }
    OUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(OUT)


if __name__ == "__main__":
    main()
