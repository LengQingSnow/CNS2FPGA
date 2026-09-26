"""Preserve the extracted graph; specialize only external input flags to left LC10a."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
SOURCE = HERE / "outputs" / "visual_to_steering_v0"
TARGET = HERE / "outputs" / "visual_left_input_ir_v0"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    if TARGET.exists() and any(TARGET.iterdir()):
        raise FileExistsError(f"Refusing to overwrite {TARGET}")
    TARGET.mkdir(parents=True)
    for name in ("synapse_table.csv", "offset_table.csv"):
        shutil.copy2(SOURCE / name, TARGET / name)
    neurons = pd.read_csv(SOURCE / "neuron_table.csv")
    original = neurons.is_input_anchor.astype(bool)
    left = original & neurons.type.eq("LC10a") & neurons.somaSide.eq("L")
    if int(left.sum()) != 109 or int(original.sum()) != 220:
        raise AssertionError("Unexpected MaleCNS input membership")
    neurons["is_input_anchor"] = left
    neurons.to_csv(TARGET / "neuron_table.csv", index=False)
    neurons.loc[left, ["neuron_index", "bodyId", "type", "instance"]].to_csv(
        TARGET / "input_mapping.csv", index=False)
    metadata = json.loads((SOURCE / "metadata.json").read_text(encoding="utf-8"))
    metadata["derived_input_mapping"] = {
        "purpose": "left LC10a only; connectivity and neuron order unchanged",
        "source_ir": str(SOURCE), "source_input_count": 220, "selected_input_count": 109,
        "source_sha256": {name: sha256(SOURCE / name) for name in
                          ("neuron_table.csv", "synapse_table.csv", "offset_table.csv", "metadata.json")}}
    (TARGET / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(f"Left-only input mapping: {int(left.sum())} / {len(neurons)} neurons")


if __name__ == "__main__":
    main()
