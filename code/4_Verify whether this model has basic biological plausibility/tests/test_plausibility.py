import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from cns2fpga_plausibility.checks import evaluate_ipi_tuning, silence_neurons


def test_silence_neurons_disables_incoming_and_outgoing_edges():
    edges = pd.DataFrame({
        "pre_index": [0, 1, 2], "post_index": [1, 2, 0],
        "synapse_count": [5, 6, 7], "nt_model_sign": [1, -1, 1],
    })
    result = silence_neurons(edges, np.array([1]))
    assert result.nt_model_sign.tolist() == [0, 0, 1]
    assert result.synapse_count.tolist() == edges.synapse_count.tolist()


def test_three_point_bandpass_constraint():
    summary = pd.DataFrame({
        "ipi_ms": [16.0, 36.0, 56.0],
        "pC1_mean_rate_hz": [2.0, 8.0, 5.0],
    })
    result = evaluate_ipi_tuning(summary, "pC1", 36.0, 16.0, 56.0)
    assert result["preferred_over_short"]
    assert result["preferred_over_long"]
    assert result["dynamic_range_hz"] == 6.0
