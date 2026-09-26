"""Streaming, directed subgraph extraction for MaleCNS Feather tables."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import pandas as pd
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.feather as feather


@dataclass(frozen=True)
class SelectorResult:
    label: str
    field: str
    pattern: str
    body_ids: frozenset[int]


def load_annotations(path: Path) -> pd.DataFrame:
    """Load the small, curated neuron annotation table and normalize body IDs."""
    annotations = pd.read_feather(path)
    annotations["bodyId"] = annotations["bodyId"].astype("int64")
    return annotations.drop_duplicates("bodyId").set_index("bodyId", drop=False)


def resolve_selectors(
    annotations: pd.DataFrame, selectors: Iterable[dict]
) -> list[SelectorResult]:
    """Resolve configuration regexes against one annotation field at a time."""
    results: list[SelectorResult] = []
    for selector in selectors:
        field = selector["field"]
        if field not in annotations.columns:
            raise ValueError(f"Selector field {field!r} is absent from annotations")
        pattern = selector["pattern"]
        matches = annotations[field].fillna("").astype(str).str.contains(
            pattern, regex=True, case=False
        )
        body_ids = frozenset(int(value) for value in annotations.loc[matches, "bodyId"])
        if not body_ids:
            raise ValueError(
                f"Selector {selector.get('label', pattern)!r} matched no annotated neurons"
            )
        results.append(
            SelectorResult(selector.get("label", pattern), field, pattern, body_ids)
        )
    return results


def _filtered_batches(
    connectivity_path: Path,
    source_column: str,
    frontier: set[int],
    min_weight: int,
    batch_rows: int,
):
    """Yield only graph rows whose source endpoint is in *frontier*.

    Arrow computes the membership predicate per record batch; the 151M-row table
    is never converted to a pandas DataFrame.
    """
    if not frontier:
        return
    table = feather.read_table(connectivity_path, memory_map=True)
    needles = pa.array(sorted(frontier), type=pa.int64())
    for batch in table.to_batches(max_chunksize=batch_rows):
        membership = pc.is_in(batch.column(source_column), value_set=needles)
        strong_enough = pc.greater_equal(batch.column("weight"), pa.scalar(min_weight))
        filtered = pa.RecordBatch.from_arrays(
            [pc.filter(column, pc.and_(membership, strong_enough)) for column in batch.columns],
            schema=batch.schema,
        )
        if filtered.num_rows:
            yield filtered


def _expand(
    connectivity_path: Path,
    frontier: set[int],
    direction: str,
    eligible_nodes: set[int],
    min_weight: int,
    batch_rows: int,
) -> set[int]:
    if direction not in {"forward", "reverse"}:
        raise ValueError("direction must be 'forward' or 'reverse'")
    source = "body_pre" if direction == "forward" else "body_post"
    destination = "body_post" if direction == "forward" else "body_pre"
    discovered: set[int] = set()
    for batch in _filtered_batches(
        connectivity_path, source, frontier, min_weight, batch_rows
    ):
        discovered.update(
            int(value)
            for value in batch.column(destination).to_pylist()
            if int(value) in eligible_nodes
        )
    return discovered


def directed_distances(
    connectivity_path: Path,
    seeds: set[int],
    direction: str,
    eligible_nodes: set[int],
    max_hops: int,
    min_weight: int,
    batch_rows: int,
    max_frontier_nodes: int,
) -> dict[int, int]:
    """Breadth-first distances over strong, annotated edges in one direction."""
    distances = {body_id: 0 for body_id in seeds if body_id in eligible_nodes}
    frontier = set(distances)
    for hop in range(1, max_hops + 1):
        discovered = _expand(
            connectivity_path,
            frontier,
            direction,
            eligible_nodes,
            min_weight,
            batch_rows,
        )
        frontier = discovered.difference(distances)
        if len(frontier) > max_frontier_nodes:
            raise RuntimeError(
                f"{direction} frontier at hop {hop} has {len(frontier):,} nodes, "
                f"exceeding the safety limit {max_frontier_nodes:,}. Increase the "
                "synapse threshold or reduce the hop budget."
            )
        distances.update({body_id: hop for body_id in frontier})
        if not frontier:
            break
    return distances


def induced_edges(
    connectivity_path: Path,
    selected_nodes: set[int],
    min_weight: int,
    batch_rows: int,
) -> pd.DataFrame:
    """Extract thresholded edges whose two endpoints are in the final node set."""
    table = feather.read_table(connectivity_path, memory_map=True)
    node_values = pa.array(sorted(selected_nodes), type=pa.int64())
    pieces: list[pd.DataFrame] = []
    for batch in table.to_batches(max_chunksize=batch_rows):
        keep = pc.and_(
            pc.and_(
                pc.is_in(batch.column("body_pre"), value_set=node_values),
                pc.is_in(batch.column("body_post"), value_set=node_values),
            ),
            pc.greater_equal(batch.column("weight"), pa.scalar(min_weight)),
        )
        filtered = pa.RecordBatch.from_arrays(
            [pc.filter(column, keep) for column in batch.columns], schema=batch.schema
        )
        if filtered.num_rows:
            pieces.append(filtered.to_pandas())
    if not pieces:
        return pd.DataFrame(columns=["body_pre", "body_post", "weight"])
    return pd.concat(pieces, ignore_index=True)


def extract_path_subgraph(
    connectivity_path: Path,
    annotations: pd.DataFrame,
    input_ids: set[int],
    output_ids: set[int],
    extraction: dict,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[int, int], dict[int, int]]:
    """Keep neurons that can lie on an input-to-output path within max_hops."""
    eligible = set(int(value) for value in annotations["bodyId"])
    max_hops = int(extraction["max_hops"])
    min_weight = int(extraction["min_synapse_weight"])
    batch_rows = int(extraction["batch_rows"])
    maximum = int(extraction["max_frontier_nodes"])
    forward = directed_distances(
        connectivity_path, input_ids, "forward", eligible, max_hops, min_weight,
        batch_rows, maximum
    )
    backward = directed_distances(
        connectivity_path, output_ids, "reverse", eligible, max_hops, min_weight,
        batch_rows, maximum
    )
    selected = {
        body_id
        for body_id in forward.keys() & backward.keys()
        if forward[body_id] + backward[body_id] <= max_hops
    }
    neurons = annotations.loc[sorted(selected)].copy()
    neurons["input_distance"] = neurons["bodyId"].map(forward)
    neurons["output_distance"] = neurons["bodyId"].map(backward)
    edges = induced_edges(connectivity_path, selected, min_weight, batch_rows)
    return neurons, edges, forward, backward
