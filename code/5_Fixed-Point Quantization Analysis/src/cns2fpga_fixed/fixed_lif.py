"""Deterministic integer LIF model with explicitly RTL-compatible arithmetic."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


def signed_limits(bits: int) -> tuple[int, int]:
    if bits < 2 or bits > 62:
        raise ValueError("Signed width must be in [2, 62]")
    return -(1 << (bits - 1)), (1 << (bits - 1)) - 1


def round_shift(values: np.ndarray, shift: int) -> np.ndarray:
    """Right shift with round-to-nearest, ties away from zero; negative shift widens."""
    values = np.asarray(values, dtype=np.int64)
    if shift == 0:
        return values.copy()
    if shift < 0:
        return values << (-shift)
    magnitude = np.abs(values)
    rounded = (magnitude + (1 << (shift - 1))) >> shift
    return np.where(values < 0, -rounded, rounded).astype(np.int64)


def quantize(values, frac_bits: int) -> np.ndarray:
    """Float to integer using round-to-nearest, ties away from zero."""
    scaled = np.asarray(values, dtype=np.float64) * float(1 << frac_bits)
    return np.copysign(np.floor(np.abs(scaled) + 0.5), scaled).astype(np.int64)


def saturate(values: np.ndarray, bits: int) -> tuple[np.ndarray, int]:
    low, high = signed_limits(bits)
    values = np.asarray(values, dtype=np.int64)
    clipped = np.clip(values, low, high)
    return clipped.astype(np.int64, copy=False), int(np.count_nonzero(clipped != values))


@dataclass(frozen=True)
class FixedFormat:
    name: str
    state_bits: int
    state_frac: int
    weight_bits: int
    weight_frac: int
    decay_bits: int
    decay_frac: int
    accumulator_bits: int

    @classmethod
    def from_dict(cls, value: dict) -> "FixedFormat":
        result = cls(**value)
        for field in ("state_frac", "weight_frac", "decay_frac"):
            if getattr(result, field) < 0:
                raise ValueError(f"{field} must be nonnegative")
        if result.state_frac >= result.state_bits or result.weight_frac >= result.weight_bits:
            raise ValueError("A signed fixed-point value needs at least one sign/integer bit")
        if result.decay_frac >= result.decay_bits:
            raise ValueError("Decay format needs a sign/integer bit")
        signed_limits(result.state_bits)
        signed_limits(result.weight_bits)
        signed_limits(result.decay_bits)
        signed_limits(result.accumulator_bits)
        return result

    def as_dict(self) -> dict:
        return self.__dict__.copy()


@dataclass(frozen=True)
class FixedSimulationResult:
    spike_times: np.ndarray
    spike_neurons: np.ndarray
    group_activity: dict[str, np.ndarray]
    state_saturation_events: int
    accumulator_saturation_events: int
    max_abs_state_integer: int


class FixedLIFNetwork:
    """Integer execution order: propagate -> saturate accumulator -> decay -> add -> saturate state -> spike."""

    def __init__(self, neurons: pd.DataFrame, synapses: pd.DataFrame, offsets: pd.DataFrame,
                 model_config: dict, fixed_format: FixedFormat):
        self.neurons = neurons
        self.synapses = synapses
        self.offsets = offsets
        self.model = model_config
        self.format = fixed_format
        self.n = len(neurons)
        if not np.array_equal(neurons.neuron_index.to_numpy(), np.arange(self.n)):
            raise ValueError("neuron_index must be contiguous and zero based")
        if len(offsets) != self.n or int(offsets.edge_count.sum()) != len(synapses):
            raise ValueError("CSR offsets do not cover the complete synapse table")
        if model_config["weight_mode"] != "raw_linear":
            raise ValueError("The bit-true v0 engine currently locks raw_linear weights")
        if float(model_config["noise_std"]) != 0:
            raise ValueError("Stochastic noise is outside the deterministic fixed-point contract")
        self.pre = synapses.pre_index.to_numpy(dtype=np.int32)
        self.post = synapses.post_index.to_numpy(dtype=np.int32)
        self.starts = offsets.edge_start.to_numpy(dtype=np.int64)
        self.counts = offsets.edge_count.to_numpy(dtype=np.int32)
        raw = (synapses.synapse_count.to_numpy(np.float64)
               * synapses.nt_model_sign.to_numpy(np.float64)
               * float(model_config["recurrent_gain"]))
        unbounded = quantize(raw, fixed_format.weight_frac)
        self.weights, self.weight_quantization_saturations = saturate(unbounded, fixed_format.weight_bits)
        decay = np.exp(-float(model_config["dt_ms"]) / float(model_config["tau_membrane_ms"]))
        decay_q = quantize([decay], fixed_format.decay_frac)
        self.decay_q, decay_sat = saturate(decay_q, fixed_format.decay_bits)
        self.decay_q = int(self.decay_q[0])
        self.decay_quantization_saturations = decay_sat
        self.threshold_q = int(quantize([model_config["threshold"]], fixed_format.state_frac)[0])
        self.reset_q = int(quantize([model_config["reset_voltage"]], fixed_format.state_frac)[0])
        self.bias_q = int(quantize([model_config["bias_current"]], fixed_format.state_frac)[0])

    def _propagate(self, previous: np.ndarray, weights: np.ndarray) -> tuple[np.ndarray, int]:
        current = np.zeros(self.n, dtype=np.int64)
        for source in np.flatnonzero(previous):
            start = int(self.starts[source])
            count = int(self.counts[source])
            if count:
                selection = slice(start, start + count)
                np.add.at(current, self.post[selection], weights[selection])
        current, saturated = saturate(current, self.format.accumulator_bits)
        return round_shift(current, self.format.weight_frac - self.format.state_frac), saturated

    def simulate(self, external_current: np.ndarray, input_indices: np.ndarray,
                 groups: dict[str, np.ndarray], silenced_indices: np.ndarray | None = None,
                 disabled_edge_indices: np.ndarray | None = None) -> FixedSimulationResult:
        silenced = np.zeros(self.n, dtype=bool)
        if silenced_indices is not None:
            selected = np.asarray(silenced_indices, dtype=np.int64)
            if selected.ndim != 1 or (selected.size and (selected.min() < 0 or selected.max() >= self.n)):
                raise ValueError("silenced_indices contains an invalid neuron index")
            silenced[selected] = True
        weights = self.weights
        if disabled_edge_indices is not None and len(disabled_edge_indices):
            disabled = np.asarray(disabled_edge_indices, dtype=np.int64)
            if disabled.ndim != 1 or disabled.min() < 0 or disabled.max() >= len(weights):
                raise ValueError("disabled_edge_indices contains an invalid edge index")
            weights = weights.copy()
            weights[disabled] = 0
        current_q = quantize(external_current, self.format.state_frac)
        current_q, input_saturations = saturate(current_q, self.format.state_bits)
        input_indices = np.asarray(input_indices, dtype=np.int64)
        voltage = np.full(self.n, self.reset_q, dtype=np.int64)
        refractory = np.zeros(self.n, dtype=np.int32)
        previous = np.zeros(self.n, dtype=bool)
        refractory_steps = int(round(float(self.model["refractory_ms"]) / float(self.model["dt_ms"])))
        activity = {name: np.zeros(len(current_q), dtype=np.int32) for name in groups}
        event_times: list[np.ndarray] = []
        event_neurons: list[np.ndarray] = []
        state_saturations = int(input_saturations)
        accumulator_saturations = 0
        max_abs = 0
        for timestep, amplitude_q in enumerate(current_q):
            active = (refractory == 0) & ~silenced
            synaptic_q, saturated = self._propagate(previous, weights)
            accumulator_saturations += saturated
            decayed_q = round_shift(voltage * self.decay_q, self.format.decay_frac)
            drive_q = synaptic_q + self.bias_q
            if amplitude_q:
                drive_q[input_indices] += int(amplitude_q)
            updated = decayed_q + drive_q
            voltage[active] = updated[active]
            voltage[~active] = self.reset_q
            voltage, saturated = saturate(voltage, self.format.state_bits)
            state_saturations += saturated
            spikes = active & (voltage >= self.threshold_q)
            indices = np.flatnonzero(spikes).astype(np.int32)
            if len(indices):
                event_times.append(np.full(len(indices), timestep, dtype=np.int32))
                event_neurons.append(indices)
            for name, members in groups.items():
                activity[name][timestep] = int(spikes[members].sum())
            max_abs = max(max_abs, int(np.max(np.abs(voltage))))
            refractory[refractory > 0] -= 1
            refractory[spikes] = refractory_steps
            voltage[spikes] = self.reset_q
            previous = spikes
        return FixedSimulationResult(
            spike_times=np.concatenate(event_times) if event_times else np.empty(0, np.int32),
            spike_neurons=np.concatenate(event_neurons) if event_neurons else np.empty(0, np.int32),
            group_activity=activity,
            state_saturation_events=state_saturations,
            accumulator_saturation_events=accumulator_saturations,
            max_abs_state_integer=max_abs,
        )
