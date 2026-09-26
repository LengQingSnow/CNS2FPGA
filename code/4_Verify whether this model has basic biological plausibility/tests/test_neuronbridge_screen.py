import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from cns2fpga_plausibility.neuronbridge_screen import explicit_male_pc1_hits, is_explicit_pc1, summarise_hits


def test_pc1_filter_excludes_lpc1_and_requires_malecns():
    assert is_explicit_pc1("pC1x_b")
    assert is_explicit_pc1("pC1_4a")
    assert not is_explicit_pc1("LPC1")
    assert not is_explicit_pc1("LLPC1")
    rows = pd.DataFrame({
        "Neuron ID": ["male-cns:v0.9:1", "male-cns:v0.9:2", "hemibrain:v1.2.1:3"],
        "Neuron Type": ["pC1x_b", "LPC1", "pC1a"],
        "Number": [4, 5, 6], "Score": [1.0, 2.0, 3.0], "Matched Pixels": [7, 8, 9],
        "source_file": ["a.csv", "a.csv", "a.csv"],
    })
    hits = explicit_male_pc1_hits(rows)
    assert hits.bodyId.tolist() == [1]


def test_summary_preserves_observations_and_reports_ir_membership():
    hits = pd.DataFrame({
        "bodyId": [1, 1], "source_file": ["a.csv", "b.csv"], "Number": [3, 2],
        "Score": [10.0, 20.0], "Matched Pixels": [4, 5],
    })
    annotations = pd.DataFrame({
        "bodyId": [1], "type": ["pC1x_b"], "instance": ["pC1x_b_L"], "somaSide": ["L"],
        "synonyms": ["pC1"], "fruDsx": ["dsx_high"], "status": ["Traced"],
    })
    frozen = pd.DataFrame({"bodyId": [2], "neuron_index": [0]})
    observed, summary = summarise_hits(hits, annotations, frozen)
    assert len(observed) == 2
    assert summary.loc[0, "explicit_hit_count"] == 2
    assert not summary.loc[0, "in_frozen_ir"]
    assert summary.loc[0, "best_explicit_rank"] == 2
