"""Diagnostic sweep for choosing a non-silent, non-explosive recurrent gain."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from cns2fpga_golden.analysis import select_groups
from cns2fpga_golden.model import FloatLIFNetwork
from cns2fpga_golden.stimulus import build_conditions


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--gains", nargs="+", type=float, default=[2, 4, 6, 8, 10, 12, 16, 20])
    parser.add_argument("--condition-index", type=int, default=1)
    args = parser.parse_args()
    config_path = args.config.resolve()
    config = json.loads(config_path.read_text(encoding="utf-8"))
    paths = {name: (config_path.parent / value).resolve() for name, value in config["ir"].items()}
    neurons = pd.read_csv(paths["neuron_table"])
    synapses = pd.read_csv(paths["synapse_table"])
    offsets = pd.read_csv(paths["offset_table"])
    groups = select_groups(neurons, config["observations"])
    condition = build_conditions(config["stimulus"], config["model"])[args.condition_index]
    print("gain,total_network_spikes,pC1_spikes,pIP10_spikes,pMP2_spikes")
    for gain in args.gains:
        model_config = dict(config["model"])
        model_config["recurrent_gain"] = gain
        result = FloatLIFNetwork(neurons, synapses, offsets, model_config).simulate(
            condition.current,
            groups["auditory_input"],
            groups,
            np.empty(0, dtype=np.int32),
        )
        print(
            f"{gain:g},{len(result.spike_times)},"
            f"{int(result.group_activity['pC1'].sum())},"
            f"{int(result.group_activity['pIP10'].sum())},"
            f"{int(result.group_activity['pMP2'].sum())}"
        )


if __name__ == "__main__":
    main()
