"""Enrich NeuronBridge MaleCNS matches with the pinned MaleCNS v1.0 annotations."""
from __future__ import annotations

import numpy as np
import pandas as pd


ANNOTATION_COLUMNS = [
    "bodyId", "type", "instance", "somaSide", "synonyms", "fruDsx", "status",
    "flywireType", "hemibrainType",
]


def male_cns_hits(search_rows):
    """Extract MaleCNS result rows and parse the versioned neuron identifier."""
    selected = search_rows.loc[
        search_rows["Neuron ID"].astype(str).str.startswith("male-cns:")
    ].copy()
    selected["bodyId"] = selected["Neuron ID"].str.rsplit(":", n=1).str[-1].astype("int64")
    return selected.reset_index(drop=True)


def enrich_hits(male_hits, annotations, frozen_neurons):
    """Join search rows to v1.0 annotations and frozen-IR membership."""
    available = [column for column in ANNOTATION_COLUMNS if column in annotations.columns]
    context = annotations.loc[:, available].drop_duplicates("bodyId").copy()
    context = context.rename(columns={column: f"v1_{column}" for column in available if column != "bodyId"})
    enriched = male_hits.merge(context, on="bodyId", how="left", validate="many_to_one", indicator="annotation_join")
    membership = frozen_neurons.loc[:, ["bodyId", "neuron_index"]].drop_duplicates("bodyId").copy()
    membership["in_frozen_ir"] = True
    enriched = enriched.merge(membership, on="bodyId", how="left", validate="many_to_one")
    enriched["in_frozen_ir"] = enriched["in_frozen_ir"].fillna(False).astype(bool)
    enriched["neuron_index"] = enriched["neuron_index"].astype("Int64")
    enriched["is_pc1_v1"] = enriched["v1_type"].fillna("").str.match(r"^pC1", case=False)
    return enriched


def summarise_pc1_hits(enriched):
    """Summarize every v1.0 pC1 seen in any of the supplied search tables."""
    pc1 = enriched.loc[enriched["is_pc1_v1"]].copy()
    if pc1.empty:
        return pd.DataFrame()
    return (
        pc1.groupby("bodyId", as_index=False)
        .agg(
            type=("v1_type", "first"),
            instance=("v1_instance", "first"),
            somaSide=("v1_somaSide", "first"),
            fruDsx=("v1_fruDsx", "first"),
            status=("v1_status", "first"),
            appearances=("bodyId", "size"),
            distinct_search_files=("source_file", "nunique"),
            source_files=("source_file", lambda values: ";".join(sorted(set(values)))),
            best_rank=("Number", "min"),
            median_rank=("Number", "median"),
            best_score=("Score", "max"),
            max_matched_pixels=("Matched Pixels", "max"),
            in_frozen_ir=("in_frozen_ir", "first"),
        )
        .sort_values(["best_rank", "best_score", "bodyId"], ascending=[True, False, True])
        .reset_index(drop=True)
    )


def classify_extraction(annotations, forward, backward, max_hops, search_summary):
    """Classify every pC1 annotation under the frozen extractor path rule."""
    pc1 = annotations.loc[
        annotations["type"].fillna("").str.match(r"^pC1", case=False),
        ["bodyId", "type", "instance", "somaSide", "synonyms", "fruDsx", "status"],
    ].copy()
    pc1["input_distance"] = pc1["bodyId"].map(forward).astype("Int64")
    pc1["output_distance"] = pc1["bodyId"].map(backward).astype("Int64")
    pc1["distance_sum"] = pc1["input_distance"] + pc1["output_distance"]
    missing_input = pc1["input_distance"].isna()
    missing_output = pc1["output_distance"].isna()
    exceeds = pc1["distance_sum"].gt(max_hops).fillna(False)
    pc1["extraction_reason"] = np.select(
        [missing_input, missing_output, exceeds],
        ["not_forward_reachable_within_limit", "not_backward_reachable_within_limit", "distance_sum_exceeds_limit"],
        default="selected",
    )
    pc1["selected_by_extractor"] = pc1["extraction_reason"].eq("selected")
    search_columns = [
        "bodyId", "appearances", "distinct_search_files", "best_rank", "median_rank",
        "best_score", "max_matched_pixels",
    ]
    status = pc1.merge(search_summary.loc[:, search_columns], on="bodyId", how="left", validate="one_to_one")
    status["found_in_search"] = status["appearances"].notna()
    for column in ["appearances", "distinct_search_files", "best_rank", "max_matched_pixels"]:
        status[column] = status[column].astype("Int64")
    return status.sort_values(
        ["selected_by_extractor", "found_in_search", "best_rank", "bodyId"],
        ascending=[False, False, True, True], na_position="last",
    ).reset_index(drop=True)


def per_file_coverage(search_rows, enriched):
    """Expose how much MaleCNS and pC1 information each exported search contains."""
    totals = search_rows.groupby("source_file", as_index=False).agg(total_result_rows=("Neuron ID", "size"))
    male = (
        enriched.groupby("source_file", as_index=False)
        .agg(
            male_cns_rows=("bodyId", "size"),
            unique_male_cns=("bodyId", "nunique"),
            pC1_rows=("is_pc1_v1", "sum"),
            annotation_joined=("annotation_join", lambda values: int((values == "both").sum())),
        )
    )
    result = totals.merge(male, on="source_file", how="left", validate="one_to_one")
    count_columns = ["male_cns_rows", "unique_male_cns", "pC1_rows", "annotation_joined"]
    result[count_columns] = result[count_columns].fillna(0).astype(int)
    return result.sort_values("source_file").reset_index(drop=True)
