"""Run structural, IPI-tuning and ablation checks on the step-3 Golden Model."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd
import scipy

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from cns2fpga_plausibility.checks import (
    CheckResult, evaluate_ipi_tuning, percent_drop, silence_neurons,
)
from cns2fpga_plausibility.plots import plot_ablation, plot_dashboard, plot_tuning


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "configs" / "courtship_song_equal_pulse_v1.json")
    parser.add_argument("--output-dir", type=Path)
    return parser.parse_args()


def resolve_paths(config_path: Path, config: dict) -> dict[str, Path]:
    return {name: (config_path.parent / value).resolve() for name, value in config["paths"].items()}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def output_rate(summary: dict) -> float:
    counts = summary["pIP10_neurons"] + summary["pMP2_neurons"]
    spikes = summary["pIP10_spikes"] + summary["pMP2_spikes"]
    duration_s = float(summary["duration_ms"]) / 1000.0
    return float(spikes / (counts * duration_s)) if counts else 0.0


def build_report(config: dict, checks: pd.DataFrame, baseline: pd.DataFrame,
                 ablations: pd.DataFrame, nt_summary: pd.DataFrame,
                 elapsed: float) -> str:
    fail_count = int(checks.status.eq("FAIL").sum())
    pass_count = int(checks.status.eq("PASS").sum())
    warn_count = int(checks.status.eq("WARN").sum())
    verdict = "NOT YET BIOLOGICALLY PLAUSIBLE" if fail_count else "BASIC PLAUSIBILITY CHECKS PASSED"
    rows = "\n".join(
        f"| {row.category} | `{row.check_id}` | **{row.status}** | {row.observed} | {row.expected} |"
        for row in checks.itertuples(index=False)
    )
    tuning_rows = "\n".join(
        f"| {row.ipi_ms:g} | {row.aPN1_mean_rate_hz:.3f} | {row.vPN1_mean_rate_hz:.3f} | {row.pC1_mean_rate_hz:.3f} | {row.pIP10_mean_rate_hz:.3f} | {row.pMP2_mean_rate_hz:.3f} |"
        for row in baseline.itertuples(index=False)
    )
    targeted = ablations[~ablations.kind.eq("random_control")]
    ablation_rows = "\n".join(
        f"| {row.label} | {row.ablated_neurons:,} | {row.output_rate_hz:.3f} | {row.output_drop_percent:.2f}% |"
        for row in targeted.itertuples(index=False)
    )
    nt_rows = "\n".join(
        f"| {row.consensus_nt} | {row.neurons:,} | {row.positive:,} | {row.negative:,} | {row.zero:,} |"
        for row in nt_summary.itertuples(index=False)
    )
    return f"""# Courtship-song basic biological-plausibility audit

## Verdict

**{verdict}** — {pass_count} passed, {fail_count} failed, {warn_count} warnings.

The network is executable and its populations respond differently to IPI, but this audit does not support a claim that it currently reproduces the known courtship-song transformation. The result is intentionally conservative: firing rates from a simple connectome-constrained LIF model are treated as qualitative, not as direct calcium or behavioural units.

## Checks

| Category | Check | Status | Observed | Expected |
| --- | --- | --- | --- | --- |
{rows}

## IPI response

| IPI (ms) | aPN1 (Hz) | vPN1 (Hz) | pC1 (Hz) | pIP10 (Hz) | pMP2 (Hz) |
| ---: | ---: | ---: | ---: | ---: | ---: |
{tuning_rows}

The experimental constraints used here are: behaviour peaks near 35 ms; vPN1 attenuates IPIs below 25 ms; pC1 has a 35–65 ms high-response band and is attenuated at short and very long IPIs. With only 16/36/56-ms model conditions, the comparison is an inequality/trend test, not a numeric correlation. Raw per-fly experimental values were not distributed with the local article, so no values were guessed or digitized.

## In-silico ablation at 36 ms

| Ablation | Neurons | Output proxy (Hz) | Drop from intact |
| --- | ---: | ---: | ---: |
{ablation_rows}

The output proxy is the combined per-neuron mean firing rate of pIP10 and pMP2. It is not the chaining behavioural index. The pC1 test therefore asks whether this implementation gives pC1 a specific causal influence on the selected downstream readout; it does not directly reproduce the behavioural ablation experiment.

## Neurotransmitter/sign audit

| Consensus transmitter | Neurons | Sign +1 | Sign -1 | Sign 0 |
| --- | ---: | ---: | ---: | ---: |
{nt_rows}

The 2024 whole-brain LIF model treats GABA and glutamate as inhibitory and acetylcholine as excitatory. This audit reports any disagreement instead of silently changing the frozen step-2 IR.

