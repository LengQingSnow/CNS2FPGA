"""Trial-local perturbations around the unchanged Step 3 and Step 5 models."""

from __future__ import annotations

import numpy as np

from cns2fpga_fixed.fixed_lif import quantize, saturate


def simulate_float(network, waveform, input_indices, groups, trace_indices,
                   silenced_indices=None, disabled_edge_indices=None, weight_multipliers=None):
    original_weights = network.weights
    original_backend = network.config.get("propagation_backend", "scipy_csr")
    modified = disabled_edge_indices is not None or weight_multipliers is not None
    try:
        if modified:
            weights = original_weights.copy()
            if weight_multipliers is not None:
                factors = np.asarray(weight_multipliers, dtype=np.float64)
                if factors.shape != weights.shape or not np.isfinite(factors).all() or np.any(factors < 0):
                    raise ValueError("Invalid per-edge weight multipliers")
                weights *= factors
            if disabled_edge_indices is not None and len(disabled_edge_indices):
                weights[np.asarray(disabled_edge_indices, dtype=np.int64)] = 0.0
            network.weights = weights
            # The original model's sparse-event backend uses the altered vector
            # while preserving the same accumulation order used in the v1 audit.
            network.config["propagation_backend"] = "sparse_event"
        return network.simulate(waveform, input_indices, groups, trace_indices,
                                silenced_indices=silenced_indices)
    finally:
        network.weights = original_weights
        network.config["propagation_backend"] = original_backend


def simulate_fixed(network, waveform, input_indices, groups,
                   silenced_indices=None, disabled_edge_indices=None, weight_multipliers=None):
    original_weights = network.weights
    try:
        if weight_multipliers is not None:
            factors = np.asarray(weight_multipliers, dtype=np.float64)
            if factors.shape != original_weights.shape or not np.isfinite(factors).all() or np.any(factors < 0):
                raise ValueError("Invalid per-edge weight multipliers")
            raw = (network.synapses.synapse_count.to_numpy(np.float64)
                   * network.synapses.nt_model_sign.to_numpy(np.float64)
                   * float(network.model["recurrent_gain"]))
            network.weights, _ = saturate(quantize(raw * factors, network.format.weight_frac),
                                          network.format.weight_bits)
        return network.simulate(waveform, input_indices, groups,
                                silenced_indices=silenced_indices,
                                disabled_edge_indices=disabled_edge_indices)
    finally:
        network.weights = original_weights
