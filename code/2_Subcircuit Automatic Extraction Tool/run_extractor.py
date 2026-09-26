"""Run a configured MaleCNS subcircuit extraction and write the CNS2FPGA IR."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from cns2fpga_extractor.core import extract, load_annotations, resolve
from cns2fpga_extractor.ir import add_neurotransmitters, build_ir, summarize


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path, help="JSON extraction definition")
    parser.add_argument("--output-dir", type=Path, help="Override outputs/<config-name>")
    return parser.parse_args()


def path_from(config_path: Path, relative: str) -> Path:
    return (config_path.parent / relative).resolve()


def report_markdown(name: str, counts: dict, graph: dict, storage: dict) -> str:
    selector_rows = "\n".join(f"| {name} | {value:,} |" for name, value in counts.items())
    graph_rows = "\n".join(f"| {name.replace('_', ' ')} | {value:,} |" for name, value in graph.items())
    return f"""# {name}: subcircuit extraction

## Selector and path result

| Item | Count |
| --- | ---: |
{selector_rows}

## Directed induced subgraph

| Metric | Value |
| --- | ---: |
{graph_rows}

## Storage planning estimate

- Total IR bits: {storage['total_bits']:,}
- BRAM36 equivalent: {storage['bram36_equivalent']:,}
- Note: {storage['assumption']}
"""


def main() -> None:
    args = parse_args()
    config_path = args.config.resolve()
    config = json.loads(config_path.read_text(encoding="utf-8"))
    data = {name: path_from(config_path, value) for name, value in config["data"].items()}
    missing = [str(path) for path in data.values() if not path.is_file()]
    if missing:
        raise FileNotFoundError("Missing MaleCNS files:\n" + "\n".join(missing))

    output = (args.output_dir or ROOT / "outputs" / config["name"]).resolve()
    output.mkdir(parents=True, exist_ok=True)
    annotations = load_annotations(data["annotations"], config.get("annotation_filters", {}))
    input_matches = resolve(annotations, config["selectors"]["inputs"])
    relay_matches = resolve(annotations, config["selectors"].get("relays", []))
    output_matches = resolve(annotations, config["selectors"]["outputs"])
    input_ids = set().union(*(match.body_ids for match in input_matches))
    relay_ids = set().union(*(match.body_ids for match in relay_matches)) if relay_matches else set()
    output_ids = set().union(*(match.body_ids for match in output_matches))

    neurons, edges, forward, backward = extract(
        data["connectivity"], annotations, input_ids, output_ids, config["extraction"]
    )
    neurons = add_neurotransmitters(neurons, data["neurotransmitters"])
    neurons["is_input_anchor"] = neurons.bodyId.isin(input_ids)
    neurons["is_relay_anchor"] = neurons.bodyId.isin(relay_ids)
    neurons["is_output_anchor"] = neurons.bodyId.isin(output_ids)
    neurons, synapses, offsets = build_ir(neurons, edges)
    graph, storage = summarize(neurons, synapses, config["ir"])
    counts = {
        "input anchors matched": len(input_ids),
        "relay anchors matched": len(relay_ids),
        "output anchors matched": len(output_ids),
        "input anchors retained": int(neurons.is_input_anchor.sum()),
        "relay anchors retained": int(neurons.is_relay_anchor.sum()),
        "output anchors retained": int(neurons.is_output_anchor.sum()),
        "forward reachable neurons": len(forward),
        "backward reachable neurons": len(backward),
        "path-retained neurons": len(neurons),
    }

    keep_columns = [
        "neuron_index", "bodyId", "type", "instance", "synonyms", "flywireType",
        "hemibrainType", "superclass", "class",
        "somaSide", "dimorphism", "fruDsx", "consensus_nt", "predicted_nt",
        "predicted_nt_confidence", "nt_model_sign", "input_distance", "output_distance",
        "is_input_anchor", "is_relay_anchor", "is_output_anchor",
    ]
    neurons[[column for column in keep_columns if column in neurons.columns]].to_csv(
        output / "neuron_table.csv", index=False
    )
    synapses[["pre_index", "post_index", "synapse_count", "nt_model_sign"]].to_csv(
        output / "synapse_table.csv", index=False
    )
    offsets.to_csv(output / "offset_table.csv", index=False)
    neurons.loc[neurons.is_input_anchor, ["neuron_index", "bodyId", "type", "instance"]].to_csv(
        output / "input_mapping.csv", index=False
    )
    neurons.loc[neurons.is_output_anchor, ["neuron_index", "bodyId", "type", "instance"]].to_csv(
        output / "output_mapping.csv", index=False
    )
    relay_columns = ["neuron_index", "bodyId", "type", "instance", "synonyms"]
    neurons.loc[neurons.is_relay_anchor, relay_columns].to_csv(
        output / "relay_mapping.csv", index=False
    )
    metadata = {"config": config, "counts": counts, "graph": graph, "storage": storage}
    (output / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    report = report_markdown(config["name"], counts, graph, storage)
    (output / "report.md").write_text(report, encoding="utf-8")
    print(report)
    print(f"Wrote IR to {output}")


if __name__ == "__main__":
    main()
