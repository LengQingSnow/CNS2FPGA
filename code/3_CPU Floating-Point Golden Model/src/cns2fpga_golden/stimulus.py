"""Deterministic external-current generators for courtship-song experiments."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class StimulusCondition:
    name: str
    parameter_name: str
    parameter_value: float
    current: np.ndarray


def _step(time_ms: float, dt_ms: float) -> int:
    return int(round(time_ms / dt_ms))


def pulse_train(duration_ms: float, dt_ms: float, start_ms: float, stop_ms: float,
                pulse_width_ms: float, ipi_ms: float, amplitude: float) -> np.ndarray:
    steps = _step(duration_ms, dt_ms)
    current = np.zeros(steps, dtype=np.float64)
    width = max(1, _step(pulse_width_ms, dt_ms))
    for pulse_time in np.arange(start_ms, stop_ms, ipi_ms):
        begin = _step(float(pulse_time), dt_ms)
        current[begin:min(begin + width, steps)] = amplitude
    return current


def sine_burst(duration_ms: float, dt_ms: float, start_ms: float, stop_ms: float,
               frequency_hz: float, amplitude: float) -> np.ndarray:
    times = np.arange(_step(duration_ms, dt_ms), dtype=np.float64) * dt_ms
    active = (times >= start_ms) & (times < stop_ms)
    phase = 2.0 * np.pi * frequency_hz * (times - start_ms) / 1000.0
    current = np.zeros_like(times)
    current[active] = amplitude * (0.5 + 0.5 * np.sin(phase[active]))
    return current


def build_conditions(stimulus: dict, model: dict) -> list[StimulusCondition]:
    kind = stimulus["kind"]
    common = dict(
        duration_ms=float(model["duration_ms"]), dt_ms=float(model["dt_ms"]),
        start_ms=float(stimulus["start_ms"]), stop_ms=float(stimulus["stop_ms"]),
        amplitude=float(stimulus["amplitude"]),
    )
    if kind == "pulse_train":
        return [
            StimulusCondition(
                name=f"pulse_ipi_{value:g}ms", parameter_name="ipi_ms", parameter_value=float(value),
                current=pulse_train(pulse_width_ms=float(stimulus["pulse_width_ms"]), ipi_ms=float(value), **common),
            )
            for value in stimulus["ipi_ms"]
        ]
    if kind == "sine_burst":
        return [
            StimulusCondition(
                name=f"sine_{value:g}hz", parameter_name="frequency_hz", parameter_value=float(value),
                current=sine_burst(frequency_hz=float(value), **common),
            )
            for value in stimulus["frequency_hz"]
        ]
    raise ValueError(f"Unsupported stimulus kind: {kind}")
