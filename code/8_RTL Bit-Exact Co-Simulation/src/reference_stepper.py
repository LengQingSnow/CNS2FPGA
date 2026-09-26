"""State-observable stepper matching the locked step-5 fixed-point model."""

from __future__ import annotations

import numpy as np


class ReferenceStepper:
    def __init__(self, neurons, synapses, offsets, model, fmt, fixed_ops):
        self.n = len(neurons)
        self.model = model
        self.fmt = fmt
        self.quantize = fixed_ops.quantize
        self.round_shift = fixed_ops.round_shift
        self.saturate = fixed_ops.saturate
        self.pre = synapses.pre_index.to_numpy(np.int32)
        self.post = synapses.post_index.to_numpy(np.int32)
        self.starts = offsets.edge_start.to_numpy(np.int64)
        self.counts = offsets.edge_count.to_numpy(np.int32)
        raw = (synapses.synapse_count.to_numpy(np.float64)
               * synapses.nt_model_sign.to_numpy(np.float64) * float(model["recurrent_gain"]))
        self.weights = self.quantize(raw, fmt["weight_frac"])
        self.decay = int(self.quantize(
            [np.exp(-float(model["dt_ms"]) / float(model["tau_membrane_ms"]))], fmt["decay_frac"])[0])
        self.threshold = int(self.quantize([model["threshold"]], fmt["state_frac"])[0])
        self.reset = int(self.quantize([model["reset_voltage"]], fmt["state_frac"])[0])
        self.bias = int(self.quantize([model["bias_current"]], fmt["state_frac"])[0])
        self.refractory_steps = int(round(model["refractory_ms"] / model["dt_ms"]))
        self.voltage = np.full(self.n, self.reset, dtype=np.int64)
        self.syn_current = np.zeros(self.n, dtype=np.int64)
        self.refractory = np.zeros(self.n, dtype=np.int32)
        self.previous = np.zeros(self.n, dtype=bool)

    def _propagate(self, spikes: np.ndarray) -> tuple[np.ndarray, int]:
        current = np.zeros(self.n, dtype=np.int64)
        for source in np.flatnonzero(spikes):
            start, count = int(self.starts[source]), int(self.counts[source])
            if count:
                selected = slice(start, start + count)
                np.add.at(current, self.post[selected], self.weights[selected])
        return self.saturate(current, self.fmt["accumulator_bits"])

    def step(self, amplitude: float, input_indices: np.ndarray) -> dict:
        active = self.refractory == 0
        decay = self.round_shift(self.voltage * self.decay, self.fmt["decay_frac"])
        updated = decay + self.syn_current + self.bias
        amplitude_q = int(self.quantize([amplitude], self.fmt["state_frac"])[0])
        if amplitude_q:
            updated[input_indices] += amplitude_q
        self.voltage[active] = updated[active]
        self.voltage[~active] = self.reset
        self.voltage, state_saturations = self.saturate(self.voltage, self.fmt["state_bits"])
        spikes = active & (self.voltage >= self.threshold)
        self.refractory[self.refractory > 0] -= 1
        self.refractory[spikes] = self.refractory_steps
        self.voltage[spikes] = self.reset
        self.syn_current, accumulator_saturations = self._propagate(spikes)
        self.previous = spikes
        return {"spikes": spikes.copy(), "voltage": self.voltage.copy(),
                "syn_current": self.syn_current.copy(), "refractory": self.refractory.copy(),
                "state_saturations": state_saturations,
                "accumulator_saturations": accumulator_saturations}