## Main limitations and next correction

1. Expand the IPI sweep to at least 15, 25, 35, 45, 55, 65, 75, 85 and 95 ms with an equal number of pulses per condition. The current fixed-duration stimulus confounds IPI with pulse count.
2. Do not treat pIP10+pMP2 firing as the published chaining index. Their combined response does not peak at 36 ms, so either identify a connectome-supported chaining readout or state that these are downstream courtship-output proxies only.
3. Obtain raw experimental values or perform a documented figure-digitization step before reporting Pearson correlation. The present audit intentionally tests only published qualitative inequalities.
4. The aPN1/vPN1 alias mapping and the acetylcholine/GABA/glutamate sign policy are now resolved and provenance-tracked; keep both frozen in later fixed-point and RTL stages.

Runtime: {elapsed:.3f} seconds.
"""


def main() -> None:
    args = parse_args()
    config_path = args.config.resolve()
    config = json.loads(config_path.read_text(encoding="utf-8"))
    if config.get("schema_version") == 1:
        from run_equal_pulse_validation import run
        run(config_path, args.output_dir)
        return
    paths = resolve_paths(config_path, config)
    missing = [str(path) for path in paths.values() if not path.is_file() and path.name != "src"]
    if not paths["golden_src"].is_dir():
        missing.append(str(paths["golden_src"]))
    if missing:
        raise FileNotFoundError("Missing validation input(s):\n" + "\n".join(missing))
    sys.path.insert(0, str(paths["golden_src"]))
    from cns2fpga_golden.analysis import condition_summary, select_groups
    from cns2fpga_golden.model import FloatLIFNetwork
    from cns2fpga_golden.stimulus import build_conditions

    golden = json.loads(paths["golden_config"].read_text(encoding="utf-8"))
    neurons = pd.read_csv(paths["neuron_table"])
    synapses = pd.read_csv(paths["synapse_table"])
    offsets = pd.read_csv(paths["offset_table"])
    groups = select_groups(neurons, golden["observations"])
    validation = config["validation"]
    output = (args.output_dir or ROOT / "outputs" / config["name"]).resolve()
    output.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()

    network = FloatLIFNetwork(neurons, synapses, offsets, golden["model"])
    conditions = build_conditions(golden["stimulus"], golden["model"])
    condition_by_ipi = {float(item.parameter_value): item for item in conditions}
    summaries: list[dict] = []
    raw_results = {}
    observed_groups = groups
    for condition in conditions:
        result = network.simulate(condition.current, groups["auditory_input"], observed_groups, np.empty(0, np.int32))
        row = condition_summary(condition, result, observed_groups, float(golden["model"]["duration_ms"]))
        row["duration_ms"] = float(golden["model"]["duration_ms"])
        summaries.append(row)
        raw_results[float(condition.parameter_value)] = result
    baseline = pd.DataFrame(summaries).sort_values("ipi_ms")
    baseline.to_csv(output / "baseline_response.csv", index=False)

    checks: list[CheckResult] = []
    def add(category: str, check_id: str, status: str, observed: str,
            expected: str, evidence: str, details: str = "") -> None:
        checks.append(CheckResult(category, check_id, status, observed, expected, evidence, details))

    # Structural pathway and sign checks.
    add("structure", "auditory_input_present", "PASS" if len(groups["auditory_input"]) else "FAIL",
        f"{len(groups['auditory_input'])} JO-A/JO-B anchors", ">0 auditory inputs", "courtship_2015")
    add("structure", "aPN1_present", "PASS" if len(groups["aPN1"]) else "FAIL",
        f"{len(groups['aPN1'])} labeled aPN1 neurons", ">0 explicit aPN1 neurons", "courtship_2015")
    add("structure", "vPN1_present", "PASS" if len(groups["vPN1"]) else "FAIL",
        f"{len(groups['vPN1'])} labeled vPN1 neurons", ">0 explicit vPN1 neurons", "courtship_2015")
    add("structure", "pC1_present", "PASS" if len(groups["pC1"]) else "FAIL",
        f"{len(groups['pC1'])} pC1 neurons", ">0 pC1 neurons", "courtship_2015")
    output_count = len(groups["pIP10"]) + len(groups["pMP2"])
    add("structure", "selected_outputs_present", "PASS" if output_count else "FAIL",
        f"{output_count} pIP10/pMP2 neurons", ">0 selected outputs", "project_definition")
    signed_fraction = float(neurons.nt_model_sign.ne(0).mean())
    add("sign", "signed_neuron_coverage",
        "PASS" if signed_fraction >= float(validation["minimum_signed_neuron_fraction"]) else "FAIL",
        f"{signed_fraction:.3%}", f">={float(validation['minimum_signed_neuron_fraction']):.1%}",
        "lif_2024")
    for transmitter, expected_sign in [("acetylcholine", 1), ("gaba", -1), ("glutamate", -1)]:
        subset = neurons[neurons.consensus_nt.eq(transmitter)]
        match = float(subset.nt_model_sign.eq(expected_sign).mean()) if len(subset) else 0.0
        add("sign", f"{transmitter}_sign", "PASS" if match >= 0.99 else "FAIL",
            f"{match:.1%} mapped to {expected_sign:+d} (n={len(subset)})", f">=99% mapped to {expected_sign:+d}",
            "lif_2024")

    # IPI selectivity and qualitative tuning checks.
    p_tuning = evaluate_ipi_tuning(
        baseline, "pC1", float(validation["preferred_ipi_ms"]),
        float(validation["short_ipi_ms"]), float(validation["long_ipi_ms"]),
    )
    pC1_modulation = p_tuning["dynamic_range_hz"] / max(
        p_tuning["preferred_rate_hz"], p_tuning["short_rate_hz"], p_tuning["long_rate_hz"]
    )
    add("dynamics", "pC1_ipi_discrimination",
        "PASS" if pC1_modulation >= float(validation["minimum_pC1_modulation_fraction"]) else "FAIL",
        f"normalized range={pC1_modulation:.1%} ({p_tuning['dynamic_range_hz']:.3f} Hz)",
        f">={float(validation['minimum_pC1_modulation_fraction']):.0%} normalized modulation",
        "courtship_2015")
    add("dynamics", "pC1_short_ipi_attenuation", "PASS" if p_tuning["preferred_over_short"] else "FAIL",
        f"36 ms={p_tuning['preferred_rate_hz']:.3f} Hz; 16 ms={p_tuning['short_rate_hz']:.3f} Hz",
        "36-ms response > 16-ms response", "courtship_2015")
    add("dynamics", "pC1_three_point_bandpass",
        "PASS" if p_tuning["preferred_over_short"] and p_tuning["preferred_over_long"] else "FAIL",
        f"16/36/56 ms={p_tuning['short_rate_hz']:.3f}/{p_tuning['preferred_rate_hz']:.3f}/{p_tuning['long_rate_hz']:.3f} Hz",
        "36 ms exceeds both 16 and 56 ms", "courtship_2015")
    output_curve = baseline.apply(lambda row: output_rate(row.to_dict()), axis=1)
    output_by_ipi = pd.Series(output_curve.to_numpy(), index=baseline.ipi_ms.to_numpy())
    output_short = float(output_by_ipi.loc[float(validation["short_ipi_ms"])])
    output_preferred = float(output_by_ipi.loc[float(validation["preferred_ipi_ms"])])
    output_long = float(output_by_ipi.loc[float(validation["long_ipi_ms"])])
    output_peak_ok = output_preferred > output_short and output_preferred > output_long
    add("dynamics", "output_proxy_conspecific_peak", "PASS" if output_peak_ok else "WARN",
        f"16/36/56 ms={output_short:.3f}/{output_preferred:.3f}/{output_long:.3f} Hz",
        "pIP10+pMP2 proxy at 36 ms exceeds both 16 and 56 ms", "courtship_2015",
        "Downstream firing is only a proxy for the published chaining behavior.")
    if len(groups["vPN1"]):
        v_tuning = evaluate_ipi_tuning(baseline, "vPN1", float(validation["preferred_ipi_ms"]),
                                       float(validation["short_ipi_ms"]), float(validation["long_ipi_ms"]))
        add("dynamics", "vPN1_short_ipi_attenuation", "PASS" if v_tuning["preferred_over_short"] else "FAIL",
            f"36 ms={v_tuning['preferred_rate_hz']:.3f} Hz; 16 ms={v_tuning['short_rate_hz']:.3f} Hz",
            "36-ms response > 16-ms response", "courtship_2015")
    else:
        add("dynamics", "vPN1_short_ipi_attenuation", "WARN", "not testable: vPN1 group is empty",
            "36-ms response > 16-ms response", "courtship_2015")

    # Targeted and matched-random ablations at the preferred IPI.
    preferred_ipi = float(validation["preferred_ipi_ms"])
    preferred_condition = condition_by_ipi[preferred_ipi]
    base_row = baseline.set_index("ipi_ms").loc[preferred_ipi].to_dict()
    base_output = output_rate(base_row)
    ablation_rows: list[dict] = []

    def simulate_ablation(label: str, kind: str, indices: np.ndarray, replicate: int) -> dict:
        ablated_synapses = silence_neurons(synapses, indices)
        ablated_network = FloatLIFNetwork(neurons, ablated_synapses, offsets, golden["model"])
        result = ablated_network.simulate(
            preferred_condition.current, groups["auditory_input"], observed_groups, np.empty(0, np.int32)
        )
        row = condition_summary(preferred_condition, result, observed_groups, float(golden["model"]["duration_ms"]))
        row["duration_ms"] = float(golden["model"]["duration_ms"])
        rate = output_rate(row)
        return {"label": label, "kind": kind, "replicate": replicate,
                "ablated_neurons": int(len(indices)), "output_rate_hz": rate,
                "output_drop_percent": percent_drop(base_output, rate)}

    ablation_rows.append(simulate_ablation("pC1", "targeted", groups["pC1"], 0))
    ablation_rows.append(simulate_ablation("auditory_input", "targeted", groups["auditory_input"], 0))
    excluded = np.unique(np.concatenate([groups["auditory_input"], groups["pC1"], groups["pIP10"], groups["pMP2"]]))
    candidates = np.setdiff1d(neurons.neuron_index.to_numpy(dtype=np.int32), excluded)
    rng = np.random.default_rng(int(validation["random_seed"]))
    for replicate in range(int(validation["random_ablation_replicates"])):
        indices = rng.choice(candidates, size=len(groups["pC1"]), replace=False)
        ablation_rows.append(simulate_ablation(f"random_{replicate:02d}", "random_control", indices, replicate))
    ablations = pd.DataFrame(ablation_rows)
    ablations.to_csv(output / "ablation_results.csv", index=False)
    pC1_drop = float(ablations.loc[ablations.label.eq("pC1"), "output_drop_percent"].iloc[0])
    input_drop = float(ablations.loc[ablations.label.eq("auditory_input"), "output_drop_percent"].iloc[0])
    random_95 = float(np.percentile(ablations.loc[ablations.kind.eq("random_control"), "output_drop_percent"], 95))
    add("ablation", "pC1_output_influence",
        "PASS" if pC1_drop >= float(validation["minimum_pC1_output_drop_percent"]) else "FAIL",
        f"{pC1_drop:.2f}% pIP10+pMP2 rate drop",
        f">={float(validation['minimum_pC1_output_drop_percent']):g}%", "courtship_2015")
    add("ablation", "pC1_specificity_vs_random", "PASS" if pC1_drop > random_95 else "FAIL",
        f"pC1={pC1_drop:.2f}%; random 95th percentile={random_95:.2f}%",
        "pC1 drop > matched-random 95th percentile", "lif_2024")
    add("ablation", "auditory_input_necessity",
        "PASS" if input_drop >= float(validation["minimum_input_output_drop_percent"]) else "FAIL",
        f"{input_drop:.2f}% pIP10+pMP2 rate drop",
        f">={float(validation['minimum_input_output_drop_percent']):g}%", "project_definition")

    check_table = pd.DataFrame([item.as_dict() for item in checks])
    check_table.to_csv(output / "validation_checks.csv", index=False)
    nt_summary = (
        neurons.groupby("consensus_nt", dropna=False).nt_model_sign
        .agg(neurons="size", positive=lambda x: int((x > 0).sum()),
             negative=lambda x: int((x < 0).sum()), zero=lambda x: int((x == 0).sum()))
        .reset_index().sort_values("neurons", ascending=False)
    )
    nt_summary.to_csv(output / "neurotransmitter_sign_audit.csv", index=False)
    reference_rows = []
    for evidence_id, item in config["literature"].items():
        for constraint in item["constraints"]:
            reference_rows.append({"evidence_id": evidence_id, "citation": item["citation"], "constraint": constraint})
    pd.DataFrame(reference_rows).to_csv(output / "reference_constraints.csv", index=False)
    plot_tuning(output, baseline)
    plot_ablation(output, ablations)
    plot_dashboard(output, check_table, nt_summary)
    elapsed = time.perf_counter() - started
    report = build_report(config, check_table, baseline, ablations, nt_summary, elapsed)
    (output / "report.md").write_text(report, encoding="utf-8")
    metadata = {
        "config": config,
        "config_sha256": sha256(config_path),
        "input_sha256": {name: sha256(path) for name, path in paths.items() if path.is_file()},
        "versions": {"numpy": np.__version__, "pandas": pd.__version__,
                     "scipy": scipy.__version__, "matplotlib": matplotlib.__version__},
        "runtime_seconds": elapsed,
        "verdict": "FAIL" if check_table.status.eq("FAIL").any() else "PASS",
        "status_counts": check_table.status.value_counts().to_dict(),
    }
    (output / "run_metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(report)
    print(f"Wrote plausibility audit to {output}")


if __name__ == "__main__":
    main()
