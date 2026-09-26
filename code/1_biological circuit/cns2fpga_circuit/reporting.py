"""Graph and early-BRAM reporting for extracted MaleCNS circuits."""

from __future__ import annotations

from math import ceil

import pandas as pd


def summarize_graph(neurons: pd.DataFrame, edges: pd.DataFrame) -> dict:
    node_count = int(len(neurons))
    edge_count = int(len(edges))
    synapse_count = int(edges["weight"].sum()) if edge_count else 0
    fan_out = edges.groupby("body_pre").size() if edge_count else pd.Series(dtype=int)
    fan_in = edges.groupby("body_post").size() if edge_count else pd.Series(dtype=int)
    weighted_out = edges.groupby("body_pre")["weight"].sum() if edge_count else pd.Series(dtype=int)
    weighted_in = edges.groupby("body_post")["weight"].sum() if edge_count else pd.Series(dtype=int)
    return {
        "neurons": node_count,
        "nonzero_edges": edge_count,
        "aggregate_synapses": synapse_count,
        "max_fan_out_edges": int(fan_out.max()) if not fan_out.empty else 0,
        "max_fan_in_edges": int(fan_in.max()) if not fan_in.empty else 0,
        "max_fan_out_synapses": int(weighted_out.max()) if not weighted_out.empty else 0,
        "max_fan_in_synapses": int(weighted_in.max()) if not weighted_in.empty else 0,
    }


def estimate_bram(graph: dict, config: dict) -> dict:
    """Estimate storage only; this does not replace a Vivado utilization report."""
    align = int(config["alignment_bits"])
    bram_bits = int(config["bram36_bits"])
    neuron_bits = graph["neurons"] * int(config["neuron_record_bits"])
    # One CSR offset per virtual neuron plus a terminal offset.
    offset_bits = (graph["neurons"] + 1) * int(config["offset_entry_bits"])
    synapse_bits = graph["nonzero_edges"] * int(config["synapse_record_bits"])
    raw_total = neuron_bits + offset_bits + synapse_bits
    aligned_total = ceil(raw_total / align) * align
    return {
        "assumptions": {
            "neuron_record_bits": int(config["neuron_record_bits"]),
            "synapse_record_bits": int(config["synapse_record_bits"]),
            "offset_entry_bits": int(config["offset_entry_bits"]),
            "bram36_bits": bram_bits,
        },
        "neuron_state_and_parameter_bits": neuron_bits,
        "csr_offset_bits": offset_bits,
        "adjacency_bits": synapse_bits,
        "total_bits_aligned": aligned_total,
        "bram36_equivalent": ceil(aligned_total / bram_bits),
    }


def markdown_report(name: str, selector_counts: dict, graph: dict, bram: dict) -> str:
    lines = [
        f"# {name} extraction report",
        "",
        "## Frozen V0 anchors",
        "",
        "| Role | Matched neurons |",
        "| --- | ---: |",
    ]
    lines.extend(f"| {role} | {count:,} |" for role, count in selector_counts.items())
    lines.extend([
        "",
        "## Extracted directed subgraph",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
    ])
    lines.extend(f"| {key.replace('_', ' ')} | {value:,} |" for key, value in graph.items())
    lines.extend([
        "",
        "## BRAM36 storage estimate",
        "",
        "Assumes 64-bit virtual-neuron records, 64-bit adjacency records, and a 32-bit CSR offset table.",
        "This is an architecture-planning estimate, not post-synthesis utilization.",
        "",
        "| Storage item | Bits |",
        "| --- | ---: |",
        f"| neuron state + parameters | {bram['neuron_state_and_parameter_bits']:,} |",
        f"| CSR offsets | {bram['csr_offset_bits']:,} |",
        f"| adjacency records | {bram['adjacency_bits']:,} |",
        f"| total aligned | {bram['total_bits_aligned']:,} |",
        f"| BRAM36 equivalent | {bram['bram36_equivalent']:,} |",
        "",
    ])
    return "\n".join(lines)
