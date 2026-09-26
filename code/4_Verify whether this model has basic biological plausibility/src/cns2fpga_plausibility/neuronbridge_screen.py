"""Audit R71G01 NeuronBridge image-search tables without overclaiming a ROI map."""
from __future__ import annotations

import hashlib
from pathlib import Path

import pandas as pd


REQUIRED_COLUMNS = {
    "Number", "Neuron ID", "Score", "Matched Pixels", "Library", "Sex",
    "Alignment Space", "Anatomical Area",
}


def sha256(path):
    """Return the digest of one source artifact."""
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def is_explicit_pc1(value):
    """Match pC1 / pC1x labels, but not unrelated LPC1 or LLPC1 classes."""
    return str(value).strip().lower().startswith("pc1")


def read_search_tables(search_dir, expected_files):
    """Read known search exports and retain their source identity."""
    search_dir = Path(search_dir)
    found = sorted(search_dir.glob("20191213_64_H*_Channel*.csv"))
    names = {path.name for path in found}
    expected = set(expected_files)
    if names != expected:
        missing = sorted(expected - names)
        unexpected = sorted(names - expected)
        raise ValueError(f"Unexpected NeuronBridge export set; missing={missing}, unexpected={unexpected}")
    frames = []
    for path in found:
        frame = pd.read_csv(path)
        missing_columns = REQUIRED_COLUMNS - set(frame.columns)
        if missing_columns:
            raise ValueError(f"{path.name} lacks required columns: {sorted(missing_columns)}")
        frame = frame.copy()
        frame["source_file"] = path.name
        frames.append(frame)
    return pd.concat(frames, ignore_index=True), found


def explicit_male_pc1_hits(search_rows):
    """Return only result rows that explicitly identify a MaleCNS pC1 label."""
    labels = search_rows.get("Neuron Type", pd.Series("", index=search_rows.index)).fillna("")
    selected = search_rows.loc[
        search_rows["Neuron ID"].astype(str).str.startswith("male-cns:")
        & labels.map(is_explicit_pc1)
    ].copy()
    selected["bodyId"] = selected["Neuron ID"].str.rsplit(":", n=1).str[-1].astype(int)
    sort_columns = [column for column in ["bodyId", "Number", "source_file"] if column in selected.columns]
    return selected.sort_values(sort_columns).reset_index(drop=True)


def summarise_hits(hits, annotations, frozen_neurons):
    """Attach full MaleCNS and frozen-IR membership; retain every observed hit."""
    context_columns = [
        "bodyId", "type", "instance", "somaSide", "synonyms", "fruDsx", "status",
    ]
    annotation_context = annotations.loc[:, context_columns].copy()
    frozen_context = frozen_neurons.loc[:, ["bodyId", "neuron_index"]].copy()
    frozen_context["in_frozen_ir"] = True
    observed = hits.merge(annotation_context, on="bodyId", how="left", validate="many_to_one")
    observed = observed.merge(frozen_context, on="bodyId", how="left", validate="many_to_one")
    observed["in_frozen_ir"] = observed["in_frozen_ir"].fillna(False).astype(bool)
    observed["neuron_index"] = observed["neuron_index"].astype("Int64")
    summary = (
        observed.groupby("bodyId", as_index=False)
        .agg(
            explicit_hit_count=("bodyId", "size"),
            source_files=("source_file", lambda values: ";".join(sorted(values))),
            best_explicit_rank=("Number", "min"),
            best_explicit_score=("Score", "max"),
            max_matched_pixels=("Matched Pixels", "max"),
            type=("type", "first"),
            instance=("instance", "first"),
            somaSide=("somaSide", "first"),
            fruDsx=("fruDsx", "first"),
            status=("status", "first"),
            in_frozen_ir=("in_frozen_ir", "first"),
        )
        .sort_values(["in_frozen_ir", "explicit_hit_count", "best_explicit_rank"], ascending=[False, False, True])
        .reset_index(drop=True)
    )
    return observed, summary
