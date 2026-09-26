import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT.parent / "3_CPU Floating-Point Golden Model/src"))
from cns2fpga_golden.model import FloatLIFNetwork
from cns2fpga_plausibility.diagnostics_v2 import (
    anatomical_groups, cut_edges, edge_partitions, filtered_proxy,
    observation_metrics, population_counts, readout_directions, shortest_paths, reconstruct_path,
)
from cns2fpga_plausibility.protocol import build_equal_pulse_conditions, summarize_activity


@pytest.mark.parametrize("backend", ["scipy_csr", "event_traversal"])
def test_edge_cut_preserves_other_weights_and_original_network(backend):
    neurons = pd.DataFrame({"neuron_index": [0, 1, 2]})
    synapses = pd.DataFrame({"pre_index": [0, 1], "post_index": [2, 2], "synapse_count": [1, 3], "nt_model_sign": [1, -1]})
    offsets = pd.DataFrame({"edge_start": [0, 1, 2], "edge_count": [1, 1, 0]})
    config = {"dt_ms": 1., "tau_membrane_ms": 20., "threshold": 1., "reset_voltage": 0., "refractory_ms": 1.,
              "bias_current": 0., "noise_std": 0., "random_seed": 1, "weight_mode": "post_normalized",
              "recurrent_gain": 2., "propagation_backend": backend}
    net = FloatLIFNetwork(neurons, synapses, offsets, config)
    original = net.weights.copy()
    cut = cut_edges(net, np.array([False, True]))
    np.testing.assert_array_equal(net.weights, original)
    np.testing.assert_array_equal(cut.weights, [.5, 0.])
    np.testing.assert_array_equal(cut._propagate(np.array([True, True, False])), [0., 0., .5])
    np.testing.assert_array_equal(net._propagate(np.array([True, True, False])), [0., 0., -1.])
    with pytest.raises(ValueError):
        cut_edges(net, np.array([0, 1]))


def test_partitions_anatomical_groups_and_bypass_paths():
    neurons = pd.DataFrame({"neuron_index": range(4), "type": ["input", "vpn", "pC1_a", "pC1_b"], "fruDsx": ["x"]*4})
    synapses = pd.DataFrame({"pre_index": [0, 1, 1, 0, 3], "post_index": [1, 2, 0, 3, 2], "nt_model_sign": [1, -1, -1, 1, 1]})
    masks = edge_partitions(synapses, [1], [2, 3])
    np.testing.assert_array_equal(masks["cut_vPN1_to_pC1"] | masks["cut_vPN1_to_other"], masks["cut_vPN1_all_output"])
    assert not np.any(masks["cut_vPN1_to_pC1"] & masks["cut_vPN1_to_other"])
    groups = anatomical_groups(neurons, synapses, {"vPN1": np.array([1]), "pC1": np.array([2, 3])})
    assert groups["pC1_direct_vPN1_recipient"].tolist() == [2]
    assert groups["pC1_no_direct_vPN1"].tolist() == [3]
    distance, parents = shortest_paths(synapses, 4, [0], blocked=[1], positive_only=True)
    assert reconstruct_path(2, distance, parents) == [0, 3, 2]
    assert reconstruct_path(1, distance, parents) == []


def test_double_exponential_matches_analytic_impulse_and_is_causal():
    counts = np.zeros(1500)
    counts[10] = 2.
    actual = filtered_proxy(counts, 1., 50., 500.)
    t = np.arange(1490.)
    tp = 50*500/450*np.log(10)
    scale = np.exp(-tp/500)-np.exp(-tp/50)
    expected = 2*(np.exp(-t/500)-np.exp(-t/50))/scale
    np.testing.assert_allclose(actual[10:], expected, atol=2e-13)
    assert np.all(actual[:11] == 0)
    assert actual.max() == pytest.approx(2., abs=.0001)
    with pytest.raises(ValueError):
        filtered_proxy(counts, 1, 500, 50)


def test_event_counts_and_rolling_metric_agree_with_v1():
    protocol = dict(ipi_ms=[15, 35, 95], pulse_count=40, start_ms=100, tail_ms=500,
                    pulse_width_ms=3, amplitude=1.2, peak_window_ms=100)
    condition = build_equal_pulse_conditions(protocol, 1.)[0]
    counts = population_counts(np.array([99, 100, 100, 101, condition.response_end]),
                               np.array([1, 1, 2, 3, 1]), [1, 2], len(condition.current))
    legacy = summarize_activity(counts, np.zeros_like(counts), 2, condition, 100.)
    metrics = observation_metrics(counts, 2, condition, [20, 100, 200], [{"rise_ms": 50, "decay_ms": 500}])
    by_name = {row["metric"]: row for row in metrics}
    assert by_name["rolling_100ms_hz"]["value"] == legacy["peak_rate_hz"]
    assert by_name["spikes_per_neuron_per_pulse"]["value"] == legacy["evoked_spikes_per_neuron_per_pulse"]
    assert not by_name["proxy_r50_d500"]["peak_after_response_window"]


def test_sensitivity_does_not_hide_failed_or_inactive_readouts():
    data = pd.DataFrame([dict(group="pC1", metric=m, ipi_ms=ipi, value=value)
                         for m in ["good", "opposite", "silent"]
                         for ipi, value in [(15, 1.), (25, 1.), (35, 2.), (85, 1.), (95, 1.)]])
    data.loc[data.metric.eq("opposite") & data.ipi_ms.eq(95), "value"] = 3.
    data.loc[data.metric.eq("silent"), "value"] = 0.
    result = readout_directions(data, 1e-12)
    assert len(result) == 6
    assert result[result.metric.eq("good")].supported.all()
    assert not result[result.metric.eq("silent")].supported.any()
    assert not result[result.metric.eq("opposite") & result.comparison.eq("long_85_95")].supported.item()
