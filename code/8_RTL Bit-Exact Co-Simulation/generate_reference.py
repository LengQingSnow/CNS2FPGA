"""Generate flattened full-network CPU reference memories for RTL comparison."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
from reference_stepper import ReferenceStepper


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_mem(path: Path, values, bits: int) -> None:
    digits = (bits + 3) // 4
    mask = (1 << bits) - 1
    with path.open("w", encoding="ascii", newline="\n") as stream:
        for value in values:
            stream.write(f"{int(value) & mask:0{digits}X}\n")


def run(config_path: Path, output_dir: Path | None = None) -> dict:
    config_path = config_path.resolve()
    config = json.loads(config_path.read_text(encoding="utf-8"))
    resolve = lambda value: (config_path.parent / value).resolve()
    compiler = resolve(config["compiler_output"])
    ir = resolve(config["source_ir"])
    golden_path = resolve(config["golden_config"])
    fixed_src = resolve(config["fixed_src"])
    fixed_config_path = resolve(config["fixed_config"])
    sys.path.insert(0, str(fixed_src))
    import cns2fpga_fixed.fixed_lif as fixed_ops
    golden = json.loads(golden_path.read_text(encoding="utf-8"))
    fixed_config = json.loads(fixed_config_path.read_text(encoding="utf-8"))
    fmt = next(item for item in fixed_config["formats"] if item["name"] == config["fixed_format"])
    neurons = pd.read_csv(ir / "neuron_table.csv")
    synapses = pd.read_csv(ir / "synapse_table.csv")
    offsets = pd.read_csv(ir / "offset_table.csv")
    input_indices = neurons.loc[neurons.is_input_anchor.astype(bool), "neuron_index"].to_numpy(np.int64)
    stepper = ReferenceStepper(neurons, synapses, offsets, golden["model"], fmt, fixed_ops)
    output = (output_dir or ROOT / "sim" / "reference" / config["name"]).resolve()
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(f"Refusing to overwrite reference: {output}")
    output.mkdir(parents=True, exist_ok=True)
    snapshots = [stepper.step(float(amplitude), input_indices) for amplitude in config["stimulus"]]
    if any(item["state_saturations"] or item["accumulator_saturations"] for item in snapshots):
        raise RuntimeError("Unexpected saturation in the co-simulation reference")
    write_mem(output / "stimulus.mem", fixed_ops.quantize(config["stimulus"], fmt["state_frac"]), fmt["state_bits"])
    write_mem(output / "expected_voltage.mem", np.concatenate([item["voltage"] for item in snapshots]), fmt["state_bits"])
    write_mem(output / "expected_syn_current.mem", np.concatenate([item["syn_current"] for item in snapshots]), fmt["accumulator_bits"])
    write_mem(output / "expected_refractory.mem", np.concatenate([item["refractory"] for item in snapshots]), 8)
    write_mem(output / "expected_spike.mem", np.concatenate([item["spikes"].astype(np.int8) for item in snapshots]), 1)
    summary = []
    for timestep, item in enumerate(snapshots):
        indices = np.flatnonzero(item["spikes"])
        summary.append({"timestep": timestep, "input_current": config["stimulus"][timestep],
                        "spikes": len(indices), "spike_index_sha256": hashlib.sha256(indices.astype(np.int32).tobytes()).hexdigest(),
                        "max_abs_voltage_integer": int(np.abs(item["voltage"]).max()),
                        "nonzero_syn_current": int(np.count_nonzero(item["syn_current"]))})
    pd.DataFrame(summary).to_csv(output / "reference_summary.csv", index=False)
    tracked = [config_path, golden_path, fixed_config_path,
               ir / "neuron_table.csv", ir / "synapse_table.csv", ir / "offset_table.csv",
               compiler / "protocol_lock.json", compiler / "artifact_sha256.json",
               Path(__file__), ROOT / "src" / "reference_stepper.py", fixed_src / "cns2fpga_fixed" / "fixed_lif.py"]
    manifest = {"schema": "cns2fpga.rtl_reference", "schema_version": 1,
                "neurons": len(neurons), "synapses": len(synapses), "timesteps": len(snapshots),
                "fixed_format": fmt, "flattening": "address=timestep*neurons+neuron_index",
                "input_and_source_sha256": {str(path): sha256(path) for path in tracked}}
    (output / "reference_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    artifacts = {path.name: sha256(path) for path in output.iterdir() if path.is_file() and path.name != "artifact_sha256.json"}
    (output / "artifact_sha256.json").write_text(json.dumps(artifacts, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(output), "timesteps": len(snapshots), "neurons": len(neurons),
                      "total_spikes": int(sum(item["spikes"].sum() for item in snapshots))}, indent=2))
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "configs" / "full_network_8step_v1.json")
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    run(args.config, args.output_dir)


if __name__ == "__main__":
    main()
