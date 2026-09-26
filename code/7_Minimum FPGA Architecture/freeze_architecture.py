"""Lock step-7 RTL evidence and estimate event-driven cycle demand."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parents[1]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")


def run() -> dict:
    started = time.perf_counter()
    output = ROOT / "outputs" / "minimum_architecture_v1"
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(f"Refusing to overwrite locked architecture evidence: {output}")
    output.mkdir(parents=True, exist_ok=True)
    compiler_output = PROJECT / "code" / "6_Connectome Compiler" / "outputs" / "courtship_song_hw_ir_v1"
    v1_output = PROJECT / "code" / "4_Verify whether this model has basic biological plausibility" / "outputs" / "courtship_song_equal_pulse_v1"
    offsets_path = PROJECT / "code" / "2_Subcircuit Automatic Extraction Tool" / "outputs" / "courtship_song_v0" / "offset_table.csv"
    rtl_files = sorted((ROOT / "rtl").glob("*.sv"))
    sim_files = sorted((ROOT / "sim").glob("*.sv")) + sorted((ROOT / "sim").glob("*.do"))
    fixture_files = sorted((ROOT / "sim" / "fixtures").rglob("*.mem"))
    evidence_files = [ROOT / "sim" / "transcript.log", ROOT / "sim" / "full_image_load.log"]
    compiler_files = [compiler_output / name for name in (
        "protocol_lock.json", "artifact_sha256.json", "compiler_manifest.json",
        "neuron_param.mem", "synapse.mem", "offset.mem", "type_sign.mem")]
    archives = sorted((v1_output / "population_activity").glob("intact_ipi_*.npz"))
    tracked_files = [Path(__file__), ROOT / "README.md", ROOT / "docs" / "architecture_v1.md",
                     offsets_path, *rtl_files, *sim_files, *fixture_files, *evidence_files,
                     *compiler_files, *archives]
    tracked = {str(path): sha256(path) for path in tracked_files}
    transcript = evidence_files[0].read_text(encoding="utf-8", errors="replace")
    full_log = evidence_files[1].read_text(encoding="utf-8", errors="replace")
    smoke_pass = "PASS two-neuron one-cycle propagation" in transcript and "Errors: 0, Warnings: 0" in transcript
    full_load_pass = "PASS full image load neurons=6279 synapses=350185 inputs=93 pC1=112" in full_log and "Errors: 0, Warnings: 0" in full_log
    if not smoke_pass or not full_load_pass:
        raise RuntimeError("ModelSim evidence does not contain both clean PASS signatures")

    offsets = pd.read_csv(offsets_path)
    fanout = offsets.edge_count.to_numpy(dtype=np.int64)
    n = len(offsets)
    cycle_rows = []
    maxima = []
    for archive in archives:
        with np.load(archive) as data:
            times = data["spike_times"].astype(np.int64)
            neurons = data["spike_neurons"].astype(np.int64)
            duration = len(data["input_current"])
        spikes_per_step = np.bincount(times, minlength=duration)
        traversed_edges = np.bincount(times, weights=fanout[neurons], minlength=duration)
        cycles = n + 2 * spikes_per_step + traversed_edges
        ipi = float(archive.stem.split("_ipi_")[-1])
        maximum = int(cycles.max())
        maxima.append(maximum)
        cycle_rows.append({"ipi_ms": ipi, "timesteps": duration,
                           "mean_cycles": float(cycles.mean()), "p99_cycles": float(np.percentile(cycles, 99)),
                           "max_cycles": maximum, "required_mhz_for_1ms_at_max": maximum / 1000.0,
                           "mean_spikes_per_timestep": float(spikes_per_step.mean()),
                           "max_spikes_per_timestep": int(spikes_per_step.max()),
                           "max_traversed_edges_per_timestep": int(traversed_edges.max())})
    cycles = pd.DataFrame(cycle_rows).sort_values("ipi_ms")
    cycles.to_csv(output / "cycle_estimate.csv", index=False)
    manifest = json.loads((compiler_output / "compiler_manifest.json").read_text(encoding="utf-8"))
    theoretical_max_cycles = n + 2*n + int(manifest["counts"]["synapses"])
    lock = {"locked_at_utc": datetime.now(timezone.utc).isoformat(),
            "architecture": {"name": "minimum_architecture_v1", "execution": "single_engine_event_driven",
                "memory": "on_chip_only", "ddr": False, "model_timestep_ms": 1.0,
                "cycle_model": "N_neuron + 2*N_spike + N_traversed_edge",
                "synthesis_claimed": False,
                "synthesis_boundary": "Direct array access is a functional reference; explicit synchronous BRAM latency is a step-8 gate."},
            "compiler_protocol_lock": manifest["protocol_lock_sha256"],
            "input_and_source_sha256": tracked}
    write_json(output / "protocol_lock.json", lock)
    lock_hash = sha256(output / "protocol_lock.json")
    summary = {"verdict": "FUNCTIONAL_ARCHITECTURE_PASS", "modelsim_smoke_pass": smoke_pass,
               "full_image_load_pass": full_load_pass, "neurons": n,
               "synapses": int(manifest["counts"]["synapses"]),
               "maximum_observed_cycles_per_timestep": max(maxima),
               "minimum_clock_mhz_for_observed_1ms_deadline": max(maxima)/1000.0,
               "theoretical_all_spike_cycles": theoretical_max_cycles,
               "theoretical_all_spike_clock_mhz_for_1ms": theoretical_max_cycles/1000.0,
               "synthesis_claimed": False, "protocol_lock_sha256": lock_hash,
               "frozen_inputs_unchanged": all(sha256(Path(path)) == digest for path, digest in tracked.items()),
               "runtime_seconds": time.perf_counter()-started}
    write_json(output / "run_metadata.json", summary)
    report = f"""# Minimum FPGA Architecture v1 report

**FUNCTIONAL PASS：单引擎 RTL 的一周期突触传播和完整第六步镜像加载均通过 ModelSim。**

- two-neuron propagation: PASS
- full image load: PASS (6,279 neurons / 350,185 synapses / 93 inputs / 112 pC1)
- DDR: disabled; on-chip memory image only
- maximum observed cycle estimate: {max(maxima):,} cycles/timestep
- minimum clock for observed 1-ms deadline: {max(maxima)/1000.0:.3f} MHz
- theoretical all-neuron/all-edge bound: {theoretical_max_cycles:,} cycles/timestep ({theoretical_max_cycles/1000.0:.3f} MHz)

周期估算来自 9 个锁定 intact IPI 事件档案。它是单引擎算法周期数，不包含同步 BRAM
新增流水级、主机接口和时钟收敛裕量。当前没有宣称综合通过或板上实时；第八步必须显式加入
同步 BRAM 延迟并与 CPU 定点模型逐周期对拍。

protocol lock: `{lock_hash}`
"""
    (output / "report.md").write_text(report, encoding="utf-8")
    artifacts = {path.name: sha256(path) for path in output.iterdir() if path.is_file() and path.name != "artifact_sha256.json"}
    write_json(output / "artifact_sha256.json", artifacts)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return summary


if __name__ == "__main__":
    run()
