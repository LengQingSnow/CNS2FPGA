"""Inspect MaleCNS edges among literature-motivated visual steering anchors."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.feather as feather

ROOT = Path(__file__).resolve().parents[2]
ANNOTATIONS = ROOT / "support" / "body-annotations-male-cns-v1.0-minconf-0.5.feather"
CONNECTIVITY = ROOT / "support" / "connectome-weights-male-cns-v1.0-minconf-0.5.feather"
TYPES = ("LC10a", "AOTU019", "AOTU025", "DNa02")


def main():
    neurons = pd.read_feather(ANNOTATIONS, columns=["bodyId", "type", "superclass"])
    sets = {name: set(neurons.loc[neurons.type == name, "bodyId"].astype("int64")) for name in TYPES}
    membership = {int(body): name for name, values in sets.items() for body in values}
    anchor_ids = pa.array(sorted(membership), type=pa.int64())
    kept = defaultdict(lambda: [0, 0])
    table = feather.read_table(CONNECTIVITY, memory_map=True)
    for batch in table.to_batches(max_chunksize=2_000_000):
        mask = pc.and_(pc.is_in(batch.column("body_pre"), value_set=anchor_ids),
                       pc.is_in(batch.column("body_post"), value_set=anchor_ids))
        selected = batch.filter(mask)
        for pre, post, weight in zip(selected.column("body_pre").to_pylist(),
                                     selected.column("body_post").to_pylist(),
                                     selected.column("weight").to_pylist()):
            if weight < 5:
                continue
            pair = (membership[int(pre)], membership[int(post)])
            kept[pair][0] += 1
            kept[pair][1] += int(weight)
    print("anchor neurons:", {key: len(value) for key, value in sets.items()})
    for pair, (edges, synapses) in sorted(kept.items()):
        print(f"{pair[0]} -> {pair[1]}: edges={edges}, synapses={synapses}")


if __name__ == "__main__":
    main()
