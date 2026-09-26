import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from cns2fpga_plausibility.roi_robustness_v3d import (
    build_membership, counts_from_events, intervention_effects,
)


def test_event_counts_and_candidate_membership_are_index_based():
    neurons = pd.DataFrame({
        "neuron_index": [0, 1, 2], "bodyId": [10, 11, 12],
        "type": ["pC1_a", "pC1_b", "x"], "somaSide": ["L", "R", "L"],
        "fruDsx": ["coexpress_high", "dsx_high", ""], "synonyms": ["pMP-e", "", ""],
    })
    nb = pd.DataFrame({"bodyId": [10, 11], "in_frozen_ir": [True, True], "best_rank": [5, 200]})
    membership, groups = build_membership(neurons, nb, 100)
    assert groups["pC1_type_all"].tolist() == [0, 1]
    assert groups["pC1_neuronbridge_best_rank_le_100"].tolist() == [0]
    counts = counts_from_events(np.array([1, 1, 3]), np.array([0, 2, 1]), groups["pC1_type_all"], 5)
    assert counts.tolist() == [0, 1, 0, 1, 0]
    assert membership.pC1_neuronbridge_any_hit.sum() == 2


def test_intervention_direction_uses_matched_group_and_ipi():
    rows = pd.DataFrame([
        {"condition_id": "intact", "candidate_id": "a", "ipi_ms": 35., "response_spikes": 10, "peak_rate_hz": 5., "evoked_spikes_per_neuron_per_pulse": 1.},
        {"condition_id": "cut", "candidate_id": "a", "ipi_ms": 35., "response_spikes": 8, "peak_rate_hz": 6., "evoked_spikes_per_neuron_per_pulse": 1.},
    ])
    result = intervention_effects(rows).set_index("metric")
    assert result.loc["response_spikes", "direction"] == -1
    assert result.loc["peak_rate_hz", "direction"] == 1
    assert result.loc["evoked_spikes_per_neuron_per_pulse", "direction"] == 0
