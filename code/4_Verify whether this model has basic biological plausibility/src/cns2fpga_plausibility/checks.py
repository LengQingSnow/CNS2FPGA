"""Pure validation helpers shared by the CLI and tests."""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class CheckResult:
    category: str
    check_id: str
    status: str
    observed: str
    expected: str
    evidence_id: str
    details: str

    def as_dict(self) -> dict[str, str]:
        return asdict(self)


def silence_neurons(synapses: pd.DataFrame, neuron_indices: np.ndarray) -> pd.DataFrame:
    """Return an edge table in which all edges touching selected neurons are disabled."""
    result = synapses.copy()
    selected = np.asarray(neuron_indices, dtype=np.int32)
    mask = result.pre_index.isin(selected) | result.post_index.isin(selected)
    result.loc[mask, "nt_model_sign"] = 0
    return result


def percent_drop(baseline: float, perturbed: float) -> float:
    if baseline <= 0:
        return 0.0
    return 100.0 * (baseline - perturbed) / baseline


def normalized_curve(values: np.ndarray) -> np.ndarray:
    values = np.asarray(values, dtype=np.float64)
    maximum = float(np.max(values)) if len(values) else 0.0
    return values / maximum if maximum > 0 else np.zeros_like(values)


def evaluate_ipi_tuning(summary: pd.DataFrame, group: str,
                        preferred_ipi_ms: float, short_ipi_ms: float,
                        long_ipi_ms: float) -> dict[str, float | bool]:
    """Evaluate the three-point qualitative band-pass constraint from Zhou et al. 2015."""
    indexed = summary.set_index("ipi_ms")
    column = f"{group}_mean_rate_hz"
    preferred = float(indexed.loc[preferred_ipi_ms, column])
    short = float(indexed.loc[short_ipi_ms, column])
    long = float(indexed.loc[long_ipi_ms, column])
    return {
        "preferred_rate_hz": preferred,
        "short_rate_hz": short,
        "long_rate_hz": long,
        "preferred_over_short": preferred > short,
        "preferred_over_long": preferred > long,
        "dynamic_range_hz": max(preferred, short, long) - min(preferred, short, long),
    }
