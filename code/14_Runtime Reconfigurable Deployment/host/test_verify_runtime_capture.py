"""Small offline checks for the runtime capture verifier."""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path


SCRIPT = Path(__file__).with_name("verify_runtime_capture.py")


def test_pass_and_mismatch() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        capture = root / "capture"
        capture.mkdir()
        (capture / "registers.csv").write_text(
            "name,hex32\n"
            "ID,434E5352\nSTATUS,00000002\nIMAGE_STATUS,00000001\n"
            "IMAGE_CHECKSUM,6C233D31\nIMAGE_EPOCH,00000001\n"
            "ACTIVE_NEURONS,000000E2\nACTIVE_SYNAPSES,000006C2\n"
            "COMPLETED_STEPS,00000001\nMISSED_STEPS,00000000\n"
            "MAX_LATENCY,00000400\n",
            encoding="utf-8",
        )
        words = [1024, 0, 2, 0, 0, 2 << 16, 0, 0]
        summary = capture / "summary_words.hex"
        summary.write_text("".join(f"{word:08X}\n" for word in words), encoding="utf-8")
        (capture / "event_words.hex").write_text("00000003\n00000004\n", encoding="utf-8")
        reference = root / "reference.csv"
        reference.write_text("timestep,spikes\n0,2\n", encoding="utf-8")
        events = root / "events.csv"
        events.write_text("timestep,neuron_index\n0,3\n0,4\n", encoding="utf-8")
        command = [
            sys.executable,
            str(SCRIPT),
            "--capture-dir", str(capture),
            "--reference-summary", str(reference),
            "--expected-checksum", "6C233D31",
            "--expected-epoch", "1",
            "--expected-neurons", "226",
            "--expected-synapses", "1730",
            "--expected-events", str(events),
        ]
        passed = subprocess.run(command, capture_output=True, text=True)
        assert passed.returncode == 0, passed.stderr
        assert '"status": "PASS"' in passed.stdout
        words[2] = 1
        summary.write_text("".join(f"{word:08X}\n" for word in words), encoding="utf-8")
        failed = subprocess.run(command, capture_output=True, text=True)
        assert failed.returncode != 0
        assert "step 0: observed 1, expected 2" in failed.stderr
        reference.write_text("timestep,total\n0,1\n", encoding="utf-8")
        passed = subprocess.run(command, capture_output=True, text=True)
        assert passed.returncode == 0, passed.stderr
        spike_mem = root / "expected_spike.mem"
        spike_mem.write_text("0\n0\n0\n1\n1\n" + "0\n" * 221, encoding="utf-8")
        memory_command = command[:-2] + ["--expected-spike-mem", str(spike_mem)]
        passed = subprocess.run(memory_command, capture_output=True, text=True)
        assert passed.returncode == 0, passed.stderr


if __name__ == "__main__":
    test_pass_and_mismatch()
    print("VERIFY_RUNTIME_CAPTURE_TEST_PASS")
