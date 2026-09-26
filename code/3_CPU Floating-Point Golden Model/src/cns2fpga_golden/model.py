"""Deterministic discrete-time floating-point LIF execution engine."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix


@dataclass(frozen=True)
class SimulationResult:
    spike_times: np.ndarray
    spike_neurons: np.ndarray
    group_activity: dict[str, np.ndarray]
    trace_indices: np.ndarray
    voltage_traces: np.ndarray
    max_abs_voltage: float


class FloatLIFNetwork:
    def __init__(self, neurons: pd.DataFrame, synapses: pd.DataFrame, offsets: pd.DataFrame, config: dict):
        self.neurons = neurons
        self.synapses = synapses
        self.offsets = offsets
        self.config = config
        self.n = len(neurons)
        expected = np.arange(self.n)
        if not np.array_equal(neurons.neuron_index.to_numpy(), expected):
            raise ValueError("neuron_index must be contiguous and zero based")
        if len(offsets) != self.n or int(offsets.edge_count.sum()) != len(synapses):
            raise ValueError("CSR offsets do not cover the complete synapse table")
        self.pre = synapses.pre_index.to_numpy(dtype=np.int32)
        self.post = synapses.post_index.to_numpy(dtype=np.int32)
        self.starts = offsets.edge_start.to_numpy(dtype=np.int64)
        self.counts = offsets.edge_count.to_numpy(dtype=np.int32)
        self.weights = self._prepare_weights()
        self.weight_matrix = csr_matrix(
            (self.weights, (self.pre, self.post)), shape=(self.n, self.n), dtype=np.float64
        )

    def _prepare_weights(self) -> np.ndarray:
        raw = (
            self.synapses.synapse_count.to_numpy(dtype=np.float64)
            * self.synapses.nt_model_sign.to_numpy(dtype=np.float64)
        )
        mode = self.config["weight_mode"]
        gain = float(self.config["recurrent_gain"])
        if mode == "raw_linear":
            return gain * raw
        if mode == "post_normalized":
            incoming = np.bincount(self.post, weights=np.abs(raw), minlength=self.n)
            denominator = incoming[self.post]
            return np.divide(gain * raw, denominator, out=np.zeros_like(raw), where=denominator > 0)
        raise ValueError(f"Unsupported weight_mode: {mode}")

    def _propagate(self, previous_spikes: np.ndarray) -> np.ndarray:
        if self.config.get("propagation_backend", "scipy_csr") == "scipy_csr":
            return np.asarray(previous_spikes.astype(np.float64) @ self.weight_matrix).ravel()
        active = np.flatnonzero(previous_spikes)
        current = np.zeros(self.n, dtype=np.float64)
        # Sparse event traversal is efficient for the intended spiking regime.
        if len(active) < max(1, self.n // 8):
            for source in active:
                start = self.starts[source]
                count = self.counts[source]
                if count:
                    selection = slice(start, start + count)
                    np.add.at(current, self.post[selection], self.weights[selection])
            return current
        # Dense fallback avoids thousands of Python iterations during population bursts.
        edge_activity = previous_spikes[self.pre]
        return np.bincount(
            self.post, weights=self.weights * edge_activity, minlength=self.n
        ).astype(np.float64, copy=False)

    def simulate(self, external_current: np.ndarray, input_indices: np.ndarray,
                 groups: dict[str, np.ndarray], trace_indices: np.ndarray,
                 silenced_indices: np.ndarray | None = None) -> SimulationResult:
        # Clamp neuron state, without rebuilding or renormalizing intact weights.
        silenced = np.zeros(self.n, dtype=bool)
        if silenced_indices is not None:
            selected = np.asarray(silenced_indices)
            if selected.ndim != 1 or (selected.size and not np.issubdtype(selected.dtype, np.integer)):
                raise ValueError("silenced_indices must be a one-dimensional integer array")
            if selected.size and (np.any(selected < 0) or np.any(selected >= self.n)):
                raise ValueError("silenced_indices contains an out-of-range neuron index")
            silenced[selected.astype(np.int64)] = True
        dt = float(self.config["dt_ms"])
        decay = float(np.exp(-dt / float(self.config["tau_membrane_ms"])))
        threshold = float(self.config["threshold"])
        reset = float(self.config["reset_voltage"])
        refractory_steps = int(round(float(self.config["refractory_ms"]) / dt))
        bias = float(self.config["bias_current"])
        noise_std = float(self.config["noise_std"])
        rng = np.random.default_rng(int(self.config["random_seed"]))
        voltage = np.full(self.n, reset, dtype=np.float64)
        refractory = np.zeros(self.n, dtype=np.int32)
        previous = np.zeros(self.n, dtype=bool)
        group_activity = {name: np.zeros(len(external_current), dtype=np.int32) for name in groups}
        voltage_traces = np.zeros((len(external_current), len(trace_indices)), dtype=np.float64)
        event_times: list[np.ndarray] = []
        event_neurons: list[np.ndarray] = []
        max_abs_voltage = 0.0

        for timestep, amplitude in enumerate(external_current):
            active = (refractory == 0) & ~silenced
            synaptic = self._propagate(previous)
            drive = synaptic + bias
            if amplitude:
                drive[input_indices] += float(amplitude)
            if noise_std:
                drive += rng.normal(0.0, noise_std, self.n)
            voltage[active] = decay * voltage[active] + drive[active]
            voltage[~active] = reset
            if not np.isfinite(voltage).all():
                raise FloatingPointError(f"Non-finite membrane voltage at timestep {timestep}")
            spikes = active & (voltage >= threshold)
            spike_indices = np.flatnonzero(spikes).astype(np.int32)
            if len(spike_indices):
                event_times.append(np.full(len(spike_indices), timestep, dtype=np.int32))
                event_neurons.append(spike_indices)
            for name, indices in groups.items():
                group_activity[name][timestep] = int(spikes[indices].sum())
            voltage_traces[timestep] = voltage[trace_indices]
            max_abs_voltage = max(max_abs_voltage, float(np.max(np.abs(voltage))))
            refractory[refractory > 0] -= 1
            refractory[spikes] = refractory_steps
            voltage[spikes] = reset
            previous = spikes

        return SimulationResult(
            spike_times=np.concatenate(event_times) if event_times else np.empty(0, dtype=np.int32),
            spike_neurons=np.concatenate(event_neurons) if event_neurons else np.empty(0, dtype=np.int32),
            group_activity=group_activity,
            trace_indices=trace_indices,
            voltage_traces=voltage_traces,
            max_abs_voltage=max_abs_voltage,
        )
