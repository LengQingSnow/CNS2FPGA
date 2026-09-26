"""Extract a configured MaleCNS subgraph and produce FPGA-capacity inputs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from cns2fpga_circuit.extractor import (
    extract_path_subgraph,
    load_annotations,
    resolve_selectors,
)
from cns2fpga_circuit.reporting import estimate_bram, markdown_report, summarize_graph


def _config_path(value: str) -> Path:
    return Path(value).resolve()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=_config_path)
    parser.add_argument("--output-dir", type=Path, default=None)
    args = parser.parse_args()

    config_path = args.config
    config = json.loads(config_path.read_text(encoding="utf-8"))
    root = config_path.parent
    data = {key: (root / value).resolve() for key, value in config["data"].items()}
    missing = [str(path) for path in data.values() if not path.is_file()]
    if missing:
        raise FileNotFoundError("Missing MaleCNS input files:\n" + "\n".join(missing))

    output_dir = (args.output_dir or root.parent / "outputs" / config["name"]).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    annotations = load_annotations(data["annotations"])
    input_matches = resolve_selectors(annotations, config["selectors"]["inputs"])
    relay_matches = resolve_selectors(annotations, config["selectors"]["relays"])
    output_matches = resolve_selectors(annotations, config["selectors"]["outputs"])
    input_ids = set().union(*(match.body_ids for match in input_matches))
    output_ids = set().union(*(match.body_ids for match in output_matches))

    neurons, edges, forward, backward = extract_path_subgraph(
        data["connectivity"], annotations, input_ids, output_ids, config["extraction"]
    )
    neurons = neurons.reset_index(drop=True)
    neurotransmitters = pd.read_feather(data["neurotransmitters"])[
        ["body", "predicted_nt", "predicted_nt_confidence", "consensus_nt"]
    ].rename(columns={"body": "bodyId"})
    neurons = neurons.merge(neurotransmitters, on="bodyId", how="left")
    relay_ids = set().union(*(match.body_ids for match in relay_matches))
    neurons["is_input_anchor"] = neurons["bodyId"].isin(input_ids)
    neurons["is_relay_anchor"] = neurons["bodyId"].isin(relay_ids)
    neurons["is_output_anchor"] = neurons["bodyId"].isin(output_ids)
    graph = summarize_graph(neurons, edges)
    bram = estimate_bram(graph, config["fpga_estimate"])
    selector_counts = {
        "input anchors": len(input_ids),
        "relay anchors": len(relay_ids),
        "output anchors": len(output_ids),
        "retained input anchors": int(neurons["is_input_anchor"].sum()),
        "retained relay anchors": int(neurons["is_relay_anchor"].sum()),
        "retained output anchors": int(neurons["is_output_anchor"].sum()),
        "forward-reachable nodes": len(forward),
        "backward-reachable nodes": len(backward),
        "path-retained nodes": len(neurons),
    }
    neurons.to_csv(output_dir / "neurons.csv", index=False)
    edges.to_csv(output_dir / "edges.csv", index=False)
    report = {
        "config": config,
        "selector_counts": selector_counts,
        "graph": graph,
        "bram_estimate": bram,
    }
    (output_dir / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (output_dir / "report.md").write_text(
        markdown_report(config["name"], selector_counts, graph, bram), encoding="utf-8"
    )
    print(markdown_report(config["name"], selector_counts, graph, bram))
    print(f"Wrote {output_dir}")


if __name__ == "__main__":
    main()
