"""Create a locked, evidence-tiered audit of experimental driver/ROI mappings."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
from cns2fpga_plausibility.roi_mapping_v3 import (
    audit_available_fields, exact_vpn1_mapping, make_candidate_summary, pC1_mask, side_counts,
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
        if isinstance(value, bool):
            return "True" if value else "False"
        return str(value).replace("|", " / ")
    return "\n".join(["| " + " | ".join(frame.columns) + " |",
                      "| " + " | ".join(["---"] * len(frame.columns)) + " |",
                      *["| " + " | ".join(clean(item) for item in row) + " |"
                        for row in frame.itertuples(index=False, name=None)]])


def run(config_path, output_dir=None):
    config_path = config_path.resolve()
    cfg = json.loads(config_path.read_text(encoding="utf-8"))
    if cfg.get("schema_version") != 3:
        raise ValueError("Expected schema_version=3")
    ir_path = (config_path.parent / cfg["ir_neurons"]).resolve()
    reference_runs = [(config_path.parent / item).resolve() for item in cfg["reference_runs"]]
    source_files = [config_path, ir_path, Path(__file__), ROOT / "src/cns2fpga_plausibility/roi_mapping_v3.py"]
    # v1 predates artifact_sha256.json. Its protocol lock plus run metadata are
    # still immutable evidence; later runs additionally provide artifact hashes.
    for folder in reference_runs:
        source_files.extend([folder / "protocol_lock.json", folder / "run_metadata.json"])
        artifact_manifest = folder / "artifact_sha256.json"
        if artifact_manifest.exists():
            source_files.append(artifact_manifest)
    absent = [path for path in source_files if not path.exists()]
    if absent:
        raise FileNotFoundError(f"Required mapping evidence is missing: {absent}")
    tracked = {str(path): sha256(path) for path in source_files}
    output = (output_dir or ROOT / "outputs" / cfg["name"]).resolve()
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(f"Refusing to overwrite mapping audit: {output}")
    output.mkdir(parents=True, exist_ok=True)
    lock = {"locked_at_utc": datetime.now(timezone.utc).isoformat(), "config": cfg,
            "input_and_source_sha256": tracked,
            "scope": cfg["scope"]}
    write_json(output / "protocol_lock.json", lock)
    lock_hash = sha256(output / "protocol_lock.json")
    neurons = pd.read_csv(ir_path)
    fields = audit_available_fields(neurons)
    vpn1 = exact_vpn1_mapping(neurons)
    pc1 = neurons.loc[pC1_mask(neurons)].copy()
    candidate = make_candidate_summary(neurons, cfg["annotation_candidates"], reported_per_hemi=23)
    candidate.to_csv(output / "pC1_candidate_sets.csv", index=False)
    pc1.to_csv(output / "all_pC1_annotation_rows.csv", index=False)
    vpn1.to_csv(output / "vPN1_exact_annotation_rows.csv", index=False)
    experiments = pd.DataFrame(cfg["experiments"])
    experiments["local_mapping_result"] = [
        f"{len(vpn1)} cells; soma sides={side_counts(vpn1)}" if item == "zhou2015_vPN1_split_gal4"
        else "UNRESOLVED: no driver/ROI expression field; see candidate sets and required evidence"
        for item in experiments.id
    ]
    experiments.to_csv(output / "experimental_mapping_registry.csv", index=False)
    requirements = pd.DataFrame({"requirement": cfg["external_evidence_requirements"],
                                 "status": "REQUIRED_BEFORE_EXACT_MAPPING"})
    requirements.to_csv(output / "external_evidence_required.csv", index=False)
    unresolved = experiments[experiments.mapping_status.ne("EXACT_ANNOTATION_NAME_MATCH")]
    summary = dict(verdict="INCOMPLETE_EXACT_PC1_DRIVER_ROI_MAPPING", model_freeze_recommended=False,
                   protocol_lock_sha256=lock_hash, frozen_inputs_unchanged=True,
                   experimental_definitions=len(experiments), exact_local_mappings=int(len(experiments)-len(unresolved)),
                   unresolved_local_mappings=int(len(unresolved)), vPN1_exact_cells=len(vpn1),
                   pC1_type_cells=len(pc1), pC1_type_soma_sides=side_counts(pc1),
                   pC1_candidate_sets=len(candidate), driver_or_roi_expression_fields=fields["driver_or_roi_expression_fields"])
    write_json(output / "run_metadata.json", summary)
    # Validate the original inputs after writing all generated output.
    changed = [path for path, digest in tracked.items() if sha256(path) != digest]
    if changed or sha256(output / "protocol_lock.json") != lock_hash:
        raise RuntimeError(f"Source/protocol changed during mapping audit: {changed}")
    report = [
        "# 实验驱动系 / ROI 与 MaleCNS 映射审计（v3）", "",
        "**结果：vPN1 可作精确的命名注释映射；pC1 的 R71G01∩dsx 和钙成像 ROI 不能由当前本地 IR 精确映射。**", "",
        "这是有效的阻断结论：当前 pC1 全体或任一 annotation-derived 子集只能用于敏感性分析，不能称为 Zhou 2015 实验驱动的同一细胞集合。该审计不修改模型、刺激或既有 verdict。", "",
        "## 文献与局部数据能支持什么", "",
        markdown_table(experiments[["id", "readout", "driver", "mapping_status", "local_mapping_result", "source"]]), "",
        "R71G01-LexA∩dsxGAL4 的表达在文献中被用作 pC1 交集；独立报告称雄性约每半球 23 个细胞。该计数是合理性约束，不能反推哪 46 个 bodyId。", "",
        "本地 `neuron_table.csv` 有 type、历史 synonym、fru/dsx 注释和 soma side，但没有 R71G01、GAL4/LexA 表达，也没有 neurite/LPC ROI membership。`fruDsx` 来自跨数据集 fruitless/doublesex annotation，不是 R71G01 驱动表达测量。[MaleCNS annotation provenance](https://github.com/flyconnectome/flywire_annotations/blob/main/README.md)", "",
        "## 仅供敏感性分析的候选集（不是驱动映射）", "",
        markdown_table(candidate.drop(columns=["body_ids"])), "",
        "`matches_reported_male_count_per_side=False` 说明不能仅靠数目把一个候选集伪装为 R71G01∩dsx ROI；即使数目碰巧相同，也仍需表达或形态证据。所有 candidate 的 bodyId 都在 `pC1_candidate_sets.csv` 中导出，供外部证据到位后逐项比对。", "",
        "## 下一步所需证据", "",
        *[f"- {item}" for item in cfg["external_evidence_requirements"]], "",
        "在这些证据到位前，后续模型可报告：`pC1_type_all` 是类型级工程读出，`pC1_fruDsx_*` / `pC1_pMP_alias` 是 annotation-compatible 敏感性读出；不能报告为“实验 pC1 ROI”。", "",
        "## 产物", "",
        "- `experimental_mapping_registry.csv`：每个实验的 driver、读出、映射状态。",
        "- `pC1_candidate_sets.csv`：候选集合、左右侧计数和全量 bodyId。",
        "- `all_pC1_annotation_rows.csv` / `vPN1_exact_annotation_rows.csv`：逐细胞证据。",
        "- `external_evidence_required.csv`：完成精确映射的输入契约。",
        f"- lock: `{lock_hash}`。", "",
        "文献：[Zhou et al., 2015](https://pmc.ncbi.nlm.nih.gov/articles/PMC4575990/)；[R71G01-LexA construct record](https://flybase.org/reports/FBtp0079698.html)；[R71G01∩dsx male-count report](https://pmc.ncbi.nlm.nih.gov/articles/PMC10882504/)。"
    ]
    (output / "report.md").write_text("\n".join(report), encoding="utf-8")
    manifest = {str(path.relative_to(output)): sha256(path) for path in output.rglob("*") if path.is_file()}
    write_json(output / "artifact_sha256.json", manifest)
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "configs/courtship_song_roi_mapping_v3.json")
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    run(args.config, args.output_dir)
