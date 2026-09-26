"""Compile the frozen courtship-song IR into versioned FPGA memory images."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import sys
import time

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from cns2fpga_compiler import Field, RecordLayout, read_mem, write_mem


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")


def boolean_series(series: pd.Series) -> np.ndarray:
    if pd.api.types.is_bool_dtype(series):
        return series.to_numpy(dtype=bool)
    values = series.astype(str).str.strip().str.lower()
    if not values.isin(["true", "false", "1", "0"]).all():
        raise ValueError(f"Invalid boolean values in {series.name}")
    return values.isin(["true", "1"]).to_numpy(dtype=bool)


def sign_code(value: int) -> int:
    return {0: 0, 1: 1, -1: 2}[int(value)]


def make_layouts(config: dict, fmt: dict) -> dict[str, RecordLayout]:
    layouts = config["layouts"]
    state_bits, weight_bits = fmt["state_bits"], fmt["weight_bits"]
    neuron_width = layouts["neuron_param"]["record_bits"]
    return {
        "neuron_param": RecordLayout("neuron_param", neuron_width, [
            Field("threshold", 0, state_bits, True),
            Field("reset", state_bits, state_bits, True),
            Field("decay", 2 * state_bits, fmt["decay_bits"], True),
            Field("refractory_steps", 2 * state_bits + fmt["decay_bits"], 8),
            Field("nt_sign_code", 2 * state_bits + fmt["decay_bits"] + 8, 2),
            Field("is_input", 2 * state_bits + fmt["decay_bits"] + 10, 1),
            Field("is_relay", 2 * state_bits + fmt["decay_bits"] + 11, 1),
            Field("is_output", 2 * state_bits + fmt["decay_bits"] + 12, 1),
        ]),
        "synapse": RecordLayout("synapse", layouts["synapse"]["record_bits"], [
            Field("post_index", 0, layouts["synapse"]["post_index_bits"]),
            Field("weight", layouts["synapse"]["post_index_bits"], weight_bits, True),
        ]),
        "offset": RecordLayout("offset", layouts["offset"]["record_bits"], [
            Field("edge_start", 0, layouts["offset"]["edge_start_bits"]),
            Field("edge_count", layouts["offset"]["edge_start_bits"], layouts["offset"]["edge_count_bits"]),
        ]),
        "type_sign": RecordLayout("type_sign", layouts["type_sign"]["record_bits"], [
            Field("nt_sign_code", 0, 2), Field("is_input", 2, 1), Field("is_relay", 3, 1),
            Field("is_output", 4, 1), Field("is_aPN1", 5, 1), Field("is_vPN1", 6, 1),
            Field("is_pC1", 7, 1), Field("is_pIP10", 8, 1), Field("is_pMP2", 9, 1),
        ]),
        "input_mapping": RecordLayout("input_mapping", layouts["input_mapping"]["record_bits"], [
            Field("neuron_index", 0, layouts["input_mapping"]["neuron_index_bits"]),
        ]),
    }


def run(config_path: Path, output_dir: Path | None = None) -> dict:
    started = time.perf_counter()
    config_path = config_path.resolve()
    config = json.loads(config_path.read_text(encoding="utf-8"))
    if config.get("schema_version") != 1:
        raise ValueError("schema_version=1 is required")
    resolve = lambda value: (config_path.parent / value).resolve()
    ir_dir = resolve(config["source_ir"])
    golden_path = resolve(config["golden_config"])
    fixed_config_path = resolve(config["fixed_config"])
    fixed_result = resolve(config["fixed_result"])
    fixed_config = json.loads(fixed_config_path.read_text(encoding="utf-8"))
    recommendations_path = fixed_result / "recommended_formats.json"
    recommendations = json.loads(recommendations_path.read_text(encoding="utf-8"))
    selected_name = recommendations[config["fixed_format_role"]]
    fmt = next((item for item in fixed_config["formats"] if item["name"] == selected_name), None)
    if fmt is None:
        raise ValueError(f"Recommended format {selected_name!r} is absent from the fixed configuration")
    golden = json.loads(golden_path.read_text(encoding="utf-8"))
    model = golden["model"]
    fixed_src = fixed_config_path.parents[1] / "src"
    sys.path.insert(0, str(fixed_src))
    from cns2fpga_fixed.fixed_lif import quantize, signed_limits

    paths = {name: ir_dir / name for name in ("neuron_table.csv", "synapse_table.csv", "offset_table.csv", "metadata.json")}
    neurons = pd.read_csv(paths["neuron_table.csv"])
    synapses = pd.read_csv(paths["synapse_table.csv"])
    offsets = pd.read_csv(paths["offset_table.csv"])
    source_metadata = json.loads(paths["metadata.json"].read_text(encoding="utf-8"))
    n, e = len(neurons), len(synapses)
    if not np.array_equal(neurons.neuron_index.to_numpy(), np.arange(n)):
        raise ValueError("neuron_index must be contiguous and zero based")
    if len(offsets) != n or int(offsets.edge_count.sum()) != e:
        raise ValueError("CSR offsets do not cover all edges")
    if int(offsets.edge_start.iloc[0]) != 0 or int((offsets.edge_start + offsets.edge_count).iloc[-1]) != e:
        raise ValueError("CSR range endpoints are invalid")
    if not np.array_equal(synapses.pre_index.to_numpy(), np.repeat(np.arange(n), offsets.edge_count.to_numpy())):
        raise ValueError("Synapse rows are not grouped in CSR source order")

    flags = {
        "input": boolean_series(neurons.is_input_anchor),
        "relay": boolean_series(neurons.is_relay_anchor),
        "output": boolean_series(neurons.is_output_anchor),
        "aPN1": neurons.synonyms.fillna("").str.contains("Vaughan 2014: aPN1", regex=False).to_numpy(),
        "vPN1": neurons.synonyms.fillna("").str.contains("Zhou 2015: vPN1", regex=False).to_numpy(),
        "pC1": neurons.type.fillna("").str.match(r"^pC1").to_numpy(),
        "pIP10": neurons.type.fillna("").eq("pIP10").to_numpy(),
        "pMP2": neurons.type.fillna("").eq("pMP2").to_numpy(),
    }
    input_indices = np.flatnonzero(flags["input"]).astype(np.int64)
    layouts = make_layouts(config, fmt)

    threshold_q = int(quantize([model["threshold"]], fmt["state_frac"])[0])
    reset_q = int(quantize([model["reset_voltage"]], fmt["state_frac"])[0])
    decay_q = int(quantize([np.exp(-model["dt_ms"] / model["tau_membrane_ms"])], fmt["decay_frac"])[0])
    refractory_steps = int(round(model["refractory_ms"] / model["dt_ms"]))
    raw_weights = (synapses.synapse_count.to_numpy(np.float64)
                   * synapses.nt_model_sign.to_numpy(np.float64) * float(model["recurrent_gain"]))
    weight_q = quantize(raw_weights, fmt["weight_frac"])
    weight_low, weight_high = signed_limits(fmt["weight_bits"])
    if np.any(weight_q < weight_low) or np.any(weight_q > weight_high):
        raise OverflowError("At least one quantized weight does not fit the selected safe format")

    output = (output_dir or ROOT / "outputs" / config["name"]).resolve()
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(f"Refusing to overwrite compiled image: {output}")
    output.mkdir(parents=True, exist_ok=True)
    source_files = [Path(__file__), *sorted((ROOT / "src" / "cns2fpga_compiler").glob("*.py")),
                    fixed_src / "cns2fpga_fixed" / "fixed_lif.py"]
    input_files = [config_path, golden_path, fixed_config_path, recommendations_path,
                   fixed_result / "protocol_lock.json", fixed_result / "artifact_sha256.json", *paths.values()]
    tracked = {str(path): sha256(path) for path in dict.fromkeys([*source_files, *input_files])}
    lock = {"locked_at_utc": datetime.now(timezone.utc).isoformat(), "config": config,
            "selected_fixed_format": fmt, "input_and_source_sha256": tracked,
            "source_counts": {"neurons": n, "edges": e, "input_neurons": len(input_indices)},
            "layouts": {name: layout.describe() for name, layout in layouts.items()}}
    write_json(output / "protocol_lock.json", lock)
    lock_hash = sha256(output / "protocol_lock.json")
    print(f"Compiler protocol locked: {lock_hash}", flush=True)

    signs = neurons.nt_model_sign.to_numpy(dtype=np.int64)
    neuron_records = (layouts["neuron_param"].pack({"threshold": threshold_q, "reset": reset_q,
        "decay": decay_q, "refractory_steps": refractory_steps, "nt_sign_code": sign_code(signs[index]),
        "is_input": int(flags["input"][index]), "is_relay": int(flags["relay"][index]),
        "is_output": int(flags["output"][index])}) for index in range(n))
    synapse_records = (layouts["synapse"].pack({"post_index": post, "weight": weight})
                        for post, weight in zip(synapses.post_index.to_numpy(np.int64), weight_q))
    offset_records = (layouts["offset"].pack({"edge_start": start, "edge_count": count})
                      for start, count in zip(offsets.edge_start.to_numpy(np.int64), offsets.edge_count.to_numpy(np.int64)))
    type_records = (layouts["type_sign"].pack({"nt_sign_code": sign_code(signs[index]),
        "is_input": int(flags["input"][index]), "is_relay": int(flags["relay"][index]),
        "is_output": int(flags["output"][index]), "is_aPN1": int(flags["aPN1"][index]),
        "is_vPN1": int(flags["vPN1"][index]), "is_pC1": int(flags["pC1"][index]),
        "is_pIP10": int(flags["pIP10"][index]), "is_pMP2": int(flags["pMP2"][index])}) for index in range(n))
    input_records = (layouts["input_mapping"].pack({"neuron_index": index}) for index in input_indices)
    files = {
        "neuron_param.mem": (layouts["neuron_param"], neuron_records),
        "synapse.mem": (layouts["synapse"], synapse_records),
        "offset.mem": (layouts["offset"], offset_records),
        "type_sign.mem": (layouts["type_sign"], type_records),
        "input_mapping.mem": (layouts["input_mapping"], input_records),
    }
    counts = {}
    for filename, (layout, records) in files.items():
        counts[filename] = write_mem(output / filename, records, layout.width)
        print(f"{filename}: {counts[filename]:,} records", flush=True)

    format_word = (fmt["state_bits"] | (fmt["state_frac"] << 8) | (fmt["weight_bits"] << 16)
                   | (fmt["weight_frac"] << 24) | (fmt["decay_bits"] << 32)
                   | (fmt["decay_frac"] << 40) | (fmt["accumulator_bits"] << 48))
    global_words = [int.from_bytes(b"CNS2FPGA", "big"), config["schema_version"], n, e,
                    len(input_indices), int(round(model["dt_ms"] * 1_000_000)), format_word,
                    int(lock_hash[:16], 16)]
    counts["global_config.mem"] = write_mem(output / "global_config.mem", global_words, 64)

    body_map = neurons[["neuron_index", "bodyId", "type", "instance"]].copy()
    for name, values in flags.items():
        body_map[f"is_{name}"] = values
    body_map.to_csv(output / "body_id_map.csv", index=False)
    svh = f"""// Generated by CNS2FPGA compiler; do not edit.
