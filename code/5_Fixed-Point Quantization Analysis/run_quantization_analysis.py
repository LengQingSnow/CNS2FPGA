"""Run locked float-vs-fixed analysis and select safe/compact RTL formats."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import sys
import time

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from cns2fpga_fixed import FixedFormat, FixedLIFNetwork


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")


def markdown_table(frame: pd.DataFrame) -> str:
    """Render a compact Markdown table without the optional tabulate package."""
    values = frame.copy()
    for column in values.select_dtypes(include=["float"]).columns:
        values[column] = values[column].map(lambda value: f"{value:.6g}")
    headers = [str(column) for column in values.columns]
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
    for row in values.itertuples(index=False, name=None):
        lines.append("| " + " | ".join(str(value) for value in row) + " |")
    return "\n".join(lines)


def sign(value: float, tolerance: float = 1e-12) -> int:
    return 0 if abs(value) <= tolerance else (1 if value > 0 else -1)


def event_scores(fixed, reference, neuron_count: int) -> dict:
    fixed_keys = fixed.spike_times.astype(np.int64) * neuron_count + fixed.spike_neurons
    ref_keys = reference["spike_times"].astype(np.int64) * neuron_count + reference["spike_neurons"]
    common = len(np.intersect1d(fixed_keys, ref_keys, assume_unique=True))
    precision = common / len(fixed_keys) if len(fixed_keys) else float(len(ref_keys) == 0)
    recall = common / len(ref_keys) if len(ref_keys) else float(len(fixed_keys) == 0)
    f1 = 0.0 if precision + recall == 0 else 2 * precision * recall / (precision + recall)
    return {"fixed_spikes": len(fixed_keys), "float_spikes": len(ref_keys),
            "exact_event_matches": common, "event_precision": precision,
            "event_recall": recall, "event_f1": f1}


def make_plots(output: Path, formats: pd.DataFrame, agreement: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(9, 5))
    x = np.arange(len(formats))
    ax.bar(x, formats["max_key_response_error_percent"], color="#4472c4")
    ax.axhline(5.0, color="#c00000", linestyle="--", label="5% acceptance")
    ax.set_xticks(x, formats["format_name"], rotation=25, ha="right")
    ax.set_ylabel("Maximum key response error (%)")
    ax.set_title("Fixed-point population-response error")
    ax.legend()
    fig.tight_layout()
    fig.savefig(output / "quantization_error.png", dpi=180)
    plt.close(fig)

    matrix = agreement.pivot(index="format_name", columns="condition_id", values="all_metrics_direction_match")
    fig, ax = plt.subplots(figsize=(11, 4.5))
    image = ax.imshow(matrix.astype(int), vmin=0, vmax=1, cmap="RdYlGn", aspect="auto")
    ax.set_xticks(range(len(matrix.columns)), matrix.columns, rotation=35, ha="right")
    ax.set_yticks(range(len(matrix.index)), matrix.index)
    ax.set_title("35-ms intervention direction preserved (all three pC1 metrics)")
    fig.colorbar(image, ax=ax, ticks=[0, 1])
    fig.tight_layout()
    fig.savefig(output / "intervention_direction_preservation.png", dpi=180)
    plt.close(fig)


def run(config_path: Path, output_dir: Path | None = None) -> dict:
    started = time.perf_counter()
    config_path = config_path.resolve()
    config = json.loads(config_path.read_text(encoding="utf-8"))
    if config.get("schema_version") != 1:
        raise ValueError("schema_version=1 is required")
    resolve = lambda value: (config_path.parent / value).resolve()
    golden_path = resolve(config["golden_config"])
    v1_config_path = resolve(config["v1_config"])
    golden_src = resolve(config["golden_src"])
    plausibility_src = resolve(config["plausibility_src"])
    reference_runs = {name: resolve(value) for name, value in config["reference_runs"].items()}
    golden = json.loads(golden_path.read_text(encoding="utf-8"))
    v1_config = json.loads(v1_config_path.read_text(encoding="utf-8"))
    ir_paths = {name: (golden_path.parent / value).resolve() for name, value in golden["ir"].items()}
    model = dict(golden["model"])
    if model["noise_std"] != 0 or model["bias_current"] != 0 or model["reset_voltage"] != 0:
        raise ValueError("This deterministic contract requires zero noise/bias/reset")
    sys.path.insert(0, str(golden_src))
    sys.path.insert(0, str(plausibility_src))
    from cns2fpga_golden.analysis import select_groups
    from cns2fpga_plausibility.protocol import build_equal_pulse_conditions, summarize_activity

    neurons = pd.read_csv(ir_paths["neuron_table"])
    synapses = pd.read_csv(ir_paths["synapse_table"])
    offsets = pd.read_csv(ir_paths["offset_table"])
    groups = select_groups(neurons, golden["observations"])
    conditions = build_equal_pulse_conditions(v1_config["protocol"], model["dt_ms"])
    condition_by_ipi = {item.ipi_ms: item for item in conditions}
    model["duration_ms"] = len(conditions[0].current) * model["dt_ms"]

    v2_lock_path = reference_runs["v2"] / "protocol_lock.json"
    v2b_lock_path = reference_runs["v2b"] / "protocol_lock.json"
    v2_lock = json.loads(v2_lock_path.read_text(encoding="utf-8"))
    v2b_lock = json.loads(v2b_lock_path.read_text(encoding="utf-8"))
    interventions = {
        "silence_vPN1": {"run": "v1", "silenced": groups["vPN1"], "edges": []},
        "cut_vPN1_to_pC1": {"run": "v2", "silenced": [], "edges": v2_lock["edge_interventions"]["cut_vPN1_to_pC1"]},
        "cut_vPN1_to_other": {"run": "v2", "silenced": [], "edges": v2_lock["edge_interventions"]["cut_vPN1_to_other"]},
        "cut_vPN1_all_output": {"run": "v2", "silenced": [], "edges": v2_lock["edge_interventions"]["cut_vPN1_all_output"]},
        "silence_aPN1": {"run": "v2", "silenced": groups["aPN1"], "edges": []},
        "cut_vPN1_to_mAL_bridge": {"run": "v2b", "silenced": [], "edges": v2b_lock["interventions"]["cut_vPN1_to_mAL_bridge"]},
        "cut_mAL_bridge_to_pC1": {"run": "v2b", "silenced": [], "edges": v2b_lock["interventions"]["cut_mAL_bridge_to_pC1"]},
        "cut_both_bridge_segments": {"run": "v2b", "silenced": [], "edges": v2b_lock["interventions"]["cut_both_bridge_segments"]},
    }
    jobs = [("intact", "v1", item.ipi_ms, [], []) for item in conditions]
    jobs += [(name, spec["run"], float(config["reference_ipi_ms"]), spec["silenced"], spec["edges"])
             for name, spec in interventions.items()]
    archives = []
    for condition_id, run_name, ipi, _, _ in jobs:
        archive = reference_runs[run_name] / "population_activity" / f"{condition_id}_ipi_{ipi:g}.npz"
        if not archive.exists():
            raise FileNotFoundError(archive)
        archives.append(archive)

    output = (output_dir or ROOT / "outputs" / config["name"]).resolve()
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(f"Refusing to overwrite locked run: {output}")
    output.mkdir(parents=True, exist_ok=True)
    local_sources = [Path(__file__), *sorted((ROOT / "src" / "cns2fpga_fixed").glob("*.py"))]
    external_sources = [*sorted((golden_src / "cns2fpga_golden").glob("*.py")),
                        plausibility_src / "cns2fpga_plausibility" / "protocol.py"]
    reference_files = []
    for run in reference_runs.values():
        reference_files += [run / "protocol_lock.json", run / "run_metadata.json"]
    tracked_files = [config_path, golden_path, v1_config_path, *ir_paths.values(),
                     *local_sources, *external_sources, *reference_files, *archives]
    tracked = {str(path): sha256(path) for path in dict.fromkeys(tracked_files)}
    reference_manifest = {
        "status": "ENGINEERING_REFERENCE_ONLY",
        "biological_claim": "CONDITIONAL_SUPPORT; exact experimental pC1 ROI remains unresolved",
        "frozen_ir": {name: {"path": str(path), "sha256": sha256(path)} for name, path in ir_paths.items()},
        "float_model": {"config_path": str(golden_path), "sha256": sha256(golden_path), "effective_model": model},
        "step4_protocol_locks": {name: sha256(run / "protocol_lock.json") for name, run in reference_runs.items()},
        "reference_event_archives": len(archives),
    }
    write_json(output / "engineering_reference_manifest.json", reference_manifest)
    lock = {"locked_at_utc": datetime.now(timezone.utc).isoformat(), "config": config,
            "arithmetic_contract": {"signed": True, "rounding": "nearest_ties_away_from_zero",
                "overflow": "saturate", "update_order": ["propagate_previous_spikes", "saturate_accumulator",
                "requantize_synaptic_drive", "decay_voltage", "add_drive", "saturate_state", "threshold_and_reset"]},
            "input_and_source_sha256": tracked, "jobs": [{"condition_id": j[0], "reference_run": j[1], "ipi_ms": j[2]} for j in jobs]}
    write_json(output / "protocol_lock.json", lock)
    lock_hash = sha256(output / "protocol_lock.json")
    print(f"Protocol locked: {lock_hash}", flush=True)

    event_rows, response_rows, format_rows = [], [], []
    empty = np.empty(0, dtype=np.int64)
    key_groups = ["vPN1", "pC1", "pIP10", "pMP2"]
    for format_value in config["formats"]:
        fmt = FixedFormat.from_dict(format_value)
        network = FixedLIFNetwork(neurons, synapses, offsets, model, fmt)
        format_state_sat = format_acc_sat = 0
        for job_index, (condition_id, run_name, ipi, silenced, edges) in enumerate(jobs):
            archive_path = archives[job_index]
            with np.load(archive_path) as reference:
                current = reference["input_current"]
                result = network.simulate(current, groups["auditory_input"], groups,
                                          np.asarray(silenced, np.int64), np.asarray(edges, np.int64))
                event = {"format_name": fmt.name, "condition_id": condition_id, "ipi_ms": ipi,
                         **event_scores(result, reference, len(neurons)),
                         "state_saturation_events": result.state_saturation_events,
                         "accumulator_saturation_events": result.accumulator_saturation_events}
                event_rows.append(event)
                format_state_sat += result.state_saturation_events
                format_acc_sat += result.accumulator_saturation_events
                condition = condition_by_ipi[float(ipi)]
                for group in key_groups:
                    fixed_counts = result.group_activity[group]
                    float_counts = reference[f"{group}_counts"]
                    fixed_metrics = summarize_activity(fixed_counts, np.zeros_like(fixed_counts), len(groups[group]), condition, v1_config["protocol"]["peak_window_ms"])
                    float_metrics = summarize_activity(float_counts, np.zeros_like(float_counts), len(groups[group]), condition, v1_config["protocol"]["peak_window_ms"])
                    row = {"format_name": fmt.name, "condition_id": condition_id, "ipi_ms": ipi,
                           "group": group, "series_l1_per_float_spike": float(np.abs(fixed_counts-float_counts).sum()/max(float_counts.sum(), 1))}
                    for metric in ("response_spikes", "peak_rate_hz", "evoked_spikes_per_neuron_per_pulse"):
                        fv, rv = float(fixed_metrics[metric]), float(float_metrics[metric])
                        row[f"fixed_{metric}"] = fv
                        row[f"float_{metric}"] = rv
                        row[f"{metric}_error_percent"] = 100.0 * abs(fv-rv) / max(abs(rv), 1e-12)
                    response_rows.append(row)
        format_rows.append({**fmt.as_dict(), "weight_quantization_saturations": network.weight_quantization_saturations,
                            "decay_quantization_saturations": network.decay_quantization_saturations,
                            "state_saturation_events": format_state_sat,
                            "accumulator_saturation_events": format_acc_sat})
        print(f"{fmt.name}: {len(jobs)} trials completed", flush=True)

    events = pd.DataFrame(event_rows)
    responses = pd.DataFrame(response_rows)
    formats = pd.DataFrame(format_rows).rename(columns={"name": "format_name"})
    tuning_rows, intervention_rows = [], []
    for format_name, table in responses.groupby("format_name"):
        intact_pc1 = table[(table.condition_id == "intact") & (table.group == "pC1")].set_index("ipi_ms")
        for metric in ("peak_rate_hz", "evoked_spikes_per_neuron_per_pulse"):
            for comparison in config["comparison_ipi_ms"]:
                fixed_direction = bool(intact_pc1.loc[35, f"fixed_{metric}"] > intact_pc1.loc[comparison, f"fixed_{metric}"])
                float_direction = bool(intact_pc1.loc[35, f"float_{metric}"] > intact_pc1.loc[comparison, f"float_{metric}"])
                tuning_rows.append({"format_name": format_name, "metric": metric, "comparison_ipi_ms": comparison,
                                    "fixed_direction": fixed_direction, "float_direction": float_direction,
                                    "direction_match": fixed_direction == float_direction})
        baseline = table[(table.condition_id == "intact") & (table.ipi_ms == 35) & (table.group == "pC1")].iloc[0]
        for condition_id in interventions:
            row = table[(table.condition_id == condition_id) & (table.group == "pC1")].iloc[0]
            matches = []
            detail = {"format_name": format_name, "condition_id": condition_id}
            for metric in ("response_spikes", "peak_rate_hz", "evoked_spikes_per_neuron_per_pulse"):
                fixed_direction = sign(row[f"fixed_{metric}"] - baseline[f"fixed_{metric}"])
                float_direction = sign(row[f"float_{metric}"] - baseline[f"float_{metric}"])
                match = fixed_direction == float_direction
                detail[f"{metric}_fixed_direction"] = fixed_direction
                detail[f"{metric}_float_direction"] = float_direction
                detail[f"{metric}_direction_match"] = match
                matches.append(match)
            detail["all_metrics_direction_match"] = all(matches)
            intervention_rows.append(detail)
    tuning = pd.DataFrame(tuning_rows)
    intervention = pd.DataFrame(intervention_rows)
    key = responses[(responses.condition_id == "intact") & responses.group.isin(key_groups)]
    summaries = []
    acceptance = config["acceptance"]
    for row in formats.itertuples(index=False):
        name = row.format_name
        max_error = float(key[key.format_name == name].response_spikes_error_percent.max())
        tuning_matches = int(tuning[tuning.format_name == name].direction_match.sum())
        intervention_matches = int(sum(
            int(value) for column in ("response_spikes_direction_match", "peak_rate_hz_direction_match", "evoked_spikes_per_neuron_per_pulse_direction_match")
            for value in intervention.loc[intervention.format_name == name, column]))
        passed = (max_error <= acceptance["max_key_response_error_percent"]
                  and tuning_matches >= acceptance["required_tuning_direction_agreements"]
                  and intervention_matches >= acceptance["required_intervention_direction_agreements"]
                  and (acceptance["allow_state_saturation"] or row.state_saturation_events == 0)
                  and (acceptance["allow_accumulator_saturation"] or row.accumulator_saturation_events == 0)
                  and row.weight_quantization_saturations == 0 and row.decay_quantization_saturations == 0)
        summaries.append({"format_name": name, "max_key_response_error_percent": max_error,
                          "tuning_direction_agreements": tuning_matches, "tuning_direction_comparisons": len(tuning[tuning.format_name == name]),
                          "intervention_direction_agreements": intervention_matches, "intervention_direction_comparisons": 24,
                          "state_saturation_events": row.state_saturation_events,
                          "accumulator_saturation_events": row.accumulator_saturation_events,
                          "acceptance_pass": passed})
    summary = pd.DataFrame(summaries).merge(formats, on=["format_name", "state_saturation_events", "accumulator_saturation_events"])
    passed = summary[summary.acceptance_pass]
    safe = None if passed.empty else passed.iloc[0].format_name
    compact = None if passed.empty else passed.assign(cost=passed.state_bits+passed.weight_bits+passed.decay_bits+passed.accumulator_bits).sort_values(["cost", "max_key_response_error_percent"]).iloc[0].format_name
    recommendations = {"safe": safe, "compact": compact,
                       "status": "PASSING_FORMATS_FOUND" if safe else "NO_FORMAT_MET_ALL_ACCEPTANCE_GATES",
                       "acceptance": acceptance}

    events.to_csv(output / "event_comparison.csv", index=False)
    responses.to_csv(output / "population_comparison.csv", index=False)
    tuning.to_csv(output / "tuning_direction_checks.csv", index=False)
    intervention.to_csv(output / "intervention_direction_checks.csv", index=False)
    summary.to_csv(output / "format_summary.csv", index=False)
    write_json(output / "recommended_formats.json", recommendations)
    make_plots(output, summary, intervention)
    report_lines = ["# Courtship-song 定点化分析（v0）", "",
        "本轮使用整数运算重放 9 个完整 IPI 条件及 35 ms 下 8 种回路干预。浮点事件只作为锁定参考，没有修改第四步结果。", "",
        "## 结论", "",
        f"- 状态：`{recommendations['status']}`", f"- safe：`{safe}`", f"- compact：`{compact}`", "",
        "验收要求：关键群体完整条件最大响应放电误差 ≤5%，8/8 个 pC1 调谐方向一致，24/24 个干预方向一致，且无运行时饱和。", "",
        "## 格式汇总", "", markdown_table(summary), "",
        "精确逐事件 F1 用于诊断，不作为群体级 FPGA 保真度的唯一门槛。当前结果是工程量化结论，不提高第四步的生物学证据等级。", "",
        f"protocol lock: `{lock_hash}`"]
    (output / "report.md").write_text("\n".join(report_lines) + "\n", encoding="utf-8")
    metadata = {"verdict": recommendations["status"], "safe_format": safe, "compact_format": compact,
                "formats_tested": len(summary), "fixed_trials": len(summary)*len(jobs), "reference_archives": len(archives),
                "protocol_lock_sha256": lock_hash, "frozen_inputs_unchanged": all(sha256(Path(path)) == digest for path, digest in tracked.items()),
                "runtime_seconds": time.perf_counter()-started, "python": platform.python_version()}
    write_json(output / "run_metadata.json", metadata)
    artifacts = {path.name: sha256(path) for path in output.iterdir() if path.is_file() and path.name != "artifact_sha256.json"}
    write_json(output / "artifact_sha256.json", artifacts)
    if not metadata["frozen_inputs_unchanged"] or sha256(output / "protocol_lock.json") != lock_hash:
        raise RuntimeError("A locked source/input changed during execution")
    print(json.dumps(metadata, ensure_ascii=False, indent=2), flush=True)
    return metadata


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "configs" / "courtship_song_fixed_point_v0.json")
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    run(args.config, args.output_dir)


if __name__ == "__main__":
    main()
