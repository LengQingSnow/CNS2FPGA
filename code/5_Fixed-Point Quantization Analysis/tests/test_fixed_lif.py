from pathlib import Path
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from cns2fpga_fixed.fixed_lif import FixedFormat, FixedLIFNetwork, quantize, round_shift, saturate


def test_rounding_and_saturation_contract():
    np.testing.assert_array_equal(round_shift(np.array([-3, -2, -1, 1, 2, 3]), 1), [-2, -1, -1, 1, 1, 2])
    np.testing.assert_array_equal(quantize([-0.5, 0.5, 1.25], 1), [-1, 1, 3])
    clipped, count = saturate(np.array([-9, -8, 7, 8]), 4)
    np.testing.assert_array_equal(clipped, [-8, -8, 7, 7])
    assert count == 2


def test_two_neuron_integer_chain_has_one_step_delay():
    neurons = pd.DataFrame({"neuron_index": [0, 1]})
    synapses = pd.DataFrame({"pre_index": [0], "post_index": [1], "synapse_count": [2], "nt_model_sign": [1]})
    offsets = pd.DataFrame({"edge_start": [0, 1], "edge_count": [1, 0]})
    model = {"weight_mode": "raw_linear", "recurrent_gain": 0.5, "dt_ms": 1.0,
             "tau_membrane_ms": 20.0, "threshold": 1.0, "reset_voltage": 0.0,
             "refractory_ms": 1.0, "bias_current": 0.0, "noise_std": 0.0}
    fmt = FixedFormat.from_dict({"name": "test", "state_bits": 16, "state_frac": 8,
        "weight_bits": 16, "weight_frac": 8, "decay_bits": 16, "decay_frac": 14,
        "accumulator_bits": 24})
    net = FixedLIFNetwork(neurons, synapses, offsets, model, fmt)
    result = net.simulate(np.array([1.0, 0.0, 0.0]), np.array([0]), {"all": np.array([0, 1])})
    assert result.spike_times.tolist() == [0, 1]
    assert result.spike_neurons.tolist() == [0, 1]
    assert result.state_saturation_events == 0


def test_edge_cut_and_silencing_are_explicit_and_repeatable():
    neurons = pd.DataFrame({"neuron_index": [0, 1]})
    synapses = pd.DataFrame({"pre_index": [0], "post_index": [1], "synapse_count": [2], "nt_model_sign": [1]})
    offsets = pd.DataFrame({"edge_start": [0, 1], "edge_count": [1, 0]})
    model = {"weight_mode": "raw_linear", "recurrent_gain": 0.5, "dt_ms": 1.0,
             "tau_membrane_ms": 20.0, "threshold": 1.0, "reset_voltage": 0.0,
             "refractory_ms": 1.0, "bias_current": 0.0, "noise_std": 0.0}
    fmt = FixedFormat.from_dict({"name": "test", "state_bits": 16, "state_frac": 8,
        "weight_bits": 16, "weight_frac": 8, "decay_bits": 16, "decay_frac": 14,
        "accumulator_bits": 24})
    net = FixedLIFNetwork(neurons, synapses, offsets, model, fmt)
    current = np.array([1.0, 0.0, 0.0])
    groups = {"all": np.array([0, 1])}
    cut = net.simulate(current, np.array([0]), groups, disabled_edge_indices=np.array([0]))
    silent = net.simulate(current, np.array([0]), groups, silenced_indices=np.array([0]))
    assert cut.spike_neurons.tolist() == [0]
    assert silent.spike_neurons.tolist() == []
    repeat = net.simulate(current, np.array([0]), groups, disabled_edge_indices=np.array([0]))
    np.testing.assert_array_equal(repeat.spike_times, cut.spike_times)
    np.testing.assert_array_equal(repeat.spike_neurons, cut.spike_neurons)