`define CNS2FPGA_SCHEMA_VERSION {config['schema_version']}
`define CNS2FPGA_NEURON_COUNT {n}
`define CNS2FPGA_SYNAPSE_COUNT {e}
`define CNS2FPGA_INPUT_COUNT {len(input_indices)}
`define CNS2FPGA_NEURON_INDEX_BITS {config['layouts']['synapse']['post_index_bits']}
`define CNS2FPGA_STATE_BITS {fmt['state_bits']}
`define CNS2FPGA_STATE_FRAC {fmt['state_frac']}
`define CNS2FPGA_WEIGHT_BITS {fmt['weight_bits']}
`define CNS2FPGA_WEIGHT_FRAC {fmt['weight_frac']}
`define CNS2FPGA_DECAY_BITS {fmt['decay_bits']}
`define CNS2FPGA_DECAY_FRAC {fmt['decay_frac']}
`define CNS2FPGA_ACCUMULATOR_BITS {fmt['accumulator_bits']}
"""
    (output / "cns2fpga_config.svh").write_text(svh, encoding="ascii", newline="\n")

    checks = []
    def add_check(name: str, passed: bool, detail: str) -> None:
        checks.append({"check": name, "status": "PASS" if passed else "FAIL", "detail": detail})
    decoded_neurons = [layouts["neuron_param"].unpack(value) for value in read_mem(output / "neuron_param.mem", layouts["neuron_param"].width)]
    add_check("neuron_record_count", len(decoded_neurons) == n, f"{len(decoded_neurons)} == {n}")
    add_check("neuron_constants_roundtrip", all(item["threshold"] == threshold_q and item["reset"] == reset_q and item["decay"] == decay_q and item["refractory_steps"] == refractory_steps for item in decoded_neurons), "threshold/reset/decay/refractory")
    decoded_synapses = [layouts["synapse"].unpack(value) for value in read_mem(output / "synapse.mem", layouts["synapse"].width)]
    decoded_post = np.fromiter((item["post_index"] for item in decoded_synapses), dtype=np.int64, count=e)
    decoded_weight = np.fromiter((item["weight"] for item in decoded_synapses), dtype=np.int64, count=e)
    add_check("synapse_post_roundtrip", np.array_equal(decoded_post, synapses.post_index.to_numpy(np.int64)), f"{e} post indices")
    add_check("synapse_weight_roundtrip", np.array_equal(decoded_weight, weight_q), f"{e} signed weights")
    decoded_offsets = [layouts["offset"].unpack(value) for value in read_mem(output / "offset.mem", layouts["offset"].width)]
    add_check("offset_roundtrip", all(item["edge_start"] == int(start) and item["edge_count"] == int(count) for item, start, count in zip(decoded_offsets, offsets.edge_start, offsets.edge_count)), f"{n} CSR entries")
    decoded_types = [layouts["type_sign"].unpack(value) for value in read_mem(output / "type_sign.mem", layouts["type_sign"].width)]
    add_check("type_sign_roundtrip", all(item["nt_sign_code"] == sign_code(signs[index]) and item["is_pC1"] == int(flags["pC1"][index]) for index, item in enumerate(decoded_types)), f"{n} sign/pC1 records")
    decoded_inputs = [layouts["input_mapping"].unpack(value)["neuron_index"] for value in read_mem(output / "input_mapping.mem", layouts["input_mapping"].width)]
    add_check("input_mapping_roundtrip", np.array_equal(decoded_inputs, input_indices), f"{len(input_indices)} input indices")
    add_check("source_counts_match_metadata", source_metadata["graph"]["neurons"] == n and source_metadata["graph"]["nonzero_edges"] == e, "step-2 metadata")
    verification = pd.DataFrame(checks)
    verification.to_csv(output / "verification.csv", index=False)
    if not verification.status.eq("PASS").all():
        raise RuntimeError("Compiled image failed round-trip verification")

    bram_bits = int(config["bram36_bits"])
    memory_rows = []
    for filename, records in counts.items():
        width = 64 if filename == "global_config.mem" else files[filename][0].width
        bits = records * width
        memory_rows.append({"file": filename, "records": records, "record_bits": width,
                            "logical_bits": bits, "bram36_if_independent": math.ceil(bits / bram_bits)})
    memory_map = pd.DataFrame(memory_rows)
    memory_map.to_csv(output / "memory_map.csv", index=False)
    logical_bits = int(memory_map.logical_bits.sum())
    aggregate_bram = math.ceil(logical_bits / bram_bits)
    independent_bram = int(memory_map.bram36_if_independent.sum())
    manifest = {"schema": "cns2fpga.hardware_ir", "schema_version": config["schema_version"],
                "name": config["name"], "source_dataset": source_metadata["config"]["dataset"],
                "fixed_format_role": config["fixed_format_role"], "fixed_format_name": selected_name,
                "fixed_format": fmt, "arithmetic": {"signed": True, "rounding": "nearest_ties_away_from_zero", "overflow": "saturate"},
                "counts": {"neurons": n, "synapses": e, "inputs": len(input_indices)},
                "layouts": {name: layout.describe() for name, layout in layouts.items()},
                "files": memory_rows, "logical_bits": logical_bits,
                "aggregate_bram36_equivalent": aggregate_bram,
                "independent_memory_bram36": independent_bram,
                "protocol_lock_sha256": lock_hash}
    write_json(output / "compiler_manifest.json", manifest)
    report = f"""# CNS2FPGA Hardware IR v1 compile report

