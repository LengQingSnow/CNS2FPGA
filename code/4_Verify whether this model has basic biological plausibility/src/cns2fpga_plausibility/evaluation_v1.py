"""Predeclared direction tests; independent counts are not a biological score."""

from __future__ import annotations

import numpy as np
import pandas as pd

from .protocol import drop_percent


def check(check_id, category, passed, observed, expected, basis, gate=True):
    return dict(check_id=check_id, category=category,
                status="NOT_EVALUABLE" if passed is None else ("PASS" if passed else "FAIL"),
                gate=gate, observed=observed, expected=expected, basis=basis)


def tuning_checks(baseline: pd.DataFrame, config: dict) -> list[dict]:
    output = []
    protocol = config["protocol"]
    tolerance = config["numerical_tolerance"]
    indexed = baseline.set_index(["group", "ipi_ms"])
    for rule in config["tuning_rules"]:
        for metric in [protocol["primary_metric"], protocol["secondary_metric"]]:
            reference = float(indexed.loc[(rule["group"], rule["reference_ipi_ms"]), metric])
            values = [float(indexed.loc[(rule["group"], ipi), metric])
                      for ipi in rule["lower_response_ipi_ms"]]
            finite = np.isfinite([reference, *values]).all()
            passed = bool(reference > tolerance and all(reference - value > tolerance for value in values)) if finite else None
            output.append(check(
                rule["id"] + "/" + metric, "literature_proxy", passed,
                f"reference={reference:.6g}; competitors={','.join(f'{x:.6g}' for x in values)}",
                f"{rule['group']} {rule['reference_ipi_ms']} ms > each of {rule['lower_response_ipi_ms']} ms",
                "Zhou 2015 Fig 5H/6K direction applied to a spike proxy; not a calcium/statistical replication",
                gate=metric == protocol["primary_metric"],
            ))
    return output


def overall_verdict(checks: pd.DataFrame) -> str:
    gates = checks[checks.gate]
    if gates.empty:
        return "INCOMPLETE"
    if gates.status.eq("FAIL").any():
        return "NOT_SUPPORTED"
    if not gates.status.eq("PASS").all():
        return "INCOMPLETE"
    return "CONDITIONAL_SUPPORT"


def ablation_effects(baseline: pd.DataFrame, perturbed: pd.DataFrame, config: dict) -> pd.DataFrame:
    index = baseline.set_index(["group", "ipi_ms"])
    rows = []
    for record in perturbed.to_dict("records"):
        for metric in [config["protocol"]["primary_metric"], config["protocol"]["ablation_metric"]]:
            before = float(index.loc[(record["group"], record["ipi_ms"]), metric])
            after = float(record[metric])
            rows.append({**{key: record[key] for key in ["condition_id", "target", "kind", "replicate", "ipi_ms", "group", "ablated_neurons"]},
                         "metric": metric, "baseline": before, "ablated": after,
                         "drop_percent": drop_percent(before, after),
                         "evaluable": bool(np.isfinite(before) and np.isfinite(after) and before > config["numerical_tolerance"])})
    return pd.DataFrame(rows)


def compare_random_controls(effects: pd.DataFrame, config: dict) -> pd.DataFrame:
    reference = config["ablation"]["reference_ipi_ms"]
    table = effects[effects.ipi_ms.eq(reference)]
    rows = []
    for target in config["ablation"]["random_targets"]:
        for group in ["pC1", "pIP10", "pMP2", "output_combined_exploratory"]:
            if group == target:
                continue
            for metric in [config["protocol"]["primary_metric"], config["protocol"]["ablation_metric"]]:
                subset = table[table.target.eq(target) & table.group.eq(group) & table.metric.eq(metric)]
                target_rows = subset[subset.kind.eq("targeted")]
                controls = subset[subset.kind.eq("random_control")].drop_percent.to_numpy(float)
                controls = controls[np.isfinite(controls)]
                actual = float(target_rows.iloc[0].drop_percent) if len(target_rows) else float("nan")
                valid = bool(np.isfinite(actual) and len(controls))
                rows.append(dict(target=target, group=group, metric=metric,
                    targeted_drop_percent=actual, random_n=len(controls),
                    random_median_drop_percent=float(np.median(controls)) if valid else np.nan,
                    random_95th_percentile=float(np.percentile(controls, 95)) if valid else np.nan,
                    controls_at_least_target=int(np.sum(controls >= actual)) if valid else np.nan,
                    interpretation="Descriptive control distribution only; not independent biological replicates or a significance test"))
    return pd.DataFrame(rows)
