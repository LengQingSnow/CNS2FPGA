"""Create a non-overwriting audit of user-exported R71G01 NeuronBridge searches."""
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
from cns2fpga_plausibility.neuronbridge_screen import (
    explicit_male_pc1_hits, read_search_tables, sha256, summarise_hits,
)


def write_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")


def markdown_table(frame):
    def clean(value):
        if pd.isna(value):
            return ""
        return str(value).replace("|", " / ").replace("\n", " ")
    return "\n".join([
        "| " + " | ".join(frame.columns) + " |",
        "| " + " | ".join(["---"] * len(frame.columns)) + " |",
        *["| " + " | ".join(clean(item) for item in row) + " |"
          for row in frame.itertuples(index=False, name=None)],
    ])


def run(config_path, output_dir=None):
    config_path = config_path.resolve()
    cfg = json.loads(config_path.read_text(encoding="utf-8"))
    if cfg.get("schema_version") != 1:
        raise ValueError("Expected schema_version=1")
    search_dir = (config_path.parent / cfg["search_dir"]).resolve()
    annotation_path = (config_path.parent / cfg["annotation_table"]).resolve()
    frozen_ir_path = (config_path.parent / cfg["frozen_ir"]).resolve()
    search_rows, search_files = read_search_tables(search_dir, cfg["expected_files"])
    source_files = [config_path, annotation_path, frozen_ir_path, Path(__file__), ROOT / "src/cns2fpga_plausibility/neuronbridge_screen.py", *search_files]
    absent = [path for path in source_files if not path.exists()]
    if absent:
        raise FileNotFoundError(f"Required source is missing: {absent}")
    tracked = {str(path): sha256(path) for path in source_files}
    output = (output_dir or ROOT / "outputs" / cfg["name"]).resolve()
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(f"Refusing to overwrite NeuronBridge screen: {output}")
    output.mkdir(parents=True, exist_ok=True)
    lock = {
        "locked_at_utc": datetime.now(timezone.utc).isoformat(), "config": cfg,
        "input_and_source_sha256": tracked,
    }
    write_json(output / "protocol_lock.json", lock)
    lock_hash = sha256(output / "protocol_lock.json")
    annotations = pd.read_feather(annotation_path)
    frozen = pd.read_csv(frozen_ir_path)
    hits = explicit_male_pc1_hits(search_rows)
    observed, candidates = summarise_hits(hits, annotations, frozen)
    if observed.empty:
        raise RuntimeError("No explicit MaleCNS pC1-labelled result exists in the supplied exports")
    candidate_ids = candidates.bodyId.tolist()
    candidate_prefixes = {f"male-cns:v0.9:{body_id}" for body_id in candidate_ids}
    all_appearances = search_rows.loc[search_rows["Neuron ID"].isin(candidate_prefixes)].copy()
    all_appearances["bodyId"] = all_appearances["Neuron ID"].str.rsplit(":", n=1).str[-1].astype(int)
    all_appearances = all_appearances.sort_values(["bodyId", "Number", "source_file"])
    appearance_summary = (
        all_appearances.groupby("bodyId", as_index=False)
        .agg(
            all_result_appearances=("bodyId", "size"),
            all_source_files=("source_file", lambda values: ";".join(sorted(values))),
            best_any_rank=("Number", "min"),
            best_any_score=("Score", "max"),
        )
    )
    candidates = candidates.merge(appearance_summary, on="bodyId", how="left", validate="one_to_one")
    observed.to_csv(output / "explicit_male_pc1_hits.csv", index=False)
    all_appearances.to_csv(output / "all_candidate_appearances.csv", index=False)
    candidates.to_csv(output / "candidate_summary.csv", index=False)
    annotations.loc[annotations.bodyId.isin(candidate_ids)].to_csv(output / "full_malecns_annotation_context.csv", index=False)
    frozen.loc[frozen.bodyId.isin(candidate_ids)].to_csv(output / "frozen_ir_rows_for_candidates.csv", index=False)
    in_ir = int(candidates.in_frozen_ir.sum())
    verdict = "MORPHOLOGY_CANDIDATE_OUTSIDE_FROZEN_SUBCIRCUIT" if in_ir == 0 else "MORPHOLOGY_CANDIDATE_PRESENT_IN_FROZEN_SUBCIRCUIT"
    summary = {
        "verdict": verdict,
        "model_freeze_recommended": False,
        "source_table_count": len(search_files),
        "source_result_rows": int(len(search_rows)),
        "explicit_male_pc1_hit_rows": int(len(observed)),
        "unique_explicit_male_pc1_candidates": int(len(candidates)),
        "candidates_in_frozen_ir": in_ir,
        "candidate_bodyIds": candidate_ids,
        "protocol_lock_sha256": lock_hash,
        "frozen_inputs_unchanged": True,
    }
    write_json(output / "run_metadata.json", summary)
    changed = [path for path, digest in tracked.items() if sha256(path) != digest]
    if changed or sha256(output / "protocol_lock.json") != lock_hash:
        raise RuntimeError(f"Source/protocol changed during screen: {changed}")
    concise = candidates[["bodyId", "explicit_hit_count", "all_result_appearances", "best_explicit_rank", "best_any_rank", "best_explicit_score", "best_any_score", "type", "instance", "somaSide", "fruDsx", "in_frozen_ir"]]
    report = [
        "# R71G01 NeuronBridge 搜索结果审计（v3）", "",
        f"**结论：{verdict}。**", "",
        "18 份用户导出的雄性 Brain R71G01 MCFO 查询表包含明确标成 MaleCNS `pC1*` 的候选；该结果是 R71G01 图像到 EM 形态的候选证据，不是 Zhou 2015 的 R71G01-LexA∩dsxGAL4 交集，也不是钙成像 ROI 的直接定义。", "",
        "## 被明确标为 MaleCNS pC1 的候选", "", markdown_table(concise), "",
        "`explicit_male_pc1_hits.csv` 保留每个显式命中行；`all_candidate_appearances.csv` 也保留同一 bodyId 在其他通道的未标注出现，用于复查一致性。未标注出现不能独自升级为 pC1 证据。", "",
        "## 对当前模型的影响", "",
        f"候选共有 {len(candidates)} 个，其中当前冻结 IR 内为 {in_ir} 个。因为 strict importer 只接受当前冻结 IR 内的 bodyId，本批候选不能导入当前模型；不能据此修改或冻结 Golden Model。", "",
        "如果要研究该形态候选，需新建并独立锁定扩展子电路版本，随后再检查它与 IPI 输入、vPN1/mAL 机制和原读出群的连接关系。即便扩展成功，仍须获得 `R71G01∩dsx` 或 ROI 的直接证据，才能称为实验 ROI 映射。", "",
        "## 来源与可追溯性", "",
        "查询来源：用户在 NeuronBridge 以 R71G01 的 FlyLight Gen1 MCFO 雄性 Brain 资料进行的 6 个切片 × 3 通道搜索；原始 CSV 的哈希在 `protocol_lock.json`。完整 MaleCNS 注释版本与冻结 IR 同样已锁定。", "",
        f"lock: `{lock_hash}`。",
    ]
    (output / "report.md").write_text("\n".join(report), encoding="utf-8")
    manifest = {str(path.relative_to(output)): sha256(path) for path in output.rglob("*") if path.is_file()}
    write_json(output / "artifact_sha256.json", manifest)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "configs/neuronbridge_r71g01_screen_v3.json")
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    run(args.config, args.output_dir)
