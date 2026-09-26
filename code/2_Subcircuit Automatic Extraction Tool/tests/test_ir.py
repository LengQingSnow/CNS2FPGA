"""Small in-memory checks for the deterministic CSR export."""

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from cns2fpga_extractor.ir import NT_SIGN, build_ir


def test_csr_offsets_match_sorted_edges():
    neurons = pd.DataFrame({"bodyId": [30, 10, 20], "nt_model_sign": [0, 1, -1]})
    edges = pd.DataFrame({"body_pre": [30, 10, 10], "body_post": [10, 20, 30], "weight": [2, 4, 3]})
    indexed, synapses, offsets = build_ir(neurons, edges)
    assert indexed.bodyId.tolist() == [10, 20, 30]
    assert synapses.pre_index.tolist() == [0, 0, 2]
    assert offsets.edge_start.tolist() == [0, 2, 2]
    assert offsets.edge_count.tolist() == [2, 0, 1]


def test_published_lif_transmitter_sign_convention():
    assert NT_SIGN == {"acetylcholine": 1, "gaba": -1, "glutamate": -1}
