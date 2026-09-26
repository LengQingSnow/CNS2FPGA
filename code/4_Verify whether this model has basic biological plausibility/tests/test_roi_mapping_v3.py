import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from cns2fpga_plausibility.roi_mapping_v3 import (
    audit_available_fields, candidate_masks, exact_vpn1_mapping, make_candidate_summary,
)
from cns2fpga_plausibility.external_roi_import import load_direct_map


def neurons():
    return pd.DataFrame({
        "neuron_index": [0, 1, 2, 3, 4],
        "bodyId": [1, 2, 3, 4, 5],
        "type": ["pC1_a", "pC1_b", "pC2", "pC1x_c", "vPN"],
        "synonyms": ["pMP-e", "", "", "pMP4", "Zhou 2015: vPN1"],
        "fruDsx": ["coexpress_high", "dsx_low", "", None, "coexpress_high"],
        "somaSide": ["L", "R", "L", None, "R"],
    })


def test_candidate_sets_are_annotation_rules_not_implicit_driver_mapping():
    masks = candidate_masks(neurons())
    assert masks["pC1_type_all"].sum() == 3
    assert masks["pC1_fruDsx_nonmissing"].sum() == 2
    assert masks["pC1_fruDsx_coexpress"].sum() == 1
    assert masks["pC1_pMP_alias"].sum() == 2
    definitions = [
        {"id": "pC1_type_all", "rule": "type", "status": "reference"},
        {"id": "pC1_fruDsx_nonmissing", "rule": "fru", "status": "candidate"},
    ]
    summary = make_candidate_summary(neurons(), definitions, 1)
    assert summary.neurons.tolist() == [3, 2]
    # Even an accidental cardinality match cannot elevate an annotation rule to
    # a driver-expression mapping.
    assert summary.matches_reported_male_count_per_side.all()
    assert summary.status.tolist() == ["reference", "candidate"]


def test_exact_named_vpn1_and_missing_driver_fields_are_audited():
    mapped = exact_vpn1_mapping(neurons())
    assert mapped.bodyId.tolist() == [5]
    audit = audit_available_fields(neurons())
    assert audit["driver_or_roi_expression_fields"] == []
    assert not audit["can_exactly_map_r71g01_intersection"]
    with pytest.raises(ValueError, match="Named Zhou"):
        exact_vpn1_mapping(neurons().iloc[:4])


def test_external_map_requires_direct_provenance_and_frozen_bodyids(tmp_path):
    valid = pd.DataFrame([dict(experiment_id="zhou2015_pC1_intersection", bodyId=1, evidence_id="F1",
        mapping_method="direct_expression_registration", source_url="https://example.org", source_version="v1",
        sex="male", age_or_stage="adult", driver_or_roi="R71G01∩dsx", confidence="high")])
    path = tmp_path / "map.csv"
    valid.to_csv(path, index=False)
    result, digest = load_direct_map(path, neurons(), {"zhou2015_pC1_intersection"})
    assert result.neuron_index.tolist() == [0]
    assert len(digest) == 64
    valid.loc[0, "mapping_method"] = "fruDsx-only selection"
    valid.to_csv(path, index=False)
    with pytest.raises(ValueError, match="Mapping method"):
        load_direct_map(path, neurons(), {"zhou2015_pC1_intersection"})
    valid.loc[0, "mapping_method"] = "morphology_registration"
    valid.loc[0, "bodyId"] = 999
    valid.to_csv(path, index=False)
    with pytest.raises(ValueError, match="absent from"):
        load_direct_map(path, neurons(), {"zhou2015_pC1_intersection"})
