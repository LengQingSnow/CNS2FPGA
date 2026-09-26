"""Strict importer for an externally curated experimental driver/ROI-to-bodyId map."""
from __future__ import annotations

import hashlib
from pathlib import Path

import pandas as pd


REQUIRED_COLUMNS = [
    "experiment_id", "bodyId", "evidence_id", "mapping_method", "source_url",
    "source_version", "sex", "age_or_stage", "driver_or_roi", "confidence",
]
DIRECT_METHODS = {"direct_expression_registration", "morphology_registration"}


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_direct_map(path, neurons, known_experiments):
    """Validate direct evidence without deriving it from type or fruDsx annotations."""
    path = Path(path)
    if {"bodyId", "neuron_index"} - set(neurons.columns):
        raise ValueError("Frozen IR must provide bodyId and neuron_index")
    mapping = pd.read_csv(path)
    missing = set(REQUIRED_COLUMNS) - set(mapping.columns)
    if missing:
        raise ValueError(f"External ROI map lacks required columns: {sorted(missing)}")
    mapping = mapping[REQUIRED_COLUMNS].copy()
    if mapping.empty:
        raise ValueError("External ROI map is empty")
    if not mapping.experiment_id.isin(known_experiments).all():
        invalid = sorted(set(mapping.experiment_id) - set(known_experiments))
        raise ValueError(f"Unknown experiment_id: {invalid}")
    if not mapping.mapping_method.isin(DIRECT_METHODS).all():
        invalid = sorted(set(mapping.mapping_method) - DIRECT_METHODS)
        raise ValueError(f"Mapping method must be direct expression/morphology registration, not {invalid}")
    if not mapping.sex.eq("male").all():
        raise ValueError("This MaleCNS model accepts only male experimental mapping evidence")
    if mapping.age_or_stage.isna().any() or mapping.age_or_stage.astype(str).str.strip().eq("").any():
        raise ValueError("age_or_stage must be explicit for every mapping row")
    if mapping.source_url.isna().any() or mapping.source_version.isna().any() or mapping.evidence_id.isna().any():
        raise ValueError("source_url, source_version and evidence_id are mandatory provenance")
    if mapping.duplicated(["experiment_id", "bodyId"]).any():
        raise ValueError("Duplicate experiment_id/bodyId mapping rows")
    available = set(neurons.bodyId.astype(int))
    unknown = sorted(set(mapping.bodyId.astype(int)) - available)
    if unknown:
        raise ValueError(f"External map bodyIds absent from the frozen IR: {unknown}")
    mapping["bodyId"] = mapping.bodyId.astype(int)
    mapping["neuron_index"] = mapping.bodyId.map(neurons.set_index("bodyId").neuron_index).astype(int)
    return mapping.sort_values(["experiment_id", "neuron_index"]).reset_index(drop=True), sha256(path)
