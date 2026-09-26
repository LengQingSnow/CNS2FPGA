"""Exact, equal-pulse stimuli and declared response windows for v1."""

from __future__ import annotations

from dataclasses import dataclass
import numpy as np


def steps(value_ms: float, dt_ms: float) -> int:
    if not np.isfinite(dt_ms) or dt_ms <= 0 or not np.isfinite(value_ms) or value_ms < 0:
        raise ValueError("Times must be finite/nonnegative and dt must be positive")
    count = int(round(value_ms / dt_ms))
    if not np.isclose(count * dt_ms, value_ms, rtol=0, atol=1e-9):
        raise ValueError(f"{value_ms} ms is not an integer multiple of dt={dt_ms}")
    return count


@dataclass(frozen=True)
class EqualPulseCondition:
    ipi_ms: float
    current: np.ndarray
    onsets: np.ndarray
    start: int
    train_end: int
    response_end: int
    pulse_width: int
    dt_ms: float

    def description(self) -> dict:
        return {
            "ipi_ms": self.ipi_ms, "pulse_count": len(self.onsets),
            "pulse_onsets_ms": (self.onsets * self.dt_ms).tolist(),
            "pulse_width_ms": self.pulse_width * self.dt_ms,
            "response_start_ms": self.start * self.dt_ms,
            "train_end_ms": self.train_end * self.dt_ms,
            "response_end_ms": self.response_end * self.dt_ms,
            "trial_duration_ms": len(self.current) * self.dt_ms,
            "current_integral": float(self.current.sum() * self.dt_ms),
        }


def build_equal_pulse_conditions(protocol: dict, dt_ms: float) -> list[EqualPulseCondition]:
    count = protocol["pulse_count"]
    if isinstance(count, bool) or not isinstance(count, int) or count < 2:
        raise ValueError("pulse_count must be an integer >= 2")
    ipis = protocol["ipi_ms"]
    if not ipis or len(set(ipis)) != len(ipis) or sorted(ipis) != ipis:
        raise ValueError("IPI values must be unique and ascending")
    start = steps(protocol["start_ms"], dt_ms)
    width = steps(protocol["pulse_width_ms"], dt_ms)
    tail = steps(protocol["tail_ms"], dt_ms)
    peak = steps(protocol["peak_window_ms"], dt_ms)
    amplitude = float(protocol["amplitude"])
    periods = [steps(ipi, dt_ms) for ipi in ipis]
    if start < peak or peak < 1 or tail < peak or width < 1 or min(periods) <= width:
        raise ValueError("Need nonoverlapping pulses, pre/tail periods >= peak window and nonzero widths")
    if not np.isfinite(amplitude) or amplitude <= 0:
        raise ValueError("amplitude must be positive and finite")
    # Identical full trial duration; summaries also report the stimulus-aligned window.
    duration = start + (count - 1) * max(periods) + width + tail
    conditions = []
    for ipi, period in zip(ipis, periods):
        onsets = start + np.arange(count, dtype=np.int64) * period
        current = np.zeros(duration, dtype=np.float64)
        for begin in onsets:
            current[begin:begin + width] = amplitude
        end = int(onsets[-1] + width)
        conditions.append(EqualPulseCondition(float(ipi), current, onsets, start,
                                               end, end + tail, width, float(dt_ms)))
    return conditions


def summarize_activity(counts: np.ndarray, silence_counts: np.ndarray, size: int,
                       condition: EqualPulseCondition, peak_window_ms: float) -> dict:
    """Count windows are [start,end); full rolling bins, no partial padding.

    Primary peak is mean-neuron spike rate, NOT deltaF/F. Silence is matched
    in duration, model parameters and ablation. All neurons (also inactive ones)
    remain in the population denominator. Missing groups produce NaNs, not zeros.
    """
    if len(counts) != len(condition.current) or len(silence_counts) != len(counts):
        raise ValueError("Population series must cover the complete trial")
    start, end = condition.start, condition.response_end
    dt_s = condition.dt_ms / 1000.
    window = steps(peak_window_ms, condition.dt_ms)
    if size <= 0:
        return {key: float("nan") for key in (
            "peak_rate_hz", "evoked_spikes_per_neuron_per_pulse", "stimulus_rate_hz",
            "response_rate_hz", "post_tail_rate_hz", "common_window_spikes_per_neuron",
            "total_spikes", "response_spikes", "silence_response_spikes", "pre_rate_hz")}
    counts = np.asarray(counts, dtype=np.float64)
    quiet = np.asarray(silence_counts, dtype=np.float64)
    evoked = counts - quiet
    sums = np.concatenate(([0.], np.cumsum(evoked[start:end])))
    rolling = sums[window:] - sums[:-window]
    response_spikes = float(counts[start:end].sum())
    silence_spikes = float(quiet[start:end].sum())
    return {
        "peak_rate_hz": float(rolling.max() / (size * window * dt_s)),
        "evoked_spikes_per_neuron_per_pulse": (response_spikes - silence_spikes) / (size * len(condition.onsets)),
        "stimulus_rate_hz": float(evoked[start:condition.train_end].sum() / (size * (condition.train_end - start) * dt_s)),
        "response_rate_hz": float(evoked[start:end].sum() / (size * (end - start) * dt_s)),
        "post_tail_rate_hz": float(evoked[end-window:end].sum() / (size * window * dt_s)),
        "common_window_spikes_per_neuron": float(evoked[start:].sum() / size),
        "pre_rate_hz": float(counts[:start].sum() / (size * start * dt_s)),
        "total_spikes": int(counts.sum()), "response_spikes": int(response_spikes),
        "silence_response_spikes": int(silence_spikes),
    }


def drop_percent(baseline: float, perturbed: float, tolerance: float = 1e-12) -> float:
    """An inactive baseline cannot support a percentage-silencing claim."""
    if not np.isfinite(baseline) or not np.isfinite(perturbed) or baseline <= tolerance:
        return float("nan")
    return 100. * (baseline - perturbed) / baseline
