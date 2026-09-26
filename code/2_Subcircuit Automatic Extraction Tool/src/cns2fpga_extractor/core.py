"""Streaming directed-path extraction over MaleCNS Feather connectivity data."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import pandas as pd
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.feather as feather


@dataclass(frozen=True)
class Match:
    """Resolved config selector, retained for reproducibility metadata."""

    label: str
    field: str
    regex: str
    body_ids: frozenset[int]


def load_annotations(path: Path, filters: dict) -> pd.DataFrame:
    annotations = pd.read_feather(path)
    annotations["bodyId"] = annotations["bodyId"].astype("int64")
    for selector in filters.get("include", []):
        annotations = _filter_rows(annotations, selector, keep=True)
    for selector in filters.get("exclude", []):
        annotations = _filter_rows(annotations, selector, keep=False)
    return annotations.drop_duplicates("bodyId").set_index("bodyId", drop=False)


def _filter_rows(frame: pd.DataFrame, selector: dict, keep: bool) -> pd.DataFrame:
    field, regex = selector["field"], selector["regex"]
    if field not in frame.columns:
        raise ValueError(f"Annotation filter field not found: {field}")
    mask = frame[field].fillna("").astype(str).str.contains(regex, case=False, regex=True)
    return frame.loc[mask if keep else ~mask].copy()


def resolve(annotations: pd.DataFrame, selectors: Iterable[dict]) -> list[Match]:
    matches: list[Match] = []
    for selector in selectors:
        field, regex = selector["field"], selector["regex"]
        if field not in annotations.columns:
            raise ValueError(f"Selector field not found: {field}")
        mask = annotations[field].fillna("").astype(str).str.contains(regex, case=False, regex=True)
        ids = frozenset(int(value) for value in annotations.loc[mask, "bodyId"])
        if not ids:
            raise ValueError(f"Selector matched no neurons: {selector.get('label', regex)}")
        matches.append(Match(selector.get("label", regex), field, regex, ids))
    return matches


def _edge_batches(path: Path, column: str, frontier: set[int], minimum: int, batch_rows: int):
    """Yield strong edges whose selected endpoint is in frontier without pandas."""
    if not frontier:
        return
    table = feather.read_table(path, memory_map=True)
    values = pa.array(sorted(frontier), type=pa.int64())
    for batch in table.to_batches(max_chunksize=batch_rows):
        keep = pc.and_(
            pc.is_in(batch.column(column), value_set=values),
            pc.greater_equal(batch.column("weight"), pa.scalar(minimum)),
        )
        filtered = pa.RecordBatch.from_arrays(
            [pc.filter(item, keep) for item in batch.columns], schema=batch.schema
        )
        if filtered.num_rows:
            yield filtered


def distances(
    connectivity: Path,
    seeds: set[int],
    direction: str,
    eligible: set[int],
    max_hops: int,
    minimum: int,
    batch_rows: int,
    frontier_limit: int,
) -> dict[int, int]:
    """BFS distances from seeds; reverse mode follows edges toward presynaptic cells."""
    if direction not in {"forward", "reverse"}:
        raise ValueError("direction must be forward or reverse")
    source, destination = ("body_pre", "body_post") if direction == "forward" else ("body_post", "body_pre")
    result = {body_id: 0 for body_id in seeds if body_id in eligible}
    frontier = set(result)
    for hop in range(1, max_hops + 1):
        discovered: set[int] = set()
        for batch in _edge_batches(connectivity, source, frontier, minimum, batch_rows):
            discovered.update(
                int(body_id) for body_id in batch.column(destination).to_pylist()
                if int(body_id) in eligible
            )
        frontier = discovered.difference(result)
        if len(frontier) > frontier_limit:
            raise RuntimeError(
                f"{direction} hop {hop} reached {len(frontier):,} new neurons; "
                "tighten min_synapse_count or max_hops."
            )
        result.update({body_id: hop for body_id in frontier})
        if not frontier:
            break
    return result


def induced_edges(connectivity: Path, nodes: set[int], minimum: int, batch_rows: int) -> pd.DataFrame:
    """Return thresholded edges fully contained in the final directed-path subgraph."""
    table = feather.read_table(connectivity, memory_map=True)
    node_values = pa.array(sorted(nodes), type=pa.int64())
    outputs: list[pd.DataFrame] = []
    for batch in table.to_batches(max_chunksize=batch_rows):
        keep = pc.and_(
            pc.and_(
                pc.is_in(batch.column("body_pre"), value_set=node_values),
                pc.is_in(batch.column("body_post"), value_set=node_values),
            ),
            pc.greater_equal(batch.column("weight"), pa.scalar(minimum)),
        )
        result = pa.RecordBatch.from_arrays(
            [pc.filter(item, keep) for item in batch.columns], schema=batch.schema
        )
        if result.num_rows:
            outputs.append(result.to_pandas())
    return pd.concat(outputs, ignore_index=True) if outputs else pd.DataFrame(
        columns=["body_pre", "body_post", "weight"]
    )


def extract(connectivity: Path, annotations: pd.DataFrame, input_ids: set[int], output_ids: set[int], options: dict):
    eligible = set(int(value) for value in annotations["bodyId"])
    arguments = dict(
        connectivity=connectivity,
        eligible=eligible,
        max_hops=int(options["max_hops"]),
        minimum=int(options["min_synapse_count"]),
        batch_rows=int(options["batch_rows"]),
        frontier_limit=int(options["max_frontier_nodes"]),
    )
    forward = distances(seeds=input_ids, direction="forward", **arguments)
    backward = distances(seeds=output_ids, direction="reverse", **arguments)
    selected = {
        body_id for body_id in forward.keys() & backward.keys()
        if forward[body_id] + backward[body_id] <= int(options["max_hops"])
    }
    neurons = annotations.loc[sorted(selected)].copy().reset_index(drop=True)
    neurons["input_distance"] = neurons["bodyId"].map(forward)
    neurons["output_distance"] = neurons["bodyId"].map(backward)
    return neurons, induced_edges(connectivity, selected, arguments["minimum"], arguments["batch_rows"]), forward, backward
