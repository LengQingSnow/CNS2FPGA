import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from run_mal_followup import select_mal_bridge


def test_bridge_requires_both_negative_segments_and_exact_mal_type_family():
    n = pd.DataFrame({"neuron_index": range(6), "type": ["vpn", "mAL_a", "mAL_b", "mALike", "pc", "mAL_c"]})
    s = pd.DataFrame({"pre_index": [0, 0, 0, 0, 1, 2, 3], "post_index": [1, 2, 3, 5, 4, 4, 4],
                      "nt_model_sign": [-1, -1, -1, -1, -1, 0, -1]})
    mal, bridge, masks = select_mal_bridge(n, s, [0], [4], r"^mAL(?:_|$)")
    assert mal.tolist() == [1, 2, 5]
    assert bridge.tolist() == [1]
    np.testing.assert_array_equal(np.flatnonzero(masks["cut_vPN1_to_mAL_bridge"]), [0])
    np.testing.assert_array_equal(np.flatnonzero(masks["cut_mAL_bridge_to_pC1"]), [4])
    assert masks["cut_both_bridge_segments"].sum() == 2
