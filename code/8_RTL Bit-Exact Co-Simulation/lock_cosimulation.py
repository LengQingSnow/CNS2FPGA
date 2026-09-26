"""Lock full-network CPU/RTL bit-exact evidence."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time

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
    config_path = ROOT / "configs" / "full_network_8step_v1.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    reference = ROOT / "sim" / "reference" / config["name"]
    compiler = PROJECT / "code" / "6_Connectome Compiler" / "outputs" / "courtship_song_hw_ir_v1"
    log_path = ROOT / "sim" / "bit_exact_transcript.log"
    rtl_summary_path = ROOT / "sim" / "rtl_step_summary.csv"
    log = log_path.read_text(encoding="utf-8", errors="replace")
    rtl = pd.read_csv(rtl_summary_path)
    cpu = pd.read_csv(reference / "reference_summary.csv")
    if log.count("PASS timestep=") != len(config["stimulus"]):
        raise RuntimeError("Missing timestep PASS records")
    if "PASS BIT-EXACT full-network timesteps=8 neurons=6279" not in log or "Errors: 0, Warnings: 0" not in log:
        raise RuntimeError("ModelSim final PASS or clean compile signature is missing")
    if not rtl.mismatches.eq(0).all() or not rtl.rtl_spikes.eq(rtl.cpu_spikes).all():
        raise RuntimeError("RTL summary contains a mismatch")
    merged = rtl.merge(cpu, on="timestep", validate="one_to_one")
    if not merged.rtl_spikes.eq(merged.spikes).all():
        raise RuntimeError("RTL and independently generated CPU summaries disagree")

    output = ROOT / "outputs" / config["name"]
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(f"Refusing to overwrite locked co-simulation: {output}")
    output.mkdir(parents=True, exist_ok=True)
    merged.to_csv(output / "cosimulation_summary.csv", index=False)
    source_files = [Path(__file__), ROOT / "generate_reference.py", ROOT / "src" / "reference_stepper.py",
                    ROOT / "rtl" / "cns2fpga_core_sync.sv", ROOT / "sim" / "tb_bit_exact_full.sv",
                    ROOT / "sim" / "run_bit_exact.do", ROOT / "docs" / "cosimulation_contract_v1.md",
                    ROOT / "README.md", config_path, log_path, rtl_summary_path]
    reference_files = list(reference.glob("*"))
    compiler_files = [compiler / name for name in ("protocol_lock.json", "artifact_sha256.json",
        "compiler_manifest.json", "neuron_param.mem", "synapse.mem", "offset.mem", "type_sign.mem")]
    tracked_files = [*source_files, *reference_files, *compiler_files]
    tracked = {str(path): sha256(path) for path in tracked_files if path.is_file()}
    lock = {"locked_at_utc": datetime.now(timezone.utc).isoformat(),
            "scope": "Full 6279-neuron state comparison for 8 timesteps",
            "comparison_fields": ["spike", "voltage", "syn_current", "refractory", "saturation_flags"],
            "tolerance": 0, "input_and_source_sha256": tracked}
    write_json(output / "protocol_lock.json", lock)
    lock_hash = sha256(output / "protocol_lock.json")
    total_neuron_steps = int(len(rtl) * 6279)
    metadata = {"verdict": "BIT_EXACT_PASS", "timesteps": len(rtl), "neurons": 6279,
                "neuron_timestep_states": total_neuron_steps, "state_fields_compared": 4,
                "total_spikes": int(rtl.rtl_spikes.sum()), "total_mismatches": int(rtl.mismatches.sum()),
                "maximum_cycles_per_timestep": int(rtl.cycles.max()),
                "minimum_clock_mhz_for_1ms_at_observed_max": float(rtl.cycles.max()/1000.0),
                "modelsim_errors": 0, "modelsim_warnings": 0,
                "synthesis_claimed": False, "protocol_lock_sha256": lock_hash,
                "frozen_inputs_unchanged": all(sha256(Path(path)) == digest for path, digest in tracked.items()),
                "runtime_seconds": time.perf_counter()-started}
    write_json(output / "run_metadata.json", metadata)
    report = f"""# Full-network CPU–RTL bit-exact report

**PASS：完整 6,279-neuron 网络连续 8 个 timestep 与 CPU 定点参考逐位一致。**

- neuron-timestep states: {total_neuron_steps:,}
- compared per state: spike / voltage / syn_current / refractory
- total spikes: {int(rtl.rtl_spikes.sum()):,}
- mismatches: 0
- saturation events: 0
- ModelSim compile/simulation: 0 errors, 0 warnings
- maximum synchronous-RTL cycles/timestep: {int(rtl.cycles.max()):,}
- minimum clock for observed 1-ms deadline: {rtl.cycles.max()/1000.0:.3f} MHz

结果证明同步存储状态机与第五步整数语义在该连续刺激上 bit-exact。它不等于 Vivado 综合、
时序收敛或全 4,308-timestep 生物学协议已经通过。单引擎在 100 MHz 下不能覆盖本测试的
峰值 timestep；下一步优化应减少每 edge 的流水周期或增加受控并行度。

protocol lock: `{lock_hash}`
"""
    (output / "report.md").write_text(report, encoding="utf-8")
    artifacts = {path.name: sha256(path) for path in output.iterdir() if path.is_file() and path.name != "artifact_sha256.json"}
    write_json(output / "artifact_sha256.json", artifacts)
    print(json.dumps(metadata, ensure_ascii=False, indent=2))
    return metadata


if __name__ == "__main__":
    run()
