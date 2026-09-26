"""Evidence-tiered mapping between published experimental labels and local IR cells."""
from __future__ import annotations

import numpy as np
import pandas as pd


def pC1_mask(neurons):
    return neurons.type.fillna("").str.match(r"^pC1")


def candidate_masks(neurons):
    base = pC1_mask(neurons)
    fru = neurons.fruDsx.fillna("")
    synonym = neurons.synonyms.fillna("")
    return {
        "pC1_type_all": base,
        "pC1_fruDsx_nonmissing": base & fru.ne(""),
        "pC1_fruDsx_coexpress": base & fru.str.startswith("coexpress"),
        "pC1_pMP_alias": base & synonym.str.contains(r"pMP-e|pMP4", regex=True),
    }


def side_counts(rows):
    """Use dataset-provided soma side; unknown values remain visible, not assigned."""
    result = rows.somaSide.fillna("unknown").value_counts(dropna=False).to_dict()
    return {str(key): int(value) for key, value in result.items()}


def make_candidate_summary(neurons, definitions, reported_per_hemi):
    masks = candidate_masks(neurons)
    rows = []
    for definition in definitions:
        identifier = definition["id"]
        if identifier not in masks:
            raise ValueError(f"No implementation for candidate {identifier}")
        selected = neurons.loc[masks[identifier]]
        sides = side_counts(selected)
        left, right = sides.get("L", 0), sides.get("R", 0)
        rows.append(dict(candidate_id=identifier, rule=definition["rule"], status=definition["status"],
                         neurons=len(selected), soma_left=left, soma_right=right,
                         soma_other=int(len(selected)-left-right),
                         matches_reported_male_count_per_side=(left == right == reported_per_hemi),
                         type_labels=int(selected.type.nunique()),
                         body_ids=";".join(map(str, selected.bodyId.astype(int).tolist()))))
    return pd.DataFrame(rows)


def audit_available_fields(neurons):
    required = {"bodyId", "type", "synonyms", "fruDsx", "somaSide"}
    missing = required - set(neurons.columns)
    if missing:
        raise ValueError(f"IR lacks fields used by mapping audit: {sorted(missing)}")
    driver_like = [column for column in neurons.columns
                   if any(token in column.lower() for token in ("driver", "gal4", "lexa", "expression", "roi"))]
    return {"driver_or_roi_expression_fields": driver_like,
            "can_exactly_map_r71g01_intersection": False,
            "reason": "No per-neuron R71G01/dsx intersection expression or LPC neurite ROI-membership field in local IR."}


def exact_vpn1_mapping(neurons):
    selected = neurons[neurons.synonyms.fillna("").str.contains("Zhou 2015: vPN1", regex=False)].copy()
    if selected.empty:
        raise ValueError("Named Zhou 2015 vPN1 annotation was not found")
    return selected
