import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from cns2fpga_plausibility.neuronbridge_annotation_audit import (
    classify_extraction, enrich_hits, male_cns_hits, summarise_pc1_hits,
)


def test_missing_search_type_is_recovered_from_pinned_annotation():
    rows = pd.DataFrame({
        "Neuron ID": ["male-cns:v0.9:10", "hemibrain:v1.2.1:20"],
        "Neuron Type": [None, "pC1a"], "Number": [3, 4], "Score": [8.0, 7.0],
        "Matched Pixels": [50, 40], "source_file": ["a.csv", "a.csv"],
    })
    annotations = pd.DataFrame({
        "bodyId": [10], "type": ["pC1_1a"], "instance": ["pC1_1a_L"], "somaSide": ["L"],
        "synonyms": ["pC1"], "fruDsx": ["coexpress_high"], "status": ["Traced"],
        "flywireType": ["pC1a"], "hemibrainType": ["pC1a"],
    })
    frozen = pd.DataFrame({"bodyId": [10], "neuron_index": [2]})
    enriched = enrich_hits(male_cns_hits(rows), annotations, frozen)
    summary = summarise_pc1_hits(enriched)
    assert enriched.is_pc1_v1.tolist() == [True]
    assert summary.bodyId.tolist() == [10]
    assert summary.in_frozen_ir.tolist() == [True]


def test_path_rule_explains_selected_and_fifth_hop_pc1():
    annotations = pd.DataFrame({
        "bodyId": [10, 11], "type": ["pC1_1a", "pC1x_b"],
        "instance": ["pC1_1a_L", "pC1x_b_L"], "somaSide": ["L", "L"],
        "synonyms": ["pC1", "pC1"], "fruDsx": ["coexpress_high", "dsx_high"],
        "status": ["Traced", "Traced"],
    })
    summary = pd.DataFrame({
        "bodyId": [10, 11], "appearances": [2, 1], "distinct_search_files": [2, 1],
        "best_rank": [3, 20], "median_rank": [4.0, 20.0], "best_score": [8.0, 5.0],
        "max_matched_pixels": [50, 30],
    })
    status = classify_extraction(annotations, {10: 2, 11: 3}, {10: 2, 11: 2}, 4, summary)
    reasons = status.set_index("bodyId").extraction_reason.to_dict()
    assert reasons == {10: "selected", 11: "distance_sum_exceeds_limit"}
