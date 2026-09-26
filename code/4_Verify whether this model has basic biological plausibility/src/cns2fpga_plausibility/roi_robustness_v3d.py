"""Readout-set sensitivity analysis over locked spike-event archives."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .roi_mapping_v3 import candidate_masks


def build_membership(neurons, neuronbridge_summary, best_rank_cutoff=100):
    """Build predeclared pC1 sensitivity sets in frozen neuron-index space."""
    masks = candidate_masks(neurons)
    nb = neuronbridge_summary.copy()
    nb["bodyId"] = nb["bodyId"].astype("int64")
    any_hit = set(nb.loc[nb["in_frozen_ir"].astype(bool), "bodyId"])
    best_hit = set(nb.loc[nb["in_frozen_ir"].astype(bool) & nb["best_rank"].le(best_rank_cutoff), "bodyId"])
    masks["pC1_neuronbridge_any_hit"] = neurons["bodyId"].isin(any_hit)
    masks[f"pC1_neuronbridge_best_rank_le_{best_rank_cutoff}"] = neurons["bodyId"].isin(best_hit)
    rows = neurons.loc[masks["pC1_type_all"], ["neuron_index", "bodyId", "type", "somaSide", "fruDsx", "synonyms"]].copy()
    rank_map = nb.drop_duplicates("bodyId").set_index("bodyId")["best_rank"]
    rows["neuronbridge_best_rank"] = rows["bodyId"].map(rank_map).astype("Int64")
    for name, mask in masks.items():
        rows[name] = rows["bodyId"].isin(set(neurons.loc[mask, "bodyId"]))
    groups = {
        name: neurons.loc[mask, "neuron_index"].to_numpy(dtype=np.int64)
        for name, mask in masks.items()
    }
    return rows.reset_index(drop=True), groups


def counts_from_events(spike_times, spike_neurons, members, duration):
    """Rebuild one population count series from complete network events."""
    spike_times = np.asarray(spike_times)
    spike_neurons = np.asarray(spike_neurons)
    members = np.asarray(members, dtype=np.int64)
    if spike_times.shape != spike_neurons.shape:
        raise ValueError("spike_times and spike_neurons must have the same shape")
    if duration <= 0 or (len(spike_times) and (spike_times.min() < 0 or spike_times.max() >= duration)):
        raise ValueError("Spike time lies outside the declared trial duration")
    selected = np.isin(spike_neurons, members)
    return np.bincount(spike_times[selected].astype(np.int64), minlength=duration).astype(np.int64)


def sign_with_tolerance(value, tolerance=1e-12):
    if not np.isfinite(value) or abs(value) <= tolerance:
        return 0
    return 1 if value > 0 else -1


def tuning_checks(response_summary, reference_ipi=35.0, comparison_ipis=(15.0, 25.0, 85.0, 95.0), metrics=("peak_rate_hz", "evoked_spikes_per_neuron_per_pulse")):
    """Compare each intact readout with the same fixed 35-ms reference."""
    intact = response_summary.loc[response_summary["condition_id"].eq("intact")]
    rows = []
    for group, grouped in intact.groupby("candidate_id"):
        indexed = grouped.set_index("ipi_ms")
        for metric in metrics:
            reference = float(indexed.loc[reference_ipi, metric])
            for ipi in comparison_ipis:
                value = float(indexed.loc[ipi, metric])
                rows.append({
                    "candidate_id": group, "metric": metric, "reference_ipi_ms": reference_ipi,
                    "comparison_ipi_ms": ipi, "reference_value": reference,
                    "comparison_value": value, "reference_greater": bool(reference > value),
                    "difference": reference - value,
                })
    return pd.DataFrame(rows)


def intervention_effects(response_summary, baseline_id="intact", tolerance=1e-12):
    """Calculate signed perturbation effects relative to intact at matched IPI/group."""
    metrics = ["response_spikes", "peak_rate_hz", "evoked_spikes_per_neuron_per_pulse"]
    baseline = response_summary.loc[response_summary.condition_id.eq(baseline_id)].set_index(["candidate_id", "ipi_ms"])
    rows = []
    for row in response_summary.loc[~response_summary.condition_id.eq(baseline_id)].itertuples(index=False):
        reference = baseline.loc[(row.candidate_id, row.ipi_ms)]
        for metric in metrics:
            base = float(reference[metric])
            perturbed = float(getattr(row, metric))
            delta = perturbed - base
            percent = float("nan") if abs(base) <= tolerance else 100.0 * delta / base
            rows.append({
                "condition_id": row.condition_id, "candidate_id": row.candidate_id,
                "ipi_ms": row.ipi_ms, "metric": metric, "intact_value": base,
                "perturbed_value": perturbed, "delta": delta, "change_percent": percent,
                "direction": sign_with_tolerance(delta, tolerance),
            })
    return pd.DataFrame(rows)


def stability_summary(tuning, effects, reference_group="pC1_type_all", reference_ipi=35.0):
    """Measure agreement with the all-pC1 engineering reference readout."""
    tuning_key = ["metric", "comparison_ipi_ms"]
    tuning_ref = tuning.loc[tuning.candidate_id.eq(reference_group)].set_index(tuning_key)["reference_greater"]
    effects_35 = effects.loc[effects.ipi_ms.eq(reference_ipi)]
    effect_key = ["condition_id", "metric"]
    effect_ref = effects_35.loc[effects_35.candidate_id.eq(reference_group)].set_index(effect_key)["direction"]
    rows = []
    for group in sorted(tuning.candidate_id.unique()):
        tg = tuning.loc[tuning.candidate_id.eq(group)].set_index(tuning_key)
        eg = effects_35.loc[effects_35.candidate_id.eq(group)].set_index(effect_key)
        tuning_agree = tg["reference_greater"].eq(tuning_ref).sum()
        effect_agree = eg["direction"].eq(effect_ref).sum()
        rows.append({
            "candidate_id": group,
            "tuning_agreements": int(tuning_agree), "tuning_comparisons": int(len(tuning_ref)),
            "tuning_agreement_fraction": float(tuning_agree / len(tuning_ref)),
            "intervention_35ms_direction_agreements": int(effect_agree),
            "intervention_35ms_direction_comparisons": int(len(effect_ref)),
            "intervention_35ms_direction_agreement_fraction": float(effect_agree / len(effect_ref)),
        })
    return pd.DataFrame(rows)