**PASS：冻结的 courtship-song IR 已编译为可回读的 FPGA 十六进制存储镜像。**

- neurons: {n:,}
- synapses: {e:,}
- input mappings: {len(input_indices):,}
- fixed format: `{selected_name}` (`safe` role)
- logical storage: {logical_bits:,} bits
- BRAM36 aggregate lower bound: {aggregate_bram}
- BRAM36 with each file independently allocated: {independent_bram}
- round-trip checks: {len(checks)}/{len(checks)} PASS

`synapse.mem` 以 CSR source 顺序保存 post index 和二补码权重；pre index 由
`offset.mem` 的 start/count 隐式确定。`.mem` 文件为定宽大写十六进制，每行一条记录。
BRAM 数为逻辑容量估算，不含双口复制、跨宽拼接损耗、事件队列和控制缓冲。

protocol lock: `{lock_hash}`
"""
    (output / "report.md").write_text(report, encoding="utf-8")
    unchanged = all(sha256(Path(path)) == digest for path, digest in tracked.items())
    metadata = {"verdict": "PASS", "schema": "cns2fpga.hardware_ir", "schema_version": 1,
                "fixed_format": selected_name, "neurons": n, "synapses": e,
                "logical_bits": logical_bits, "aggregate_bram36_equivalent": aggregate_bram,
                "independent_memory_bram36": independent_bram, "roundtrip_checks_passed": len(checks),
                "protocol_lock_sha256": lock_hash, "frozen_inputs_unchanged": unchanged,
                "runtime_seconds": time.perf_counter() - started}
    write_json(output / "run_metadata.json", metadata)
    artifacts = {path.name: sha256(path) for path in output.iterdir() if path.is_file() and path.name != "artifact_sha256.json"}
    write_json(output / "artifact_sha256.json", artifacts)
    if not unchanged or sha256(output / "protocol_lock.json") != lock_hash:
        raise RuntimeError("A locked input/source changed during compilation")
    print(json.dumps(metadata, ensure_ascii=False, indent=2), flush=True)
    return metadata


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "configs" / "courtship_song_hw_ir_v1.json")
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    run(args.config, args.output_dir)


if __name__ == "__main__":
    main()
