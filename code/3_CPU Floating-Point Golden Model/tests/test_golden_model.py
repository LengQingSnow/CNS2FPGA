"""Deterministic smoke tests for stimulus and LIF propagation semantics."""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from cns2fpga_golden.model import FloatLIFNetwork
from cns2fpga_golden.stimulus import pulse_train


def test_pulse_train_timing():
    current = pulse_train(12.0, 1.0, 2.0, 10.0, 2.0, 4.0, 1.5)
    assert np.flatnonzero(current).tolist() == [2, 3, 6, 7]


def test_two_neuron_chain_spikes_with_one_step_delay():
    neurons = pd.DataFrame({"neuron_index": [0, 1]})
    synapses = pd.DataFrame({
        "pre_index": [0], "post_index": [1], "synapse_count": [1], "nt_model_sign": [1]
    })
    offsets = pd.DataFrame({"pre_index": [0, 1], "edge_count": [1, 0], "edge_start": [0, 1]})
    config = {
        "dt_ms": 1.0, "tau_membrane_ms": 10.0, "threshold": 1.0,
        "reset_voltage": 0.0, "refractory_ms": 1.0, "bias_current": 0.0,
        "noise_std": 0.0, "random_seed": 1, "weight_mode": "post_normalized",
        "recurrent_gain": 1.1, "propagation_backend": "scipy_csr",
    }
    network = FloatLIFNetwork(neurons, synapses, offsets, config)
    result = network.simulate(
        external_current=np.array([1.1, 0.0, 0.0]), input_indices=np.array([0]),
        groups={"all": np.array([0, 1])}, trace_indices=np.array([0, 1]),
    )
    assert result.spike_times.tolist() == [0, 1]
    assert result.spike_neurons.tolist() == [0, 1]


@pytest.mark.parametrize("backend", ["scipy_csr", "event_traversal"])
def test_silencing_clamps_driven_neuron_without_changing_other_weights(backend):
    neurons = pd.DataFrame({"neuron_index": [0, 1, 2]})
    synapses = pd.DataFrame({"pre_index": [0, 1], "post_index": [2, 2],
                             "synapse_count": [1, 3], "nt_model_sign": [1, 1]})
    offsets = pd.DataFrame({"pre_index": [0, 1, 2], "edge_count": [1, 1, 0],
                            "edge_start": [0, 1, 2]})
    config = {"dt_ms": 1., "tau_membrane_ms": 20., "threshold": 1.,
              "reset_voltage": 0., "refractory_ms": 1., "bias_current": 0.,
              "noise_std": 0., "random_seed": 1, "weight_mode": "post_normalized",
              "recurrent_gain": 2., "propagation_backend": backend}
    net = FloatLIFNetwork(neurons, synapses, offsets, config)
    kwargs = dict(external_current=np.array([2., 0., 0.]), input_indices=np.array([0, 1]),
                  groups={"all": np.arange(3)}, trace_indices=np.arange(3))
    intact = net.simulate(**kwargs)
    weights = net.weights.copy()
    ablated = net.simulate(**kwargs, silenced_indices=np.array([1]))
    # The remaining input contributes 0.5, not 2.0 from accidental renormalization.
    assert ablated.spike_neurons.tolist() == [0]
    assert 2 in intact.spike_neurons
    assert np.all(ablated.voltage_traces[:, 1] == 0)
    np.testing.assert_array_equal(net.weights, weights)
    repeat = net.simulate(**kwargs)
    np.testing.assert_array_equal(repeat.spike_neurons, intact.spike_neurons)
    np.testing.assert_array_equal(repeat.spike_times, intact.spike_times)
    with pytest.raises(ValueError, match="out-of-range"):
        net.simulate(**kwargs, silenced_indices=np.array([-1]))
