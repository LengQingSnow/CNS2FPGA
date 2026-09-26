"""Reproducible Step 11 perturbation study for the locked 35-ms song protocol."""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
CODE = ROOT.parent
STEP3 = CODE / "3_CPU Floating-Point Golden Model"
STEP5 = CODE / "5_Fixed-Point Quantization Analysis"
STEP9 = CODE / "9_KU115 FPGA Validation"
STEP10 = CODE / "10_Complete Courtship-Song Circuit Experiment"
OUT = ROOT / "outputs" / "courtship_song_robustness_v2"
BOARD_CAPTURE_SOURCE = ROOT / "outputs" / "courtship_song_robustness_v1"
GROUPS = ("vPN1", "pC1", "pIP10", "pMP2")
LEVELS = (5, 10, 20)
REPLICATES = 5
SEED = 20260925
WINDOW = slice(100, 1968)

sys.path.insert(0, str(STEP3 / "src"))
sys.path.insert(0, str(STEP5 / "src"))
sys.path.insert(0, str(ROOT / "src"))
from cns2fpga_fixed import FixedFormat, FixedLIFNetwork
from perturbation_adapter import simulate_float, simulate_fixed


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def import_file(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def cases():
    yield {"name": "intact", "family": "intact", "level_pct": 0, "replicate": 0, "seed": None}
    for family in ("synapse_deletion", "neuron_failure", "weight_jitter", "input_noise"):
        for level in LEVELS:
            for rep in range(REPLICATES):
                index = ("synapse_deletion", "neuron_failure", "weight_jitter", "input_noise").index(family)
                yield {"name": f"{family}_{level:02d}_r{rep}", "family": family,
                       "level_pct": level, "replicate": rep,
                       "seed": SEED + index * 10000 + level * 100 + rep}
    for target in ("auditory_input", "aPN1", "vPN1", "pIP10"):
        yield {"name": f"ablate_{target}", "family": "ablation", "target": target,
               "level_pct": None, "replicate": 0, "seed": None}


def intervention(case: dict, current: np.ndarray, group_indices: dict, n: int, edges: int):
    family = case["family"]
    parameters = {"external_current": current, "silenced_indices": None,
                  "disabled_edge_indices": None, "weight_multipliers": None}
    artifact = {"selection_sha256": None, "selection_count": 0}
    if family == "intact":
        return parameters, artifact
    if family == "ablation":
        selected = np.asarray(group_indices[case["target"]], dtype=np.int64)
        if not len(selected):
            raise ValueError(f"Empty ablation target {case['target']}")
        parameters["silenced_indices"] = selected
        artifact = {"selection_sha256": hashlib.sha256(selected.tobytes()).hexdigest(),
                    "selection_count": len(selected)}
        return parameters, artifact
    rng = np.random.default_rng(case["seed"])
    level = case["level_pct"] / 100.0
    if family == "synapse_deletion":
        chosen = np.sort(rng.choice(edges, size=round(edges * level), replace=False)).astype(np.int64)
        parameters["disabled_edge_indices"] = chosen
        artifact = {"selection_sha256": hashlib.sha256(chosen.tobytes()).hexdigest(),
                    "selection_count": len(chosen)}
    elif family == "neuron_failure":
        chosen = np.sort(rng.choice(n, size=round(n * level), replace=False)).astype(np.int64)
        parameters["silenced_indices"] = chosen
        artifact = {"selection_sha256": hashlib.sha256(chosen.tobytes()).hexdigest(),
                    "selection_count": len(chosen)}
    elif family == "weight_jitter":
        factors = np.maximum(0.0, 1.0 + rng.normal(0.0, level, edges))
        parameters["weight_multipliers"] = factors
        artifact = {"selection_sha256": hashlib.sha256(factors.tobytes()).hexdigest(),
                    "selection_count": len(factors), "multiplier_mean": float(factors.mean())}
    elif family == "input_noise":
        # One waveform sample per model millisecond, shared by the 93 input neurons.
        waveform = current + rng.normal(0.0, 1.2 * level, len(current))
        parameters["external_current"] = waveform
        artifact = {"selection_sha256": hashlib.sha256(waveform.tobytes()).hexdigest(),
                    "selection_count": len(waveform), "noise_sigma": 1.2 * level}
    else:
        raise ValueError(f"Unknown family: {family}")
    return parameters, artifact


def event_f1(floating, fixed, neurons: int) -> float:
    a = floating.spike_times.astype(np.int64) * neurons + floating.spike_neurons
    b = fixed.spike_times.astype(np.int64) * neurons + fixed.spike_neurons
    if not len(a) and not len(b):
        return 1.0
    common = len(np.intersect1d(a, b, assume_unique=True))
    return 2 * common / (len(a) + len(b))


def setup():
    step10 = import_file("step10_experiment", STEP10 / "run_experiment.py")
    step9 = import_file("step9_host", STEP9 / "host" / "step9_host.py")
    cfg, ir_paths, groups, floating, fixed = step10.network_inputs()
    base_path = STEP10 / "outputs" / "courtship_song_v1" / "cpu" / "ipi_35.npz"
    with np.load(base_path) as archive:
        current = archive["current"].copy()
        expected = {key: archive[key].copy() for key in ("float_spike_times", "float_spike_neurons",
                                                       "fixed_spike_times", "fixed_spike_neurons")}
    if len(current) != 4308 or len(groups["auditory_input"]) != 93:
        raise ValueError("Frozen Step 10 baseline protocol/network changed")
    return step9, cfg, ir_paths, groups, floating, fixed, current, expected, base_path


def prepare(output: Path):
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(f"Refusing to overwrite nonempty study: {output}")
    output.mkdir(parents=True, exist_ok=True)
    (output / "trials").mkdir()
    step9, cfg, ir_paths, groups, floating, fixed, current, expected, base_path = setup()
    trace = np.empty(0, dtype=np.int64)
    source_files = [Path(__file__), STEP3 / "src" / "cns2fpga_golden" / "model.py",
                    STEP5 / "src" / "cns2fpga_fixed" / "fixed_lif.py",
                    ROOT / "src" / "perturbation_adapter.py",
                    STEP10 / "run_experiment.py", base_path,
                    STEP5 / "configs" / "courtship_song_fixed_point_v6_final.json",
                    *ir_paths.values()]
    lock = {"schema": "cns2fpga.step11", "version": 2,
            "baseline": "Step 10, intact 35-ms IPI, 40 pulses at 1.2, 4308 steps",
            "seed": SEED, "replicates": REPLICATES, "levels_pct": LEVELS,
            "response_window_ms": [WINDOW.start, WINDOW.stop],
            "source_sha256": {str(path.relative_to(CODE)): sha(path) for path in source_files},
            "cases": []}
    records = []
    baseline = None
    for i, case in enumerate(cases()):
        parameters, artifact = intervention(case, current, groups, floating.n, len(floating.synapses))
        waveform = parameters["external_current"]
        shared = {key: parameters[key] for key in ("silenced_indices", "disabled_edge_indices", "weight_multipliers")}
        f = simulate_float(floating, waveform, groups["auditory_input"], groups, trace, **shared)
        q = simulate_fixed(fixed, waveform, groups["auditory_input"], groups, **shared)
        if q.state_saturation_events or q.accumulator_saturation_events:
            raise RuntimeError(f"Fixed-point saturation: {case['name']}")
        if case["family"] == "intact":
            if not (np.array_equal(f.spike_times, expected["float_spike_times"]) and
                    np.array_equal(f.spike_neurons, expected["float_spike_neurons"]) and
                    np.array_equal(q.spike_times, expected["fixed_spike_times"]) and
                    np.array_equal(q.spike_neurons, expected["fixed_spike_neurons"])):
                raise RuntimeError("Baseline no longer matches frozen Step 10 events")
            baseline = {group: (int(f.group_activity[group][WINDOW].sum()),
                                int(q.group_activity[group][WINDOW].sum())) for group in GROUPS}
        f1 = event_f1(f, q, floating.n)
        for group in GROUPS:
            f_count = int(f.group_activity[group][WINDOW].sum())
            q_count = int(q.group_activity[group][WINDOW].sum())
            f_base, q_base = baseline[group]
            records.append({**case, "group": group, "float_spikes": f_count, "fixed_spikes": q_count,
                            "float_change_pct": 100 * (f_count - f_base) / max(f_base, 1),
                            "fixed_change_pct": 100 * (q_count - q_base) / max(q_base, 1),
                            "float_degradation_pct": 100 * abs(f_count - f_base) / max(f_base, 1),
                            "fixed_degradation_pct": 100 * abs(q_count - q_base) / max(q_base, 1),
                            "float_fixed_abs_spike_difference": abs(f_count - q_count),
                            "event_f1": f1,
                            "state_saturation_events": q.state_saturation_events,
                            "accumulator_saturation_events": q.accumulator_saturation_events})
        if case["family"] == "input_noise" and case["replicate"] == 0:
            details = {"profile": "step11", "family": "input_noise", "level_pct": case["level_pct"],
                       "replicate": 0, "seed": case["seed"], "noise_sigma": artifact["noise_sigma"],
                       "response_start_ms": WINDOW.start, "response_end_ms": WINDOW.stop}
            step9.write_trial(output / "trials", case["name"], waveform.tolist(), details)
            artifact["fpga_stimulus_mem_sha256"] = sha(output / "trials" / case["name"] / "stimulus.mem")
        lock["cases"].append({**case, **artifact})
        if i % 10 == 0 or case["family"] == "ablation":
            print(f"CPU completed {i + 1}/{1 + 4 * len(LEVELS) * REPLICATES + 4}: {case['name']}", flush=True)
    pd.DataFrame(records).to_csv(output / "condition_metrics.csv", index=False)
    (output / "protocol_lock.json").write_text(json.dumps(lock, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(f"Prepared {len(lock['cases'])} conditions; lock SHA-256 {sha(output / 'protocol_lock.json')}")


def quantization_rows(output: Path) -> pd.DataFrame:
    config = json.loads((STEP5 / "configs" / "courtship_song_fixed_point_v6_final.json").read_text(encoding="utf-8"))
    step10 = import_file("step10_quant", STEP10 / "run_experiment.py")
    _, paths, groups, _, _ = step10.network_inputs()
    neurons = pd.read_csv(paths["neuron_table"])
    synapses = pd.read_csv(paths["synapse_table"])
    offsets = pd.read_csv(paths["offset_table"])
    with np.load(STEP10 / "outputs" / "courtship_song_v1" / "cpu" / "ipi_35.npz") as base:
        current = base["current"].copy()
        ref_times = base["float_spike_times"].copy()
        ref_neurons = base["float_spike_neurons"].copy()
        pC1_reference = int(base["float_pC1"][WINDOW].sum())
    rows = []
    for fmt_value in config["formats"]:
        fmt = FixedFormat.from_dict(fmt_value)
        network = FixedLIFNetwork(neurons, synapses, offsets, step10.network_inputs()[0]["model"], fmt)
        result = network.simulate(current, groups["auditory_input"], groups)
        exact = np.array_equal(result.spike_times, ref_times) and np.array_equal(result.spike_neurons, ref_neurons)
        rows.append({"format_name": fmt.name, "state_bits": fmt.state_bits,
                     "weight_bits": fmt.weight_bits, "weight_frac": fmt.weight_frac,
                     "pC1_spikes": int(result.group_activity["pC1"][WINDOW].sum()),
                     "pC1_error_pct": 100 * abs(int(result.group_activity["pC1"][WINDOW].sum()) - pC1_reference) / pC1_reference,
                     "exact_events": exact,
                     "state_saturation_events": result.state_saturation_events,
                     "accumulator_saturation_events": result.accumulator_saturation_events})
    frame = pd.DataFrame(rows)
    frame.to_csv(output / "quantization_sensitivity.csv", index=False)
    return frame


def analyze(output: Path):
    lock_path = output / "protocol_lock.json"
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    if lock.get("schema") != "cns2fpga.step11" or len(lock["cases"]) != 65:
        raise ValueError("Unexpected Step 11 protocol lock")
    for relative, digest in lock["source_sha256"].items():
        if sha(CODE / relative) != digest:
            raise RuntimeError(f"Source changed since CPU experiment: {relative}")
    metrics = pd.read_csv(output / "condition_metrics.csv")
    if len(metrics) != 65 * len(GROUPS):
        raise ValueError("Incomplete condition metrics")
    board_rows = []
    for level in LEVELS:
        name = f"input_noise_{level:02d}_r0"
        local_capture = output / "captures" / f"{name}_parsed"
        folder = local_capture if local_capture.is_dir() else BOARD_CAPTURE_SOURCE / "captures" / f"{name}_parsed"
        capture = folder / "counts.csv"
        metadata_path = folder / "capture_metadata.json"
        if not capture.is_file() or not metadata_path.is_file():
            raise FileNotFoundError(f"Missing parsed board capture: {folder}")
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        if sha(capture) != metadata["counts_csv_sha256"] or metadata["period_cycles"] != 200000:
            raise RuntimeError(f"Board capture hash/clock mismatch: {name}")
        recorded_stimulus = folder.parent / name / "stimulus.mem"
        trial_stimulus = output / "trials" / name / "stimulus.mem"
        if recorded_stimulus.exists() and sha(recorded_stimulus) != sha(trial_stimulus):
            raise RuntimeError(f"Board stimulus differs from Step 11 v2 trial: {name}")
        previous_trial = BOARD_CAPTURE_SOURCE / "trials" / name / "stimulus.mem"
        if folder.is_relative_to(BOARD_CAPTURE_SOURCE) and sha(previous_trial) != sha(trial_stimulus):
            raise RuntimeError(f"Reused board stimulus differs from Step 11 v2 trial: {name}")
        board = pd.read_csv(capture)
        if len(board) != 4308 or not np.array_equal(board.timestep.to_numpy(), np.arange(4308)):
            raise RuntimeError(f"Incomplete board trial: {name}")
        register_path = folder.parent / name / "registers.csv"
        with register_path.open(newline="", encoding="ascii") as stream:
            registers = {row["name"]: row["hex32"] for row in csv.DictReader(stream)}
        if registers["STATUS"] != "00000002" or int(registers["COMPLETED_STEPS"], 16) != 4308:
            raise RuntimeError(f"Board trial did not complete cleanly: {name}")
        flags = {key: int(board[key].sum()) for key in ("state_saturation", "accumulator_saturation",
                                                    "deadline_miss", "event_overflow")}
        for group in GROUPS:
            cpu = metrics[(metrics.name == name) & (metrics.group == group)].iloc[0]
            count = int(board[group].to_numpy()[WINDOW].sum())
            board_rows.append({"name": name, "level_pct": level, "group": group,
                               "float_spikes": int(cpu.float_spikes), "fixed_spikes": int(cpu.fixed_spikes),
                               "fpga_spikes": count, "fixed_fpga_response_match": count == int(cpu.fixed_spikes),
                               "max_latency_cycles": int(metadata["max_latency_cycles"]),
                               **{f"{key}_steps": value for key, value in flags.items()},
                               "capture_sha256": sha(capture)})
    hardware = pd.DataFrame(board_rows)
    hardware.to_csv(output / "fpga_noise_comparison.csv", index=False)
    quant = quantization_rows(output)
    summary = (metrics[metrics.family.isin(("synapse_deletion", "neuron_failure", "weight_jitter", "input_noise"))]
               .groupby(["family", "level_pct", "group"], as_index=False)
               .agg(float_degradation_mean_pct=("float_degradation_pct", "mean"),
                    float_degradation_sd_pct=("float_degradation_pct", "std"),
                    fixed_degradation_mean_pct=("fixed_degradation_pct", "mean"),
                    fixed_degradation_sd_pct=("fixed_degradation_pct", "std"),
                    float_fixed_max_abs_spike_difference=("float_fixed_abs_spike_difference", "max"),
                    event_f1_mean=("event_f1", "mean")))
    summary.to_csv(output / "degradation_summary.csv", index=False)
    plot(output, metrics, summary, hardware, quant)
    board_match = bool(hardware.fixed_fpga_response_match.all())
    board_flags = int(hardware[[column for column in hardware if column.endswith("_steps")]].sum().sum())
    worst_cpu_error = int(metrics.float_fixed_abs_spike_difference.max())
    report = ["# Step 11 — courtship-song 回路鲁棒性", "",
              "35 ms IPI、40 个 3 ms 脉冲、幅度 1.2；网络与动力学沿用第十步。",
              "随机突触删除、随机神经元失效、权重高斯扰动和输入高斯噪声各用 5/10/20% 三档、每档 5 个预先固定种子。",
              "比例为被删元素比例或噪声标准差相对标称值的比例；全量关键节点消融另列。", "",
              "## 结果", "",
              f"- CPU 执行 {len(lock['cases'])} 条完整 4308-step 试次；浮点/定点响应窗关键群体计数最大绝对差 {worst_cpu_error} spikes。",
              f"- 三条输入噪声试次上板：定点 CPU 与 FPGA 响应窗群组计数 {'全部一致' if board_match else '存在不一致'}；诊断标志合计 {board_flags}。",
              "- 板上捕获来自同一组已完成的噪声试次；复用前逐文件核对 v2 刺激与上板刺激 SHA-256。",
              f"- 上板最慢步 {int(hardware.max_latency_cycles.max())} / 200000 cycles。",
              "- 原始/汇总数据：`condition_metrics.csv`、`degradation_summary.csv`、`fpga_noise_comparison.csv`、`quantization_sensitivity.csv`。",
              "- 图：`degradation_curve.png`、`ablation_response.png`、`quantization_sensitivity.png`、`fpga_noise.png`。", "",
              "## 解释范围", "",
              "性能变化定义为相对完整模型的响应窗 spike 数绝对偏差，并非行为准确率。",
              "当前 CNS9 bitstream 的运行时接口只能更新刺激；突触删除、神经元失效和权重扰动的 FPGA 实现需要重新编译 IR 与 bitstream，本次仅做 CPU 浮点/定点对照。",
              "上板输入噪声为每毫秒一个标量电流值，由 93 个输入神经元共同接收；不表示每个神经元独立噪声。",
              "随机试次仅 5 个重复；图中的标准差是这 5 个样本的描述性波动，不是总体置信区间。",
              "实验 ROI 与 MaleCNS 亚型映射尚待独立生物学证据。", "",
              f"协议锁 SHA-256：`{sha(lock_path)}`。", ""]
    (output / "report.md").write_text("\n".join(report), encoding="utf-8")
    print(f"Step 11 report: {output / 'report.md'}; board_match={board_match}; flags={board_flags}")


def plot(output: Path, metrics: pd.DataFrame, summary: pd.DataFrame, hardware: pd.DataFrame, quant: pd.DataFrame):
    families = ("synapse_deletion", "neuron_failure", "weight_jitter", "input_noise")
    fig, axes = plt.subplots(2, 2, figsize=(11, 8), sharex=True)
    for ax, family in zip(axes.flat, families):
        part = summary[(summary.family == family) & (summary.group == "pC1")].sort_values("level_pct")
        for source, color in (("float", "#4472c4"), ("fixed", "#e69f00")):
            ax.errorbar(part.level_pct, part[f"{source}_degradation_mean_pct"],
                        yerr=part[f"{source}_degradation_sd_pct"], marker="o", capsize=3,
                        color=color, label=source)
        ax.set_title(family.replace("_", " "))
        ax.set_ylabel("pC1 absolute response deviation (%)")
        ax.grid(alpha=.2)
    axes[0, 0].legend()
    for ax in axes[-1]:
        ax.set_xlabel("Perturbation level (%)")
    fig.suptitle("Response deviation from the intact 35-ms IPI circuit (n=5)")
    fig.tight_layout()
    fig.savefig(output / "degradation_curve.png", dpi=190)
    plt.close(fig)

    ablation = metrics[(metrics.family == "ablation") & (metrics.group.isin(("pC1", "pIP10", "pMP2")))]
    fig, axes = plt.subplots(1, 3, figsize=(13, 4))
    for ax, group in zip(axes, ("pC1", "pIP10", "pMP2")):
        part = ablation[ablation.group == group]
        x = np.arange(len(part))
        ax.bar(x - .18, part.float_change_pct, width=.36, label="float")
        ax.bar(x + .18, part.fixed_change_pct, width=.36, label="fixed")
        ax.set_xticks(x, part.target, rotation=35, ha="right")
        ax.set_title(group)
        ax.set_ylabel("Change from intact (%)")
        ax.axhline(0, color="black", linewidth=.6)
    axes[0].legend()
    fig.tight_layout()
    fig.savefig(output / "ablation_response.png", dpi=190)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(9, 4.5))
    x = np.arange(len(quant))
    ax.bar(x, quant.pC1_error_pct, color="#4472c4")
    ax.set_xticks(x, quant.format_name, rotation=20, ha="right")
    ax.set_ylabel("35-ms pC1 response error (%)")
    ax2 = ax.twinx()
    ax2.plot(x, quant.state_saturation_events, color="#c00000", marker="o", label="state saturation")
    ax2.set_ylabel("State saturation events")
    fig.tight_layout()
    fig.savefig(output / "quantization_sensitivity.png", dpi=190)
    plt.close(fig)

    fig, axes = plt.subplots(2, 2, figsize=(10, 7))
    for ax, group in zip(axes.flat, GROUPS):
        part = hardware[hardware.group == group].sort_values("level_pct")
        for source, marker in (("float", "o"), ("fixed", "s"), ("fpga", "x")):
            ax.plot(part.level_pct, part[f"{source}_spikes"], marker=marker, label=source)
        ax.set_title(group)
        ax.set_ylabel("Response spikes")
        ax.grid(alpha=.2)
    axes[0, 0].legend()
    for ax in axes[-1]:
        ax.set_xlabel("Input noise σ / 1.2 (%)")
    fig.tight_layout()
    fig.savefig(output / "fpga_noise.png", dpi=190)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "analyze"))
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()
    if args.command == "prepare":
        prepare(args.output.resolve())
    else:
        analyze(args.output.resolve())


if __name__ == "__main__":
    main()
