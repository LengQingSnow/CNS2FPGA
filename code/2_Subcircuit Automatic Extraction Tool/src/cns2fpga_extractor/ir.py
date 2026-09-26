"""Convert a graph subcircuit into a stable CSR-oriented CNS2FPGA IR."""

from __future__ import annotations

from math import ceil

import pandas as pd


# Match the presynaptic transmitter-sign convention in Shiu et al., Nature 2024.
NT_SIGN = {"acetylcholine": 1, "gaba": -1, "glutamate": -1}


def add_neurotransmitters(neurons: pd.DataFrame, transmitters_path) -> pd.DataFrame:
    transmitters = pd.read_feather(transmitters_path)[
        ["body", "predicted_nt", "predicted_nt_confidence", "consensus_nt"]
    ].rename(columns={"body": "bodyId"})
    result = neurons.merge(transmitters, on="bodyId", how="left")
    result["nt_model_sign"] = result["consensus_nt"].map(NT_SIGN).fillna(0).astype("int8")
    return result


def build_ir(neurons: pd.DataFrame, edges: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Index neurons by body ID and make a deterministic CSR adjacency representation."""
    neurons = neurons.sort_values("bodyId").reset_index(drop=True).copy()
    neurons.insert(0, "neuron_index", range(len(neurons)))
    index_of = pd.Series(neurons.neuron_index.to_numpy(), index=neurons.bodyId.to_numpy())
    synapses = edges.rename(columns={"body_pre": "pre_body_id", "body_post": "post_body_id", "weight": "synapse_count"}).copy()
    synapses["pre_index"] = synapses.pre_body_id.map(index_of).astype("int32")
    synapses["post_index"] = synapses.post_body_id.map(index_of).astype("int32")
    signs = neurons.set_index("neuron_index")["nt_model_sign"]
    synapses["nt_model_sign"] = synapses.pre_index.map(signs).astype("int8")
    synapses = synapses.sort_values(["pre_index", "post_index"]).reset_index(drop=True)
    counts = synapses.groupby("pre_index").size()
    offsets = pd.DataFrame({"pre_index": neurons.neuron_index})
    offsets["edge_count"] = offsets.pre_index.map(counts).fillna(0).astype("int32")
    offsets["edge_start"] = offsets.edge_count.cumsum().shift(fill_value=0).astype("int64")
    return neurons, synapses, offsets


def summarize(neurons: pd.DataFrame, synapses: pd.DataFrame, ir: dict) -> tuple[dict, dict]:
    fan_out = synapses.groupby("pre_index").size()
    fan_in = synapses.groupby("post_index").size()
    graph = {
        "neurons": int(len(neurons)),
        "nonzero_edges": int(len(synapses)),
        "aggregate_synapses": int(synapses.synapse_count.sum()),
        "max_fan_out_edges": int(fan_out.max()) if len(fan_out) else 0,
        "max_fan_in_edges": int(fan_in.max()) if len(fan_in) else 0,
    }
    bits = (
        graph["neurons"] * int(ir["neuron_record_bits"])
        + (graph["neurons"] + 1) * int(ir["offset_entry_bits"])
        + graph["nonzero_edges"] * int(ir["synapse_record_bits"])
    )
    estimate = {
        "total_bits": bits,
        "bram36_equivalent": ceil(bits / int(ir["bram36_bits"])),
        "assumption": "Storage estimate only; excludes buffers, port replication and control logic."
    }
    return graph, estimate
