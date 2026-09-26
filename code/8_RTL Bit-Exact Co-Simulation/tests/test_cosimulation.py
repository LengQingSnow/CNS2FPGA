from pathlib import Path
import json
import sys

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT.parents[1]


def test_modelsim_full_network_is_bit_exact():
    log = (ROOT / "sim" / "bit_exact_transcript.log").read_text(encoding="utf-8", errors="replace")
    assert log.count("PASS timestep=") == 8
    assert "PASS BIT-EXACT full-network timesteps=8 neurons=6279" in log
    assert "Errors: 0, Warnings: 0" in log
    table = pd.read_csv(ROOT / "sim" / "rtl_step_summary.csv")
    assert len(table) == 8
    assert table.mismatches.eq(0).all()
    assert table.rtl_spikes.eq(table.cpu_spikes).all()


def test_generated_reference_events_match_locked_fixed_model():
    config_path = ROOT / "configs" / "full_network_8step_v1.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    resolve = lambda value: (config_path.parent / value).resolve()
    fixed_src = resolve(config["fixed_src"])
    sys.path.insert(0, str(fixed_src))
    from cns2fpga_fixed.fixed_lif import FixedFormat, FixedLIFNetwork
    ir = resolve(config["source_ir"])
    neurons = pd.read_csv(ir / "neuron_table.csv")
    synapses = pd.read_csv(ir / "synapse_table.csv")
    offsets = pd.read_csv(ir / "offset_table.csv")
    golden = json.loads(resolve(config["golden_config"]).read_text(encoding="utf-8"))
    fixed = json.loads(resolve(config["fixed_config"]).read_text(encoding="utf-8"))
    fmt = FixedFormat.from_dict(next(item for item in fixed["formats"] if item["name"] == config["fixed_format"]))
    network = FixedLIFNetwork(neurons, synapses, offsets, golden["model"], fmt)
    inputs = neurons.loc[neurons.is_input_anchor.astype(bool), "neuron_index"].to_numpy(np.int64)
    result = network.simulate(np.asarray(config["stimulus"], np.float64), inputs, {})
    tokens = (ROOT / "sim" / "reference" / config["name"] / "expected_spike.mem").read_text(encoding="ascii").splitlines()
    expected = np.asarray([int(token, 16) for token in tokens], dtype=bool).reshape(len(config["stimulus"]), len(neurons))
    times, indices = np.nonzero(expected)
    np.testing.assert_array_equal(result.spike_times, times.astype(np.int32))
    np.testing.assert_array_equal(result.spike_neurons, indices.astype(np.int32))
