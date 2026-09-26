"""Run the preregistered v1 assay against the unchanged step-3 model parameters.

The protocol/source/input lock and random neuron selections are written BEFORE
any simulation. An existing run directory cannot be overwritten. A biological
FAIL still produces a complete report; --require-pass provides a CI exit gate.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import sys
import time

import numpy as np
import pandas as pd
import scipy
import matplotlib

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from cns2fpga_plausibility.protocol import build_equal_pulse_conditions, summarize_activity
from cns2fpga_plausibility.evaluation_v1 import (
    check, tuning_checks, overall_verdict, ablation_effects, compare_random_controls,
)
from cns2fpga_plausibility.reporting_v1 import make_figures, write_report


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")


def make_ablation_plan(neurons, groups, settings):
    plan = []
    all_observed = np.unique(np.concatenate(list(groups.values())))
    candidates = np.setdiff1d(neurons.neuron_index.to_numpy(np.int32), all_observed)
    signs = neurons.nt_model_sign.to_numpy()
    rng = np.random.default_rng(settings["random_seed"])
    for target in settings["targets"]:
        plan.append(dict(condition_id=f"silence_{target}", kind="targeted", target=target,
                         replicate=0, indices=groups[target].tolist()))
    for target in settings["random_targets"]:
        unique, counts = np.unique(signs[groups[target]], return_counts=True)
        for replicate in range(settings["random_replicates"]):
            sample = []
            for sign, count in zip(unique, counts):
                available = candidates[signs[candidates] == sign]
                if len(available) < count:
                    raise ValueError(f"Not enough sign={sign} controls for {target}")
                sample.extend(rng.choice(available, size=count, replace=False).tolist())
            plan.append(dict(condition_id=f"random_{target}_{replicate:02d}", kind="random_control",
                             target=target, replicate=replicate, indices=sorted(sample)))
    for entry in plan:
        entry["body_ids"] = neurons.iloc[entry["indices"]].bodyId.astype(int).tolist()
        unique, counts = np.unique(signs[entry["indices"]], return_counts=True)
        entry["sign_counts"] = {str(int(sign)): int(count) for sign, count in zip(unique, counts)}
    return plan


def run(config_path: Path, output_dir: Path | None = None):
    started = time.perf_counter()
    config_path = config_path.resolve()
    config = json.loads(config_path.read_text(encoding="utf-8"))
    if config.get("schema_version") != 1:
        raise ValueError("This runner requires schema_version=1")
    golden_path = (config_path.parent / config["golden_config"]).resolve()
    golden_src = (config_path.parent / config["golden_src"]).resolve()
    golden = json.loads(golden_path.read_text(encoding="utf-8"))
    paths = {name: (golden_path.parent / relative).resolve() for name, relative in golden["ir"].items()}
    model = dict(golden["model"])
    if model["noise_std"] != 0 or model["bias_current"] != 0 or model["reset_voltage"] != 0:
        raise ValueError("v1 uses a deterministic, quiescent model (noise/bias/reset=0); register a new protocol for other settings")
    conditions = build_equal_pulse_conditions(config["protocol"], model["dt_ms"])
    model["duration_ms"] = len(conditions[0].current) * model["dt_ms"]
    if model["threshold"] <= 0:
        raise ValueError("Threshold must be above the quiescent reset")
    available_ipis = {item.ipi_ms for item in conditions}
    for rule in config["tuning_rules"]:
        required = {rule["reference_ipi_ms"], *rule["lower_response_ipi_ms"]}
        if not required <= available_ipis:
            raise ValueError(f"Missing IPI values for rule {rule['id']}")
    if config["ablation"]["reference_ipi_ms"] not in available_ipis:
        raise ValueError("Missing ablation reference IPI")
    if config["ablation"]["random_replicates"] < 1:
        raise ValueError("At least one random control is required")

    sys.path.insert(0, str(golden_src))
    from cns2fpga_golden.analysis import select_groups
    from cns2fpga_golden.model import FloatLIFNetwork
    neurons = pd.read_csv(paths["neuron_table"])
    synapses = pd.read_csv(paths["synapse_table"])
    offsets = pd.read_csv(paths["offset_table"])
    groups = select_groups(neurons, golden["observations"])
    for name in ["auditory_input", "aPN1", "vPN1", "pC1", "pIP10", "pMP2"]:
        if name not in groups or not len(groups[name]):
            raise ValueError(f"Required biological group is empty: {name}")
    groups["output_combined_exploratory"] = np.unique(np.concatenate([groups["pIP10"], groups["pMP2"]]))
    plan = make_ablation_plan(neurons, groups, config["ablation"])
    output = (output_dir or ROOT / "outputs" / config["name"]).resolve()
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(f"Refusing to overwrite locked run: {output}. Use --output-dir with a new directory.")
    output.mkdir(parents=True, exist_ok=True)
    source_files = sorted(set([Path(__file__), *list((ROOT / "src" / "cns2fpga_plausibility").glob("*.py")),
                              *list((golden_src / "cns2fpga_golden").glob("*.py"))]))
    tracked = {str(path): sha256(path) for path in [config_path, golden_path, *paths.values(), *source_files]}
    locked_at = datetime.now(timezone.utc).isoformat()
    lock = {"locked_at_utc": locked_at, "config": config, "golden_config": golden,
            "effective_model": model, "changes_from_golden": {"duration_ms": model["duration_ms"]},
            "input_and_source_sha256": tracked, "conditions": [item.description() for item in conditions],
            "ablation_plan": plan, "group_sizes": {name: len(indices) for name, indices in groups.items()},
            "primary_rule": "All declared reference-vs-comparator differences must be strictly positive beyond numerical tolerance",
            "acceptance_scope": "Spike proxies and one causal hypothesis; no validated behavioral mapping or calcium replication"}
    write_json(output / "protocol_lock.json", lock)
    lock_digest = sha256(output / "protocol_lock.json")
    write_json(output / "ablation_membership.json", plan)
    write_json(output / "stimulus_manifest.json", [item.description() for item in conditions])
    write_json(output / "output_readout_scope.json", {
        "status": "UNVALIDATED_BEHAVIOR_MAPPING",
        "separate_readouts": ["pIP10", "pMP2"],
        "exploratory_combined_readout": "output_combined_exploratory",
        "acceptance_threshold": None,
        "reason": "The cited perception study does not validate mean pIP10+pMP2 firing as the chaining index. Old warning is preserved as a scope limitation, not converted into a biological pass."})
    mapped = []
    for name, indices in groups.items():
        rows = neurons.iloc[indices][["neuron_index", "bodyId", "type", "instance", "synonyms", "nt_model_sign"]].copy()
        rows.insert(0, "group", name)
        mapped.append(rows)
    pd.concat(mapped, ignore_index=True).to_csv(output / "group_mapping.csv", index=False)
    print(f"Protocol locked before simulation: {lock_digest}", flush=True)

    net = FloatLIFNetwork(neurons, synapses, offsets, model)
    weight_digest = hashlib.sha256(net.weights.tobytes()).hexdigest()
    checks = []
    node_signs = neurons.nt_model_sign.to_numpy()
    sign_ok = np.array_equal(synapses.nt_model_sign.to_numpy(), node_signs[synapses.pre_index.to_numpy()])
    checks.append(check("presynaptic_sign_consistency", "engineering", sign_ok, str(sign_ok), "Every edge sign equals its presynaptic neuron sign", "IR invariant"))
    for transmitter, sign in [("acetylcholine", 1), ("gaba", -1), ("glutamate", -1)]:
        selected = neurons[neurons.consensus_nt.eq(transmitter)]
        ok = len(selected) > 0 and selected.nt_model_sign.eq(sign).all()
        checks.append(check(f"{transmitter}_policy", "engineering", bool(ok), f"n={len(selected)}, sign={sign}", "All annotated cells follow the declared sign convention", "Modelling assumption, Shiu 2024; not receptor verification"))
    # Explicitly audit connecting edges, not just labels.
    links = []
    for source, dest in [("auditory_input", "aPN1"), ("aPN1", "vPN1"), ("vPN1", "pC1"), ("pC1", "pIP10"), ("pC1", "pMP2")]:
        selected = synapses[synapses.pre_index.isin(groups[source]) & synapses.post_index.isin(groups[dest])]
        links.append(dict(source=source, destination=dest, edges=len(selected), aggregate_synapses=int(selected.synapse_count.sum()),
                          active_weight_edges=int(selected.nt_model_sign.ne(0).sum())))
    pd.DataFrame(links).to_csv(output / "pathway_connectivity.csv", index=False)
    checks.append(check("named_pathway_edges", "engineering", all(item["active_weight_edges"] > 0 for item in links[:3]),
                        str([item["active_weight_edges"] for item in links[:3]]), "Nonzero signed edges in JO->aPN1->vPN1->pC1", "Structural coverage; does not assert a unique pathway"))
    checks.append(check("equal_pulse_charge", "engineering", len({round(item.current.sum(), 10) for item in conditions}) == 1,
                        str([len(item.onsets) for item in conditions]), "40 pulses and equal current integral in every trial", "Stimulus invariant"))

    empty = np.empty(0, dtype=np.int32)
    silent_current = np.zeros_like(conditions[0].current)
    baseline_quiet = net.simulate(silent_current, groups["auditory_input"], groups, empty)
    checks.append(check("silence_baseline", "engineering", len(baseline_quiet.spike_times) == 0,
                        f"{len(baseline_quiet.spike_times)} spikes", "Quiescent model without stimulus", "Frozen bias/noise/reset=0"))
    all_quiet = {"intact": baseline_quiet}
    simulation_checks = []
    rows = []
    condition_files = output / "population_activity"
    condition_files.mkdir()

    def simulate(entry, condition, quiet, save=False):
        silenced = np.asarray(entry["indices"], dtype=np.int32)
        result = net.simulate(condition.current, groups["auditory_input"], groups, empty, silenced_indices=silenced)
        clamped_spikes = int(np.isin(result.spike_neurons, silenced).sum())
        simulation_checks.append(dict(condition_id=entry["condition_id"], ipi_ms=condition.ipi_ms,
            network_spikes=len(result.spike_times), max_abs_voltage=result.max_abs_voltage,
            finite=bool(np.isfinite(result.max_abs_voltage)), silenced_spikes=clamped_spikes))
        summaries = []
        for name, indices in groups.items():
            metrics = summarize_activity(result.group_activity[name], quiet.group_activity[name], len(indices), condition, config["protocol"]["peak_window_ms"])
            summaries.append(dict(condition_id=entry["condition_id"], kind=entry["kind"], target=entry["target"],
                replicate=entry["replicate"], ablated_neurons=len(silenced), ipi_ms=condition.ipi_ms,
                group=name, neurons=len(indices), pulse_count=len(condition.onsets), **metrics))
        if save:
            np.savez_compressed(condition_files / f"{entry['condition_id']}_ipi_{condition.ipi_ms:g}.npz",
                dt_ms=np.array([condition.dt_ms]), input_current=condition.current,
                spike_times=result.spike_times, spike_neurons=result.spike_neurons,
                **{f"{name}_counts": value for name, value in result.group_activity.items()})
        return summaries

    intact = dict(condition_id="intact", kind="intact", target="none", replicate=0, indices=[])
    for condition in conditions:
        rows.extend(simulate(intact, condition, baseline_quiet, save=True))
        print(f"Intact IPI {condition.ipi_ms:g} ms completed", flush=True)
    baseline = pd.DataFrame(rows)
    baseline.to_csv(output / "baseline_response.csv", index=False)
    checks.extend(tuning_checks(baseline, config))
    ablated_rows = []
    for number, entry in enumerate(plan):
        if entry["kind"] == "targeted":
            quiet = net.simulate(silent_current, groups["auditory_input"], groups, empty,
                                 silenced_indices=np.asarray(entry["indices"], dtype=np.int32))
            if len(quiet.spike_times):
                raise RuntimeError("Unexpected spontaneous firing in the declared quiescent ablated model")
            all_quiet[entry["condition_id"]] = quiet
            for condition in conditions:
                ablated_rows.extend(simulate(entry, condition, quiet, save=True))
            print(f"Targeted {entry['target']}: all 9 IPI trials completed", flush=True)
        else:
            # For zero reset/bias/noise, zero activity is invariant for every clamp.
            # This avoids repeating identical zero-drive trials for 48 random masks.
            condition = next(item for item in conditions if item.ipi_ms == config["ablation"]["reference_ipi_ms"])
            ablated_rows.extend(simulate(entry, condition, baseline_quiet))
            if (entry["replicate"] + 1) % 4 == 0:
                print(f"Matched controls for {entry['target']}: {entry['replicate']+1}/{config['ablation']['random_replicates']}", flush=True)
    ablated = pd.DataFrame(ablated_rows)
    ablated.to_csv(output / "ablation_response.csv", index=False)
    effects = ablation_effects(baseline, ablated, config)
    effects.to_csv(output / "ablation_effects.csv", index=False)
    controls = compare_random_controls(effects, config)
    controls.to_csv(output / "random_control_summary.csv", index=False)
    diagnostics = pd.DataFrame(simulation_checks)
    diagnostics.to_csv(output / "simulation_integrity.csv", index=False)
    checks.append(check("silenced_cells_never_spike", "engineering", diagnostics.silenced_spikes.eq(0).all(),
                        f"{int(diagnostics.silenced_spikes.sum())} clamped-cell spikes", "0 in every targeted/random trial", "Execution invariant"))
    checks.append(check("finite_voltages", "engineering", diagnostics.finite.all(),
                        f"maximum absolute voltage={diagnostics.max_abs_voltage.max():.6g}", "Finite throughout all simulations", "Numerical check, not biological voltage units"))
    checks.append(check("weights_unchanged_by_ablation", "engineering", hashlib.sha256(net.weights.tobytes()).hexdigest() == weight_digest,
                        weight_digest, "Same weights in every condition; no post-ablation renormalization", "Execution invariant"))
    tolerance = config["numerical_tolerance"]
    metric = config["protocol"]["ablation_metric"]
    input_rows = effects[effects.target.eq("auditory_input") & effects.kind.eq("targeted") & effects.group.isin(["vPN1", "pC1", "pIP10", "pMP2"]) & effects.metric.eq(metric)]
    checks.append(check("input_ablation_stops_downstream", "engineering", bool(input_rows.ablated.abs().le(tolerance).all()),
                        f"max residual={input_rows.ablated.abs().max():.6g}", "No downstream evoked spikes when all external input cells are clamped", "Computational input necessity, not a behavioral ablation claim"))
    for hypothesis in config["ablation"]["causal_hypotheses"]:
        effect = effects[effects.target.eq(hypothesis["target"]) & effects.kind.eq("targeted") & effects.group.eq(hypothesis["readout"]) & effects.ipi_ms.eq(config["ablation"]["reference_ipi_ms"]) & effects.metric.eq(metric)].iloc[0]
        passed = bool(effect.baseline - effect.ablated > tolerance) if effect.evaluable else None
        checks.append(check(f"{hypothesis['target']}_silencing_reduces_{hypothesis['readout']}", "causal_hypothesis", passed,
                            f"{effect.baseline:.6g} -> {effect.ablated:.6g}; drop={effect.drop_percent:.4g}%", "Strict reduction at 35 ms in evoked spikes / neuron / pulse", "Project causal hypothesis motivated by ascending pathway, not calibrated behavioral threshold"))
    # Window sensitivity is reported even though deterministic long-lived activity is not
    # automatically invalid biology. No biological duration threshold is invented.
    active_tail = baseline[baseline.group.isin(["vPN1", "pC1", "pIP10", "pMP2"])].post_tail_rate_hz.gt(tolerance).any()
    checks.append(dict(check_id="activity_at_response_window_end", category="scope", status="WARN" if active_tail else "PASS", gate=False,
                       observed="Residual spikes in the final 100 ms" if active_tail else "No residual spikes in the final 100 ms",
                       expected="Report window dependence of integrated counts", basis="A 500-ms tail is an engineering choice, not a fitted neural/calcium decay constant"))
    checks.append(dict(check_id="behavior_readout_mapping", category="scope", status="NOT_EVALUABLE", gate=False,
                       observed="pIP10/pMP2 separately measured; combination exploratory", expected="Independent evidence before equating rates with chaining", basis="No direct experimental mapping supplied"))
    checks.append(dict(check_id="experimental_numeric_correlation", category="scope", status="NOT_EVALUABLE", gate=False,
                       observed="No raw/digitized calcium reference or calibrated observation model", expected="Matched experimental quantity and sourced reference values", basis="Direction-only comparison"))
    check_table = pd.DataFrame(checks)
    check_table.to_csv(output / "validation_checks.csv", index=False)
    changed = [path for path, digest in tracked.items() if sha256(path) != digest]
    if changed or sha256(output / "protocol_lock.json") != lock_digest:
        raise RuntimeError(f"Inputs/source/protocol changed during the run: {changed}")
    metadata = dict(verdict=overall_verdict(check_table), locked_at_utc=locked_at,
        completed_at_utc=datetime.now(timezone.utc).isoformat(), protocol_lock_sha256=lock_digest,
        frozen_inputs_unchanged=True, runtime_seconds=time.perf_counter()-started,
        model_parameter_changes={"duration_ms": model["duration_ms"]},
        stimulus_trials=len(diagnostics), silence_trials=len(all_quiet),
        versions={"python": platform.python_version(), "numpy": np.__version__, "pandas": pd.__version__, "scipy": scipy.__version__, "matplotlib": matplotlib.__version__},
        gate_status_counts=check_table[check_table.gate].status.value_counts().to_dict(),
        all_status_counts=check_table.status.value_counts().to_dict())
    make_figures(output, baseline, effects, controls, config)
    write_report(output, baseline, effects, controls, check_table, config, metadata)
    write_json(output / "run_metadata.json", metadata)
    print(json.dumps(metadata, ensure_ascii=False, indent=2), flush=True)
    print(f"Report: {output / 'report.md'}", flush=True)
    return metadata


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "configs" / "courtship_song_equal_pulse_v1.json")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--require-pass", action="store_true", help="Exit 2 unless all core checks pass")
    args = parser.parse_args()
    metadata = run(args.config, args.output_dir)
    if args.require_pass and metadata["verdict"] != "CONDITIONAL_SUPPORT":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
