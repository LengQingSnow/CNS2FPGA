"""Recompute pC1 candidate-set readouts from locked spike-event archives."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
from cns2fpga_plausibility.protocol import build_equal_pulse_conditions, summarize_activity
from cns2fpga_plausibility.roi_robustness_v3d import (
    build_membership, counts_from_events, intervention_effects, stability_summary, tuning_checks,
)


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")


def markdown_table(frame):
    def clean(value):
        if pd.isna(value):
            return ""
        if isinstance(value, float):
            return f"{value:.4g}"
        return str(value).replace("|", " / ")
    return "\n".join([
        "| " + " | ".join(frame.columns) + " |",
        "| " + " | ".join(["---"] * len(frame.columns)) + " |",
        *["| " + " | ".join(clean(item) for item in row) + " |" for row in frame.itertuples(index=False, name=None)],
    ])


def plot_tuning(summary, output):
    intact = summary.loc[summary.condition_id.eq("intact")]
    fig, ax = plt.subplots(figsize=(9.2, 5.4))
    for candidate, rows in intact.groupby("candidate_id"):
        rows = rows.sort_values("ipi_ms")
        peak = rows.peak_rate_hz.max()
        ax.plot(rows.ipi_ms, rows.peak_rate_hz / peak if peak > 0 else rows.peak_rate_hz,
                marker="o", linewidth=1.6, markersize=4, label=candidate)
    ax.axvline(35, color="#777777", linestyle="--", linewidth=1)
    ax.set(xlabel="IPI (ms)", ylabel="Normalized 100-ms peak rate", title="pC1 candidate readout sensitivity")
    ax.grid(alpha=.25)
    ax.legend(fontsize=7, ncol=2)
    fig.tight_layout()
    fig.savefig(output, dpi=180)
    plt.close(fig)


def plot_effects(effects, output, reference_ipi=35.0):
    rows = effects.loc[(effects.ipi_ms.eq(reference_ipi)) & effects.metric.eq("response_spikes")].copy()
    table = rows.pivot(index="candidate_id", columns="condition_id", values="change_percent")
    fig, ax = plt.subplots(figsize=(10.5, 4.9))
    vmax = float(np.nanmax(np.abs(table.to_numpy())))
    image = ax.imshow(table.to_numpy(), cmap="coolwarm", vmin=-vmax, vmax=vmax, aspect="auto")
    ax.set_xticks(range(len(table.columns)), labels=table.columns, rotation=35, ha="right", fontsize=7)
    ax.set_yticks(range(len(table.index)), labels=table.index, fontsize=8)
    ax.set_title("35-ms intervention effect on response spikes (%)")
    fig.colorbar(image, ax=ax, label="Change from intact (%)")
    fig.tight_layout()
    fig.savefig(output, dpi=180)
    plt.close(fig)


def run(config_path, output_dir=None):
    config_path = config_path.resolve()
    cfg = json.loads(config_path.read_text(encoding="utf-8"))
    if cfg.get("schema_version") != 1:
        raise ValueError("Expected schema_version=1")
    ir_path = (config_path.parent / cfg["frozen_ir"]).resolve()
    v1_config_path = (config_path.parent / cfg["v1_config"]).resolve()
    runs = {name: (config_path.parent / relative).resolve() for name, relative in cfg["reference_runs"].items()}
    nb_run = (config_path.parent / cfg["neuronbridge_audit"]).resolve()
    nb_summary_path = nb_run / "pc1_search_candidate_summary.csv"
    v1_cfg = json.loads(v1_config_path.read_text(encoding="utf-8"))
    conditions = build_equal_pulse_conditions(v1_cfg["protocol"], dt_ms=1.0)
    condition_by_ipi = {item.ipi_ms: item for item in conditions}
    event_files = {}
    for condition_id, run_name in cfg["conditions"].items():
        for condition in conditions:
            path = runs[run_name] / "population_activity" / f"{condition_id}_ipi_{condition.ipi_ms:g}.npz"
            event_files[(condition_id, condition.ipi_ms)] = path
    source_files = [
        config_path, v1_config_path, ir_path, nb_summary_path, Path(__file__),
        ROOT / "src/cns2fpga_plausibility/roi_robustness_v3d.py",
        ROOT / "src/cns2fpga_plausibility/roi_mapping_v3.py",
        ROOT / "src/cns2fpga_plausibility/protocol.py",
        nb_run / "protocol_lock.json", nb_run / "run_metadata.json", nb_run / "artifact_sha256.json",
    ]
    for run in runs.values():
        source_files.extend([run / "protocol_lock.json", run / "run_metadata.json"])
        manifest = run / "artifact_sha256.json"
        if manifest.exists():
            source_files.append(manifest)
    source_files.extend(event_files.values())
    absent = [path for path in source_files if not path.exists()]
    if absent:
        raise FileNotFoundError(f"Required robustness source is missing: {absent}")
    tracked = {str(path): sha256(path) for path in source_files}
    output = (output_dir or ROOT / "outputs" / cfg["name"]).resolve()
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(f"Refusing to overwrite robustness audit: {output}")
    output.mkdir(parents=True, exist_ok=True)
    lock = {"locked_at_utc": datetime.now(timezone.utc).isoformat(), "config": cfg,
            "input_and_source_sha256": tracked}
    write_json(output / "protocol_lock.json", lock)
    lock_hash = sha256(output / "protocol_lock.json")

    neurons = pd.read_csv(ir_path)
    nb_summary = pd.read_csv(nb_summary_path)
    membership, groups = build_membership(neurons, nb_summary, int(cfg["neuronbridge_best_rank_cutoff"]))
    group_sizes = {name: len(indices) for name, indices in groups.items()}
    if not all(group_sizes.values()):
        raise RuntimeError(f"Empty candidate readout: {group_sizes}")
    response_rows = []
    integrity_rows = []
    for (condition_id, ipi), path in event_files.items():
        condition = condition_by_ipi[ipi]
        with np.load(path) as data:
            times = data["spike_times"]
            indices = data["spike_neurons"]
            duration = len(data["input_current"])
            if duration != len(condition.current) or not np.isclose(float(data["dt_ms"][0]), condition.dt_ms):
                raise RuntimeError(f"Event archive protocol mismatch: {path}")
            all_counts = counts_from_events(times, indices, groups["pC1_type_all"], duration)
            np.testing.assert_array_equal(all_counts, data["pC1_counts"])
            integrity_rows.append({"condition_id": condition_id, "ipi_ms": ipi, "event_file": str(path),
                                   "network_spikes": len(times), "pC1_recomputed_exact": True})
            for candidate_id, members in groups.items():
                counts = counts_from_events(times, indices, members, duration)
                metrics = summarize_activity(counts, np.zeros(duration, dtype=np.int64), len(members), condition, 100.0)
                response_rows.append({"condition_id": condition_id, "ipi_ms": ipi,
                                      "candidate_id": candidate_id, "neurons": len(members), **metrics})
    response = pd.DataFrame(response_rows)
    integrity = pd.DataFrame(integrity_rows)
    tuning = tuning_checks(response, float(cfg["reference_ipi_ms"]), tuple(map(float, cfg["comparison_ipi_ms"])))
    effects = intervention_effects(response, tolerance=float(cfg["numerical_tolerance"]))
    stability = stability_summary(tuning, effects, reference_ipi=float(cfg["reference_ipi_ms"]))

    membership.to_csv(output / "candidate_membership.csv", index=False)
    response.to_csv(output / "response_summary.csv", index=False)
    tuning.to_csv(output / "tuning_checks.csv", index=False)
    effects.to_csv(output / "intervention_effects.csv", index=False)
    stability.to_csv(output / "stability_summary.csv", index=False)
    integrity.to_csv(output / "archive_integrity.csv", index=False)
    plot_tuning(response, output / "candidate_tuning.png")
    plot_effects(effects, output / "intervention_effects_35ms.png", float(cfg["reference_ipi_ms"]))

    full_tuning = tuning.loc[tuning.candidate_id.eq("pC1_type_all")]
    all_peak_pass = int(full_tuning.loc[full_tuning.metric.eq("peak_rate_hz"), "reference_greater"].sum())
    perfect_tuning = int(stability.tuning_agreement_fraction.eq(1.0).sum())
    perfect_interventions = int(stability.intervention_35ms_direction_agreement_fraction.eq(1.0).sum())
    summary = {
        "verdict": "EXPLORATORY_ROI_READOUT_SENSITIVITY_COMPLETED",
        "biological_pass_claimed": False, "model_freeze_recommended": False,
        "candidate_readouts": group_sizes, "event_archives_reused": len(event_files),
        "new_simulations": 0, "all_pC1_peak_tuning_comparisons_passed": all_peak_pass,
        "all_pC1_peak_tuning_comparisons_total": 4,
        "readouts_with_identical_tuning_pattern_to_all_pC1": perfect_tuning,
        "readouts_with_identical_35ms_intervention_directions_to_all_pC1": perfect_interventions,
        "protocol_lock_sha256": lock_hash, "frozen_inputs_unchanged": True,
    }
    write_json(output / "run_metadata.json", summary)
    changed = [path for path, digest in tracked.items() if sha256(path) != digest]
    if changed or sha256(output / "protocol_lock.json") != lock_hash:
        raise RuntimeError(f"Source/protocol changed during robustness audit: {changed}")

    report_stability = stability.copy()
    report_stability["tuning_agreement_fraction"] = report_stability.tuning_agreement_fraction.round(3)
    report_stability["intervention_35ms_direction_agreement_fraction"] = report_stability.intervention_35ms_direction_agreement_fraction.round(3)
    report = [
        "# pC1 候选读出鲁棒性审计（v3d）", "",
        "**结论：已完成读出集合敏感性分析；结果用于判断工程结论对 pC1 定义的依赖程度，不构成实验 ROI 映射或新的生物学通过判定。**", "",
        f"本审计从 81 个锁定事件文件重算 6 个 pC1 候选集合的群体活动，共生成 {len(response)} 条条件×IPI×读出摘要；新增仿真为 0。所有 81 个文件中，全体 pC1 事件重算均与原存档 `pC1_counts` 逐时间步完全一致。", "",
        "## 候选集合", "", markdown_table(pd.DataFrame({"candidate_id": list(group_sizes), "neurons": list(group_sizes.values())})), "",
        "NeuronBridge 任意命中和最佳名次≤100子集来自 R71G01 MCFO 搜索，只用于敏感性分析；其他三个子集来自注释字段。任何集合都未被标记为 Zhou 2015 的 R71G01∩dsx 或钙成像 ROI。", "",
        "## 与全体 pC1 的一致性", "", markdown_table(report_stability), "",
        "调谐一致性比较固定的 35 ms 对 15、25、85、95 ms，并同时检查 100-ms 峰值和每脉冲累计放电。干预一致性比较 35 ms 下 8 类 vPN1/aPN1/mAL 干预的三种指标方向。分数 1.0 表示方向模式与全体 pC1 完全一致；它不表示与实验完全一致。", "",
        "## 产物", "",
        "- `candidate_membership.csv`：112 个冻结 pC1 对六个候选集合的成员关系。",
        "- `response_summary.csv`：全部重算读出。",
        "- `tuning_checks.csv` / `intervention_effects.csv`：IPI 和干预敏感性。",
        "- `candidate_tuning.png` / `intervention_effects_35ms.png`：可视化。",
        f"- lock: `{lock_hash}`。",
    ]
    (output / "report.md").write_text("\n".join(report), encoding="utf-8")
    manifest = {str(path.relative_to(output)): sha256(path) for path in output.rglob("*") if path.is_file()}
    write_json(output / "artifact_sha256.json", manifest)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "configs/courtship_song_roi_robustness_v3d.json")
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    run(args.config, args.output_dir)
