"""Cheap protocol and provenance checks; no FPGA required."""

import importlib.util
from pathlib import Path
import unittest

import numpy as np


PATH = Path(__file__).resolve().parents[1] / "run_experiment.py"
SPEC = importlib.util.spec_from_file_location("run_experiment", PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ProtocolTests(unittest.TestCase):
    def test_case_families_and_horizons(self):
        cases = MODULE.make_cases()
        self.assertEqual(len(cases), 13)
        self.assertEqual([c["name"] for c in cases[:9]], [f"ipi_{v:02d}" for v in MODULE.IPIS])
        self.assertEqual([c["duration"] for c in cases], [4308] * 12 + [350])
        self.assertEqual([c["family"] for c in cases].count("intensity"), 2)

    def test_equal_pulse_width_and_pattern(self):
        for case in MODULE.make_cases():
            self.assertEqual(int(np.count_nonzero(case["current"])), 3 * len(case["onsets"]))
            self.assertTrue(all(np.all(case["current"][i:i + 3] == case["amplitude"])
                                for i in case["onsets"]))
        pattern = next(c for c in MODULE.make_cases() if c["family"] == "pattern")
        self.assertEqual(np.diff(pattern["onsets"]).tolist(), [20, 50] * 19 + [20])

    def test_locked_baseline_and_raster(self):
        cases = {c["name"]: c for c in MODULE.make_cases()}
        self.assertEqual(cases["ipi_35"]["response_end"], 1968)
        self.assertEqual(cases["raster_35_short"]["response_end"], 350)
        np.testing.assert_array_equal(cases["ipi_35"]["current"][:350], cases["raster_35_short"]["current"])


if __name__ == "__main__":
    unittest.main()
