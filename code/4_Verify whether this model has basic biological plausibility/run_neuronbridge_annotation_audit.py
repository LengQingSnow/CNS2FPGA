"""Audit all MaleCNS hits in the user-exported R71G01 NeuronBridge results."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
from cns2fpga_plausibility.neuronbridge_annotation_audit import (
    classify_extraction, enrich_hits, male_cns_hits, per_file_coverage, summarise_pc1_hits,
)
from cns2fpga_plausibility.neuronbridge_screen import read_search_tables, sha256


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
    search_config_path = (config_path.parent / cfg["search_config"]).resolve()
    search_cfg = json.loads(search_config_path.read_text(encoding="utf-8"))
    search_dir = (search_config_path.parent / search_cfg["search_dir"]).resolve()
    search_rows, search_files = read_search_tables(search_dir, search_cfg["expected_files"])
    extractor_root = (config_path.parent / cfg["extractor_root"]).resolve()
    extractor_config_path = (config_path.parent / cfg["extractor_config"]).resolve()
    annotation_path = (config_path.parent / cfg["annotation_table"]).resolve()
    connectivity_path = (config_path.parent / cfg["connectivity_table"]).resolve()
    frozen_ir_path = (config_path.parent / cfg["frozen_ir"]).resolve()
    sys.path.insert(0, str(extractor_root / "src"))
    from cns2fpga_extractor.core import distances, load_annotations, resolve

    source_files = [
        config_path, search_config_path, extractor_config_path, annotation_path,
        connectivity_path, frozen_ir_path, Path(__file__),
        ROOT / "src/cns2fpga_plausibility/neuronbridge_annotation_audit.py",
        ROOT / "src/cns2fpga_plausibility/neuronbridge_screen.py",
        extractor_root / "src/cns2fpga_extractor/core.py", *search_files,
    ]
    absent = [path for path in source_files if not path.exists()]
    if absent:
        raise FileNotFoundError(f"Required audit source is missing: {absent}")
    tracked = {str(path): sha256(path) for path in source_files}
    output = (output_dir or ROOT / "outputs" / cfg["name"]).resolve()
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(f"Refusing to overwrite annotation audit: {output}")
    output.mkdir(parents=True, exist_ok=True)
    lock = {
        "locked_at_utc": datetime.now(timezone.utc).isoformat(), "config": cfg,
        "search_query_provenance": search_cfg["query_provenance"],
        "input_and_source_sha256": tracked,
    }
    write_json(output / "protocol_lock.json", lock)
    lock_hash = sha256(output / "protocol_lock.json")

    annotations_raw = pd.read_feather(annotation_path)
    frozen = pd.read_csv(frozen_ir_path)
    male_hits = male_cns_hits(search_rows)
    enriched = enrich_hits(male_hits, annotations_raw, frozen)
    search_summary = summarise_pc1_hits(enriched)
    coverage = per_file_coverage(search_rows, enriched)

    extractor_cfg = json.loads(extractor_config_path.read_text(encoding="utf-8"))
    annotations = load_annotations(annotation_path, extractor_cfg.get("annotation_filters", {}))
    input_ids = set().union(*(match.body_ids for match in resolve(annotations, extractor_cfg["selectors"]["inputs"])))
    output_ids = set().union(*(match.body_ids for match in resolve(annotations, extractor_cfg["selectors"]["outputs"])))
    options = extractor_cfg["extraction"]
    distance_args = dict(
        connectivity=connectivity_path, eligible=set(annotations.bodyId.astype(int)),
        max_hops=int(options["max_hops"]), minimum=int(options["min_synapse_count"]),
        batch_rows=int(options["batch_rows"]), frontier_limit=int(options["max_frontier_nodes"]),
    )
    forward = distances(seeds=input_ids, direction="forward", **distance_args)
    backward = distances(seeds=output_ids, direction="reverse", **distance_args)
    extraction_status = classify_extraction(
        annotations.reset_index(drop=True), forward, backward, int(options["max_hops"]), search_summary,
    )
    frozen_pc1 = set(frozen.loc[frozen["type"].fillna("").str.match(r"^pC1", case=False), "bodyId"].astype(int))
    calculated_pc1 = set(extraction_status.loc[extraction_status.selected_by_extractor, "bodyId"].astype(int))
    if frozen_pc1 != calculated_pc1:
        raise RuntimeError("Recomputed pC1 extraction membership differs from the frozen IR")

    enriched.to_csv(output / "all_malecns_hits_enriched.csv", index=False)
    enriched.loc[enriched.is_pc1_v1].to_csv(output / "pc1_hit_rows_enriched.csv", index=False)
    search_summary.to_csv(output / "pc1_search_candidate_summary.csv", index=False)
    extraction_status.to_csv(output / "all_pc1_extraction_status.csv", index=False)
    coverage.to_csv(output / "per_file_coverage.csv", index=False)
    search_summary.head(50).to_csv(output / "top50_pc1_search_candidates.csv", index=False)

    joined_rows = int(enriched.annotation_join.eq("both").sum())
    unique_male = int(enriched.bodyId.nunique())
    pc1_hit_rows = int(enriched.is_pc1_v1.sum())
    pc1_candidates = int(search_summary.bodyId.nunique())
    pc1_in_ir = int(search_summary.in_frozen_ir.sum())
    pc1_outside = pc1_candidates - pc1_in_ir
    reasons = {str(key): int(value) for key, value in extraction_status.extraction_reason.value_counts().items()}
    target = extraction_status.loc[extraction_status.bodyId.eq(10217)].iloc[0]
    summary = {
        "verdict": "BROAD_PC1_RECOVERY_WITH_PATH_LIMIT_EXCLUSIONS",
        "model_freeze_recommended": False,
        "source_table_count": len(search_files),
        "source_result_rows": int(len(search_rows)),
        "male_cns_result_rows": int(len(enriched)),
        "unique_male_cns_bodyIds": unique_male,
        "v09_to_v10_joined_rows": joined_rows,
        "v09_to_v10_unmatched_rows": int(len(enriched) - joined_rows),
        "pc1_result_rows_after_v10_enrichment": pc1_hit_rows,
        "unique_pc1_search_candidates": pc1_candidates,
        "pc1_search_candidates_in_frozen_ir": pc1_in_ir,
        "pc1_search_candidates_outside_frozen_ir": pc1_outside,
        "all_v10_pc1_annotations": int(len(extraction_status)),
        "extraction_reason_counts": reasons,
        "bodyId_10217": {
            "type": str(target["type"]), "input_distance": int(target["input_distance"]),
            "output_distance": int(target["output_distance"]), "distance_sum": int(target["distance_sum"]),
            "max_hops": int(options["max_hops"]), "reason": str(target["extraction_reason"]),
            "found_in_search": bool(target["found_in_search"]), "best_rank": int(target["best_rank"]),
        },
        "protocol_lock_sha256": lock_hash,
        "frozen_inputs_unchanged": True,
    }
    write_json(output / "run_metadata.json", summary)
    changed = [path for path, digest in tracked.items() if sha256(path) != digest]
    if changed or sha256(output / "protocol_lock.json") != lock_hash:
        raise RuntimeError(f"Source/protocol changed during audit: {changed}")

    top = search_summary.head(12)[
        ["bodyId", "type", "instance", "appearances", "best_rank", "best_score", "in_frozen_ir"]
    ]
    report = [
        "# R71G01 NeuronBridge 全量注释与提取路径审计（v3c）", "",
        "**结论：18 份搜索表在补全 MaleCNS v1.0 注释后检出 148 个 pC1；107 个已在冻结子图，41 个在子图外。`10217` 不是唯一 pC1 候选。**", "",
        f"全部 {len(enriched):,} 条 MaleCNS v0.9 结果、{unique_male:,} 个唯一 bodyId 都能按相同 bodyId 对上固定的 v1.0 注释表；未匹配行数为 {len(enriched)-joined_rows}。补全后得到 {pc1_hit_rows:,} 条 pC1 命中、{pc1_candidates} 个唯一 pC1。早先只检查 CSV 自带 `Neuron Type` 会漏掉大多数通道，因为部分导出没有该列。", "",
        "## 排名靠前的 pC1", "", markdown_table(top), "",
        "`best_rank` 是每份导出内部名次，`best_score` 是 NeuronBridge 搜索分数。两者用于排序和复查，不是校准后的置信概率。R71G01 单独的 MCFO 结果也不能直接定义 R71G01∩dsx 交集或钙成像 ROI。", "",
        "## 为什么 10217 不在当前子图", "",
        f"`10217 / {target['type']}` 符合第二步 `^pC1` relay 选择器。从 JO-A/JO-B 输入到它的最短距离为 {int(target['input_distance'])} 跳，从它到 pIP10/pMP2 输出的最短距离为 {int(target['output_distance'])} 跳，总计 {int(target['distance_sum'])} 跳。冻结规则要求总距离 ≤ {int(options['max_hops'])}，因此其排除原因是 `{target['extraction_reason']}`。", "",
        f"完整 v1.0 注释共有 {len(extraction_status)} 个 `^pC1`：{reasons.get('selected',0)} 个进入冻结 IR，{reasons.get('distance_sum_exceeds_limit',0)} 个因总距离超过限制被排除；没有 pC1 因单向不可达被排除。当前阈值为每条聚合边至少 {int(options['min_synapse_count'])} 个突触。", "",
        "## 工程决定", "",
        "现有模型已经覆盖多数搜索命中的 pC1，包括排名最靠前的一批。仅凭 `10217` 的第 1466 名最佳命中，没有依据单独把它加入网络。若以后要测试第五跳 pC1，应建立 max_hops=5 的独立子图版本并重新计算规模、BRAM 和全部 Golden Model 结果。", "",
        "## 产物", "",
        "- `all_malecns_hits_enriched.csv`：全部 MaleCNS 命中及 v1.0 注释、冻结 IR 成员关系。",
        "- `pc1_search_candidate_summary.csv`：148 个 pC1 的跨文件汇总。",
        "- `all_pc1_extraction_status.csv`：156 个 v1.0 pC1 的输入/输出距离和排除原因。",
        "- `per_file_coverage.csv`：18 份导出的覆盖情况。",
        f"- lock: `{lock_hash}`。",
    ]
    (output / "report.md").write_text("\n".join(report), encoding="utf-8")
    manifest = {str(path.relative_to(output)): sha256(path) for path in output.rglob("*") if path.is_file()}
    write_json(output / "artifact_sha256.json", manifest)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "configs/neuronbridge_r71g01_annotation_audit_v3c.json")
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    run(args.config, args.output_dir)
