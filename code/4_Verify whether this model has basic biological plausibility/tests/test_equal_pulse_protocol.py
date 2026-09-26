import copy
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))
from cns2fpga_plausibility.protocol import build_equal_pulse_conditions, summarize_activity, drop_percent
from cns2fpga_plausibility.evaluation_v1 import tuning_checks, overall_verdict
from run_equal_pulse_validation import make_ablation_plan


def config():
    return json.loads((ROOT / "configs" / "courtship_song_equal_pulse_v1.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("dt", [1., .5])
def test_exactly_40_pulses_including_last_and_equal_charge(dt):
    conditions = build_equal_pulse_conditions(config()["protocol"], dt)
    assert len(conditions) == 9
    assert len({len(item.current) for item in conditions}) == 1
    assert {item.description()["trial_duration_ms"] for item in conditions} == {4308.}
    for condition in conditions:
        current = condition.current
        rising = np.flatnonzero(np.diff(np.r_[False, current > 0].astype(int)) == 1)
        np.testing.assert_array_equal(rising, condition.onsets)
        assert len(rising) == 40
        assert np.count_nonzero(current) == 40 * int(3 / dt)
        assert current[condition.train_end-1] == 1.2
        assert current[condition.train_end] == 0
        assert np.allclose(np.diff(rising) * dt, condition.ipi_ms)
        assert current.sum() * dt == pytest.approx(144.)


def test_invalid_fractional_time_and_overlapping_pulses_rejected():
    protocol = config()["protocol"]
    with pytest.raises(ValueError, match="integer multiple"):
        build_equal_pulse_conditions(protocol, 2.)
    protocol["pulse_width_ms"] = 15.
    with pytest.raises(ValueError, match="nonoverlapping"):
        build_equal_pulse_conditions(protocol, 1.)


def test_metric_window_boundaries_and_population_denominators():
    condition = build_equal_pulse_conditions(config()["protocol"], 1.)[0]
    counts = np.zeros_like(condition.current)
    counts[condition.start-1] = 5  # baseline: must not enter evoked count/peak
    counts[condition.start] = 4
    counts[condition.response_end-1] = 2
    counts[condition.response_end] = 9  # excluded by the half-open response window
    quiet = np.zeros_like(counts)
    quiet[condition.start] = 2
    summary = summarize_activity(counts, quiet, 2, condition, 100.)
    assert summary["peak_rate_hz"] == 10.
    assert summary["response_spikes"] == 6
    assert summary["silence_response_spikes"] == 2
    assert summary["evoked_spikes_per_neuron_per_pulse"] == .05
    assert summary["post_tail_rate_hz"] == 10.
    assert summary["common_window_spikes_per_neuron"] == 6.5
    assert np.isnan(summarize_activity(counts, quiet, 0, condition, 100.)["peak_rate_hz"])
    assert np.isnan(drop_percent(0., 0.))
    assert drop_percent(2., 3.) == -50.


def test_band_plateau_allowed_and_long_ipi_failures_not_hidden():
    cfg = config()
    rows = []
    for group in ["vPN1", "pC1"]:
        for ipi in cfg["protocol"]["ipi_ms"]:
            response = 2. if ipi in [15, 25, 85, 95] else 5.
            rows.append(dict(group=group, ipi_ms=ipi, peak_rate_hz=response,
                             evoked_spikes_per_neuron_per_pulse=response))
    summary = pd.DataFrame(rows)
    checks = pd.DataFrame(tuning_checks(summary, cfg))
    assert overall_verdict(checks) == "CONDITIONAL_SUPPORT"
    summary.loc[summary.group.eq("pC1") & summary.ipi_ms.eq(95), "peak_rate_hz"] = 6.
    checks = pd.DataFrame(tuning_checks(summary, cfg))
    assert overall_verdict(checks) == "NOT_SUPPORTED"
    summary.loc[summary.group.eq("pC1"), "peak_rate_hz"] = np.nan
    assert overall_verdict(pd.DataFrame(tuning_checks(summary, cfg))) == "INCOMPLETE"
    assert overall_verdict(pd.DataFrame(columns=["gate", "status"]).astype({"gate": bool})) == "INCOMPLETE"


def test_random_masks_match_count_and_signs_and_exclude_all_observed_cells():
    neurons = pd.DataFrame({"neuron_index": np.arange(14), "bodyId": np.arange(100, 114),
                            "nt_model_sign": [1, -1, 0, 1, -1, 0, 1, -1, 0, 1, -1, 0, 1, -1]})
    groups = {"vPN1": np.array([0, 1]), "pC1": np.array([2, 3]), "auditory_input": np.array([4])}
    settings = copy.deepcopy(config()["ablation"])
    settings["random_replicates"] = 3
    plan = make_ablation_plan(neurons, groups, settings)
    assert plan == make_ablation_plan(neurons, groups, settings)
    for entry in plan:
        if entry["kind"] == "random_control":
            assert len(entry["indices"]) == len(set(entry["indices"])) == 2
            assert set(entry["indices"]).isdisjoint({0, 1, 2, 3, 4})
            expected = neurons.iloc[groups[entry["target"]]].nt_model_sign.to_numpy()
            observed = neurons.iloc[entry["indices"]].nt_model_sign.to_numpy()
            np.testing.assert_array_equal(np.sort(observed), np.sort(expected))
