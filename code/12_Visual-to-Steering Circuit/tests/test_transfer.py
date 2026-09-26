"""Regression checks for the second circuit's published engineering claims."""

import json
import unittest
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
BASELINES = ROOT.parent / "13_Baselines and Ablations" / "outputs" / "baseline_v0"


class TransferTests(unittest.TestCase):
    def test_extracted_graph_and_compiler(self):
        ir = ROOT / "outputs" / "visual_to_steering_v0"
        neurons = pd.read_csv(ir / "neuron_table.csv")
        edges = pd.read_csv(ir / "synapse_table.csv")
        self.assertEqual((len(neurons), len(edges), int(edges.synapse_count.sum())), (226, 1730, 33748))
        for name, count in (("visual_hw_ir_v0", 220), ("visual_left_hw_ir_v0", 109)):
            image = ROOT / "outputs" / name
            manifest = json.loads((image / "compiler_manifest.json").read_text(encoding="utf-8"))
            self.assertTrue((image / "protocol_lock.json").is_file())
            with (image / "input_mapping.mem").open(encoding="ascii") as stream:
                self.assertEqual(sum(1 for _ in stream), count)
            self.assertEqual(manifest["schema_version"], 1)

    def test_float_fixed_lateralized_output(self):
        frame = pd.read_csv(ROOT / "outputs" / "visual_experiment_v0" / "summary.csv")
        self.assertEqual(len(frame), 9)
        self.assertTrue(frame.event_f1.eq(1).all())
        self.assertTrue(frame.state_saturations.eq(0).all())
        self.assertTrue(frame.accumulator_saturations.eq(0).all())
        case = frame.loc[frame.condition.eq("pulse_ipi_40ms")].set_index("stimulated_side")
        self.assertEqual((int(case.loc["L", "fixed_DNa02_L_spikes"]),
                          int(case.loc["L", "fixed_DNa02_R_spikes"])), (5, 0))
        self.assertEqual((int(case.loc["R", "fixed_DNa02_L_spikes"]),
                          int(case.loc["R", "fixed_DNa02_R_spikes"])), (0, 5))

    def test_manual_baseline_is_discriminated(self):
        rows = pd.read_csv(BASELINES / "manual_vs_automatic.csv")
        left = rows.loc[rows.condition.eq("pulse_ipi_40ms") & rows.stimulated_side.eq("L")].iloc[0]
        self.assertEqual((int(left.reference_DNa02_L), int(left.manual_DNa02_L)), (5, 0))
        structure = json.loads((BASELINES / "structural_comparison.json").read_text(encoding="utf-8"))
        self.assertEqual(structure["manual_edges_overlapping_real"], 321)

    def test_physical_capture_locked(self):
        board = ROOT / "outputs" / "visual_left_board_v0"
        result = json.loads((board / "verification.json").read_text(encoding="utf-8"))
        self.assertEqual(result["verdict"], "PASS")
        self.assertEqual((result["ordered_events_compared"], result["per_timestep_total_compared"]), (560, 250))
        self.assertEqual((result["DNa02_L_spikes"], result["DNa02_R_spikes"]), (5, 0))
        self.assertLess(result["max_latency_cycles"], result["period_cycles"])
        self.assertTrue(all(value == 0 for value in result["diagnostic_sum"].values()))


if __name__ == "__main__":
    unittest.main()
