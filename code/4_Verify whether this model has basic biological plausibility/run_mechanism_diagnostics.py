"""v2 mechanism diagnosis; reuse locked v1 events and run a 2x2 edge intervention."""
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
from cns2fpga_plausibility.diagnostics_v2 import (
    anatomical_groups, cut_edges, edge_partitions, observation_metrics,
    population_counts, shortest_paths, reconstruct_path, readout_directions,
)
from cns2fpga_plausibility.protocol import build_equal_pulse_conditions, summarize_activity, drop_percent
from cns2fpga_plausibility.reporting_v2 import make_figures, write_report


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")


def verify(tracked):
    changed = [path for path, digest in tracked.items() if sha256(path) != digest]
    if changed:
        raise RuntimeError(f"Frozen input/source hash mismatch: {changed}")


def run(config_path, output_dir=None):
    started = time.perf_counter()
    config_path = config_path.resolve()
    cfg = json.loads(config_path.read_text(encoding="utf-8"))
    if cfg["schema_version"] != 2:
        raise ValueError("Expected schema_version=2")
    baseline = (config_path.parent / cfg["baseline_run"]).resolve()
    v1_lock = json.loads((baseline / "protocol_lock.json").read_text(encoding="utf-8"))
    verify(v1_lock["input_and_source_sha256"])
    v1_metadata = json.loads((baseline / "run_metadata.json").read_text(encoding="utf-8"))
    if sha256(baseline / "protocol_lock.json") != v1_metadata["protocol_lock_sha256"]:
        raise RuntimeError("v1 protocol lock no longer matches completed-run metadata")
    golden_path = next(Path(p) for p in v1_lock["input_and_source_sha256"]
                       if Path(p).name == "courtship_song_lif_v0.json")
    golden = v1_lock["golden_config"]
    golden_src = golden_path.parent.parent / "src"
    sys.path.insert(0, str(golden_src))
    from cns2fpga_golden.model import FloatLIFNetwork
    from cns2fpga_golden.analysis import select_groups

    paths = {key: (golden_path.parent / value).resolve() for key, value in golden["ir"].items()}
    neurons = pd.read_csv(paths["neuron_table"])
    synapses = pd.read_csv(paths["synapse_table"])
    offsets = pd.read_csv(paths["offset_table"])
    groups = select_groups(neurons, golden["observations"])
    all_groups = anatomical_groups(neurons, synapses, groups)
    conditions = build_equal_pulse_conditions(v1_lock["config"]["protocol"], golden["model"]["dt_ms"])
    model = v1_lock["effective_model"].copy()
    if model["weight_mode"] != "raw_linear" or any(model[k] != 0 for k in ["bias_current", "noise_std", "reset_voltage"]):
        raise ValueError("v2 requires the frozen raw-linear, quiescent model")
    masks = edge_partitions(synapses, groups["vPN1"], groups["pC1"])
    if set(cfg["perturbations"]) != {*masks, "silence_aPN1"}:
        raise ValueError("v2 requires the complete factorial design plus aPN1 silencing")
    if not (np.all(~(masks["cut_vPN1_to_pC1"] & masks["cut_vPN1_to_other"])) and
            np.array_equal(masks["cut_vPN1_to_pC1"] | masks["cut_vPN1_to_other"], masks["cut_vPN1_all_output"])):
        raise AssertionError("Invalid disjoint edge partition")
    raw_nt_path = (config_path.parent / cfg["nt_source"]).resolve()
    raw_nt = pd.read_feather(raw_nt_path)
    nt_audit = neurons.iloc[groups["vPN1"]][["neuron_index", "bodyId", "type", "synonyms", "consensus_nt", "nt_model_sign"]].merge(
        raw_nt, left_on="bodyId", right_on="body", how="left", validate="one_to_one", suffixes=("_ir", "_raw"))
    if not nt_audit.consensus_nt_ir.eq(nt_audit.consensus_nt_raw).all():
        raise AssertionError("vPN1 raw neurotransmitter annotations do not match the IR")

    reused = {(kind, condition.ipi_ms): baseline / "population_activity" / f"{kind}_ipi_{condition.ipi_ms:g}.npz"
              for kind in ["intact", "silence_vPN1"] for condition in conditions}
    tracked = dict(v1_lock["input_and_source_sha256"])
    extra = [config_path, Path(__file__), raw_nt_path, baseline / "protocol_lock.json",
             baseline / "run_metadata.json", baseline / "baseline_response.csv", *reused.values(),
             ROOT / "src/cns2fpga_plausibility/diagnostics_v2.py",
             ROOT / "src/cns2fpga_plausibility/reporting_v2.py"]
    tracked.update({str(path.resolve()): sha256(path) for path in extra})
    output = (output_dir or ROOT / "outputs" / cfg["name"]).resolve()
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(f"Refusing to overwrite results: {output}")
    output.mkdir(parents=True, exist_ok=True)
    activity_dir = output / "population_activity"
    activity_dir.mkdir()
    lock = dict(locked_at_utc=datetime.now(timezone.utc).isoformat(), config=cfg,
                v1_protocol_sha256=sha256(baseline / "protocol_lock.json"), effective_model=model,
                input_and_source_sha256=tracked,
                groups={key: value.tolist() for key, value in all_groups.items()},
                edge_interventions={key: np.flatnonzero(mask).tolist() for key, mask in masks.items()},
                scope="Exploratory after viewing v1, not a preregistered independent validation or new biological PASS")
    write_json(output / "protocol_lock.json", lock)
    lock_hash = sha256(output / "protocol_lock.json")
    print(f"v2 protocol locked before intervention simulations: {lock_hash}", flush=True)
    nt_audit.to_csv(output / "vPN1_raw_nt_audit.csv", index=False)
    pd.concat([neurons.iloc[idx][["neuron_index", "bodyId", "type", "fruDsx"]].assign(group=name)
               for name, idx in all_groups.items()]).to_csv(output / "group_mapping.csv", index=False)
    net = FloatLIFNetwork(neurons, synapses, offsets, model)
    original_weights = net.weights.copy()
    interventions = {key: cut_edges(net, mask) for key, mask in masks.items()}
    edge_audit = []
    for name, mask in masks.items():
        selected = synapses.loc[mask]
        edge_audit.append(dict(condition_id=name, removed_edges=int(mask.sum()),
                               removed_synapses=int(selected.synapse_count.sum()),
                               recipients=int(selected.post_index.nunique()),
                               negative_edges=int(selected.nt_model_sign.lt(0).sum()),
                               unchanged_other_weights=bool(np.array_equal(interventions[name].weights[~mask], original_weights[~mask])),
                               all_selected_weights_zero=bool(np.all(interventions[name].weights[mask] == 0))))
    edge_audit = pd.DataFrame(edge_audit)
    edge_audit.to_csv(output / "edge_interventions.csv", index=False)

    # Per-cell structural evidence and explicit paths in the already extracted IR.
    pc = neurons.iloc[groups["pC1"]][["neuron_index", "bodyId", "type", "fruDsx"]].copy()
    incoming = synapses[synapses.post_index.isin(groups["pC1"])]
    direct = synapses.loc[masks["cut_vPN1_to_pC1"]]
    total = incoming.groupby("post_index").synapse_count.sum()
    vpn_total = direct.groupby("post_index").synapse_count.sum()
    pc["incoming_synapses"] = pc.neuron_index.map(total).fillna(0).astype(int)
    pc["vPN1_synapses"] = pc.neuron_index.map(vpn_total).fillna(0).astype(int)
    pc["vPN1_incoming_fraction"] = pc.vPN1_synapses / pc.incoming_synapses.replace(0, np.nan)
    for positive_only, label in [(False, "nonzero_signed"), (True, "positive_only")]:
        distances, parents = shortest_paths(synapses, len(neurons), groups["auditory_input"], groups["vPN1"], positive_only)
        pc[f"bypass_{label}_hops"] = distances[pc.neuron_index]
        pc[f"bypass_{label}_body_ids"] = [json.dumps(neurons.iloc[reconstruct_path(int(i), distances, parents)].bodyId.astype(int).tolist())
                                          for i in pc.neuron_index]
    pc.to_csv(output / "pC1_connectivity.csv", index=False)
    pc.groupby("type", sort=True).agg(neurons=("neuron_index", "size"),
        direct_recipients=("vPN1_synapses", lambda v: int(v.gt(0).sum())),
        vPN1_synapses=("vPN1_synapses", "sum"), incoming_synapses=("incoming_synapses", "sum")
        ).reset_index().to_csv(output / "pC1_subtype_connectivity.csv", index=False)

    empty = np.empty(0, dtype=np.int32)
    quiet = np.zeros_like(conditions[0].current)
    integrity = []
    for name, network in {"intact": net, **interventions, "silence_aPN1": net}.items():
        silenced = groups["aPN1"] if name == "silence_aPN1" else empty
        result = network.simulate(quiet, groups["auditory_input"], groups, empty, silenced_indices=silenced)
        if len(result.spike_times):
            raise AssertionError(f"Unexpected spontaneous activity: {name}")
    reference = next(c for c in conditions if c.ipi_ms == cfg["reference_ipi_ms"])
    replay = net.simulate(reference.current, groups["auditory_input"], groups, empty)
    with np.load(reused[("intact", reference.ipi_ms)]) as saved:
        for key in ["spike_times", "spike_neurons"]:
            np.testing.assert_array_equal(getattr(replay, key), saved[key])
    print("Intact reference replay exactly matches v1 spike events", flush=True)

    files = dict(reused)
    all_output_equivalence = []
    for name in cfg["perturbations"]:
        network = interventions.get(name, net)
        silenced = groups["aPN1"] if name == "silence_aPN1" else empty
        for condition in conditions:
            result = network.simulate(condition.current, groups["auditory_input"], groups, empty, silenced_indices=silenced)
            path = activity_dir / f"{name}_ipi_{condition.ipi_ms:g}.npz"
            np.savez_compressed(path, dt_ms=np.array([condition.dt_ms]), input_current=condition.current,
                                spike_times=result.spike_times, spike_neurons=result.spike_neurons,
                                **{f"{key}_counts": value for key, value in result.group_activity.items()})
            files[(name, condition.ipi_ms)] = path
            clamped = int(np.isin(result.spike_neurons, silenced).sum())
            integrity.append(dict(condition_id=name, ipi_ms=condition.ipi_ms, network_spikes=len(result.spike_times),
                                  finite=bool(np.isfinite(result.max_abs_voltage)), max_abs_voltage=result.max_abs_voltage,
                                  silenced_spikes=clamped))
            if clamped:
                raise AssertionError("Silenced neurons spiked")
            if name == "cut_vPN1_all_output":
                selected = ~np.isin(result.spike_neurons, groups["vPN1"])
                with np.load(reused[("silence_vPN1", condition.ipi_ms)]) as saved:
                    np.testing.assert_array_equal(result.spike_times[selected], saved["spike_times"])
                    np.testing.assert_array_equal(result.spike_neurons[selected], saved["spike_neurons"])
                all_output_equivalence.append(condition.ipi_ms)
        print(f"Completed {name}: {len(conditions)} IPI trials", flush=True)
    pd.DataFrame(integrity).to_csv(output / "simulation_integrity.csv", index=False)
    np.testing.assert_array_equal(net.weights, original_weights)

    summaries, cells, observations, drives = [], [], [], []
    for (name, ipi), path in files.items():
        condition = next(c for c in conditions if c.ipi_ms == ipi)
        with np.load(path) as data:
            times, indices = data["spike_times"], data["spike_neurons"]
            np.testing.assert_array_equal(data["input_current"], condition.current)
            np.testing.assert_array_equal(data["dt_ms"], [condition.dt_ms])
            active = (times >= condition.start) & (times < condition.response_end)
            counts_per_cell = np.bincount(indices[active], minlength=len(neurons))
            row = pc[["neuron_index", "bodyId", "type", "fruDsx", "vPN1_synapses"]].copy()
            row["condition_id"], row["ipi_ms"] = name, ipi
            row["response_spikes"] = counts_per_cell[row.neuron_index]
            cells.append(row)
            for group, members in all_groups.items():
                if not len(members):
                    continue
                counts = population_counts(times, indices, members, len(condition.current))
                if f"{group}_counts" in data:
                    np.testing.assert_array_equal(counts, data[f"{group}_counts"])
                metrics = summarize_activity(counts, quiet, len(members), condition, 100.)
                summaries.append(dict(condition_id=name, ipi_ms=ipi, group=group, neurons=len(members), **metrics))
                if name == "intact":
                    for metric in observation_metrics(counts, len(members), condition, cfg["rolling_windows_ms"], cfg["observation_kernels"]):
                        observations.append(dict(group=group, neurons=len(members), ipi_ms=ipi, **metric))
            if name == "intact":
                # One-step delayed offered drive, before active/refractory gating.
                arrivals = (times + 1 >= condition.start) & (times + 1 < condition.response_end)
                pre_spikes = np.bincount(indices[arrivals], minlength=len(neurons))
                for label, selected in [
                    ("vPN1", incoming.pre_index.isin(groups["vPN1"])),
                    ("other_excitatory", ~incoming.pre_index.isin(groups["vPN1"]) & incoming.nt_model_sign.gt(0)),
                    ("other_inhibitory", ~incoming.pre_index.isin(groups["vPN1"]) & incoming.nt_model_sign.lt(0)),
                    ("zero_sign", incoming.nt_model_sign.eq(0)),
                ]:
                    edges = incoming.loc[selected]
                    drive = pre_spikes[edges.pre_index] * edges.synapse_count.to_numpy() * edges.nt_model_sign.to_numpy() * model["recurrent_gain"]
                    drives.append(dict(ipi_ms=ipi, source=label, synapses=int(edges.synapse_count.sum()),
                                       offered_signed_drive=float(drive.sum()), offered_abs_drive=float(np.abs(drive).sum())))
    summary = pd.DataFrame(summaries)
    summary.to_csv(output / "response_summary.csv", index=False)
    pd.concat(cells, ignore_index=True).to_csv(output / "pC1_single_cell_response.csv", index=False)
    observation = pd.DataFrame(observations)
    observation.to_csv(output / "observation_sensitivity.csv", index=False)
    directions = readout_directions(observation, cfg["numerical_tolerance"])
    directions.to_csv(output / "observation_directions.csv", index=False)
    pd.DataFrame(drives).to_csv(output / "pC1_offered_drive.csv", index=False)
    # Re-derived baseline summaries must agree with the v1 saved metric table.
    old = pd.read_csv(baseline / "baseline_response.csv")
    joined = summary[summary.condition_id.eq("intact")].merge(old, on=["group", "ipi_ms"], suffixes=("_new", "_old"))
    if len(joined) != len(groups) * len(conditions):
        raise AssertionError("Missing baseline metric rows")
    for metric in ["peak_rate_hz", "evoked_spikes_per_neuron_per_pulse", "response_spikes"]:
        np.testing.assert_allclose(joined[f"{metric}_new"], joined[f"{metric}_old"], rtol=1e-12, atol=1e-12)

    effect_rows, factorial = [], []
    for (group, ipi), frame in summary.groupby(["group", "ipi_ms"]):
        frame = frame.set_index("condition_id")
        for metric in ["peak_rate_hz", "evoked_spikes_per_neuron_per_pulse"]:
            intact = float(frame.loc["intact", metric])
            for name in ["silence_vPN1", *cfg["perturbations"]]:
                changed = float(frame.loc[name, metric])
                effect_rows.append(dict(group=group, ipi_ms=ipi, metric=metric, condition_id=name,
                                        baseline=intact, perturbed=changed, drop_percent=drop_percent(intact, changed)))
            direct = float(frame.loc["cut_vPN1_to_pC1", metric])
            other = float(frame.loc["cut_vPN1_to_other", metric])
            both = float(frame.loc["cut_vPN1_all_output", metric])
            factorial.append(dict(group=group, ipi_ms=ipi, metric=metric, intact=intact,
                                  direct_cut=direct, other_cut=other, both_cut=both,
                                  interaction=both-direct-other+intact))
    effects = pd.DataFrame(effect_rows)
    effects.to_csv(output / "intervention_effects.csv", index=False)
    pd.DataFrame(factorial).to_csv(output / "factorial_interactions.csv", index=False)
    make_figures(output, summary, observation, effects, cfg)
    verify(tracked)
    if sha256(output / "protocol_lock.json") != lock_hash:
        raise RuntimeError("v2 lock changed during execution")
    metadata = dict(verdict="DIAGNOSTIC_ONLY_NOT_BIOLOGICAL_PASS", model_freeze_recommended=False,
        protocol_lock_sha256=lock_hash, baseline_lock_sha256=lock["v1_protocol_sha256"],
        locked_at_utc=lock["locked_at_utc"], completed_at_utc=datetime.now(timezone.utc).isoformat(),
        frozen_inputs_unchanged=True, model_parameter_changes={}, reference_replay_exact=True,
        all_output_cut_matches_vPN1_clamp_outside_vPN1=all_output_equivalence,
        reused_stimulus_trials=len(reused), new_stimulus_trials=len(integrity), replay_trials=1, quiet_trials=5,
        pC1_neurons=len(pc), pC1_type_labels=int(pc.type.nunique()),
        vPN1_nt_consensus_counts=nt_audit.consensus_nt_raw.value_counts().to_dict(),
        vPN1_nonmissing_ground_truth=int(nt_audit.ground_truth.notna().sum()),
        vPN1_direct_pC1_edges=int(masks["cut_vPN1_to_pC1"].sum()),
        vPN1_direct_pC1_synapses=int(direct_synapses := synapses.loc[masks["cut_vPN1_to_pC1"], "synapse_count"].sum()),
        vPN1_direct_pC1_recipients=int(pc.vPN1_synapses.gt(0).sum()),
        vPN1_fraction_all_pC1_incoming_synapses=float(direct_synapses / pc.incoming_synapses.sum()),
        pC1_reachable_without_vPN1_positive_only=int(pc.bypass_positive_only_hops.ge(0).sum()),
        runtime_seconds=time.perf_counter()-started,
        versions=dict(python=platform.python_version(), numpy=np.__version__, pandas=pd.__version__, scipy=scipy.__version__, matplotlib=matplotlib.__version__))
    write_report(output, summary, observation, directions, effects, pc, nt_audit, cfg, metadata)
    write_json(output / "run_metadata.json", metadata)
    manifest = {str(path.relative_to(output)): sha256(path) for path in sorted(output.rglob("*")) if path.is_file()}
    write_json(output / "artifact_sha256.json", manifest)
    print(json.dumps(metadata, indent=2), flush=True)
    return metadata


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "configs/courtship_song_mechanism_v2.json")
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    run(args.config, args.output_dir)
