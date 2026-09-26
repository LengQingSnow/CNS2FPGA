"""Import a direct-evidence ROI map into a new, locked mapping audit directory."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
from cns2fpga_plausibility.external_roi_import import load_direct_map, sha256


def write_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mapping-csv", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--ir-neurons", type=Path, default=ROOT / "../2_Subcircuit Automatic Extraction Tool/outputs/courtship_song_v0/neuron_table.csv")
    args = parser.parse_args()
    output = args.output_dir.resolve()
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(f"Refusing to overwrite imported ROI map: {output}")
    neurons = pd.read_csv(args.ir_neurons)
    known = {"zhou2015_vPN1_split_gal4", "zhou2015_pC1_intersection", "zhou2015_pC1_calcium_roi"}
    mapping, mapping_hash = load_direct_map(args.mapping_csv, neurons, known)
    output.mkdir(parents=True, exist_ok=True)
    mapping.to_csv(output / "direct_roi_bodyid_map.csv", index=False)
    summary = mapping.groupby("experiment_id").agg(neurons=("bodyId", "size"),
        body_ids=("bodyId", lambda value: ";".join(map(str, value))),
        methods=("mapping_method", lambda value: ";".join(sorted(set(value)))),
        sources=("source_url", lambda value: ";".join(sorted(set(value))))).reset_index()
    summary.to_csv(output / "direct_roi_summary.csv", index=False)
    write_json(output / "provenance_lock.json", {
        "mapping_csv": str(args.mapping_csv.resolve()), "mapping_sha256": mapping_hash,
        "ir_neurons": str(args.ir_neurons.resolve()), "ir_neurons_sha256": sha256(args.ir_neurons),
        "accepted_methods": sorted(["direct_expression_registration", "morphology_registration"]),
        "rejected_as_insufficient": ["type-only selection", "fruDsx-only selection", "historical-alias-only selection", "activity-based selection"],
    })
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
