"""Step 10: locked three-way courtship-song experiment and paper-ready figures."""

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
STEP4 = CODE / "4_Verify whether this model has basic biological plausibility"
STEP5 = CODE / "5_Fixed-Point Quantization Analysis"
STEP9 = CODE / "9_KU115 FPGA Validation"
OUTPUT = ROOT / "outputs" / "courtship_song_v1"
BASE_CAPTURE = STEP9 / "host" / "captures"
GROUPS = ("vPN1", "pC1", "pIP10", "pMP2")
IPIS = (15, 25, 35, 45, 55, 65, 75, 85, 95)
STEPS = 4308

sys.path.insert(0, str(STEP3 / "src"))
sys.path.insert(0, str(STEP5 / "src"))
from cns2fpga_golden.analysis import select_groups
from cns2fpga_golden.model import FloatLIFNetwork
from cns2fpga_fixed import FixedFormat, FixedLIFNetwork


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_step9():
    path = STEP9 / "host" / "step9_host.py"
    spec = importlib.util.spec_from_file_location("step9_host", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def protocol() -> dict:
    return json.loads((STEP4 / "configs" / "courtship_song_equal_pulse_v1.json").read_text(encoding="utf-8"))["protocol"]


def make_cases() -> list[dict]:
    """Use one 4308-step horizon, 40 equal-width pulses, and a fixed response window definition."""
    p = protocol()
    assert p["ipi_ms"] == list(IPIS) and p["pulse_count"] == 40
    assert p["pulse_width_ms"] == 3.0 and p["start_ms"] == 100.0
    assert p["tail_ms"] == 500.0 and p["amplitude"] == 1.2
    cases = []

    def add(name: str, family: str, onsets: list[int], amplitude: float, duration: int = STEPS):
        assert len(onsets) >= 1 and onsets[0] == 100 and all(b > a + 2 for a, b in zip(onsets, onsets[1:]))
        assert onsets[-1] + 3 <= duration <= 8192
        current = np.zeros(duration, dtype=np.float64)
        for onset in onsets:
            current[onset:onset + 3] = amplitude
        end = min(duration, onsets[-1] + 3 + 500)
        cases.append({"name": name, "family": family, "onsets": onsets, "amplitude": amplitude,
                      "duration": duration, "response_start": 100, "response_end": end, "current": current})

    for ipi in IPIS:
        add(f"ipi_{ipi:02d}", "ipi", [100 + i * ipi for i in range(40)], 1.2)
    add("intensity_08", "intensity", [100 + i * 35 for i in range(40)], 0.8)
    add("intensity_14", "intensity", [100 + i * 35 for i in range(40)], 1.4)
    alternating = [100]
    for i in range(39):
        alternating.append(alternating[-1] + (20 if i % 2 == 0 else 50))
    add("alternating_20_50", "pattern", alternating, 1.2)
    add("raster_35_short", "raster", [100 + i * 35 for i in range(8)], 1.2, 350)
    return cases


def network_inputs():
    cfg_path = STEP3 / "configs" / "courtship_song_lif_v0.json"
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    paths = {key: (cfg_path.parent / value).resolve() for key, value in cfg["ir"].items()}
    neurons = pd.read_csv(paths["neuron_table"])
    synapses = pd.read_csv(paths["synapse_table"])
    offsets = pd.read_csv(paths["offset_table"])
    groups = select_groups(neurons, cfg["observations"])
    fmt_cfg = json.loads((STEP5 / "configs" / "courtship_song_fixed_point_v6_final.json").read_text(encoding="utf-8"))
    fmt = FixedFormat.from_dict(next(item for item in fmt_cfg["formats"] if item["name"] == "safe_wf24"))
    return cfg, paths, groups, FloatLIFNetwork(neurons, synapses, offsets, cfg["model"]), FixedLIFNetwork(neurons, synapses, offsets, cfg["model"], fmt)


def prepare(output: Path):
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(f"Refusing to overwrite experiment: {output}")
    output.mkdir(parents=True, exist_ok=True)
    (output / "trials").mkdir()
    (output / "cpu").mkdir()
    step9 = load_step9()
    step9.assert_locked_format()
    cfg, paths, groups, floating, fixed = network_inputs()
    input_indices = groups["auditory_input"]
    trace = np.asarray([int(groups[g][0]) for g in GROUPS if len(groups[g])], dtype=np.int64)
    source_files = [STEP3 / "configs" / "courtship_song_lif_v0.json",
                    STEP4 / "configs" / "courtship_song_equal_pulse_v1.json",
                    STEP5 / "configs" / "courtship_song_fixed_point_v6_final.json",
                    STEP9 / "host" / "step9_host.py", *paths.values()]
    lock = {"schema": "cns2fpga.step10", "version": 1, "model": "unmodified_float_and_safe_wf24",
            "cases": [], "source_sha256": {str(path.relative_to(CODE)): sha(path) for path in source_files}}
    fixed_reference = pd.read_csv(STEP5 / "outputs" / "courtship_song_fixed_point_v6_final" / "population_comparison.csv")
    for case in make_cases():
        name = case["name"]
        current = case["current"]
        # Input must be exactly the values that the FPGA input encoder receives.
        encoded = np.array([step9.quantize_current(v) for v in current], dtype=np.int64)
        f = floating.simulate(current, input_indices, groups, trace)
        q = fixed.simulate(current, input_indices, groups)
        if q.state_saturation_events or q.accumulator_saturation_events:
            raise RuntimeError(f"CPU fixed saturation under {name}")
        if case["family"] == "ipi":
            old = STEP4 / "outputs" / "courtship_song_equal_pulse_v1" / "population_activity" / f"intact_ipi_{int(name[-2:])}.npz"
            with np.load(old) as reference:
                if not np.array_equal(current, reference["input_current"]):
                    raise RuntimeError(f"Step 4 stimulus changed: {name}")
                if not (np.array_equal(f.spike_times, reference["spike_times"]) and
                        np.array_equal(f.spike_neurons, reference["spike_neurons"])):
                    raise RuntimeError(f"Step 4 float reference changed: {name}")
            for group in GROUPS:
                expected = fixed_reference[(fixed_reference.format_name == "safe_wf24") &
                                           (fixed_reference.condition_id == "intact") &
                                           (fixed_reference.ipi_ms == int(name[-2:])) &
                                           (fixed_reference.group == group)].iloc[0]
                count = int(q.group_activity[group][case["response_start"]:case["response_end"]].sum())
                if count != int(expected.fixed_response_spikes):
                    raise RuntimeError(f"Step 5 fixed reference changed: {name}/{group}")
        arrays = {"current": current, "trace_indices": trace, "float_voltage_traces": f.voltage_traces,
                  "float_spike_times": f.spike_times, "float_spike_neurons": f.spike_neurons,
                  "fixed_spike_times": q.spike_times, "fixed_spike_neurons": q.spike_neurons}
        for group in GROUPS:
            arrays[f"float_{group}"] = f.group_activity[group]
            arrays[f"fixed_{group}"] = q.group_activity[group]
        np.savez_compressed(output / "cpu" / f"{name}.npz", **arrays)
        details = {"profile": "step10", "family": case["family"], "amplitude": case["amplitude"],
                   "pulse_count": len(case["onsets"]), "pulse_width_ms": 3,
                   "pulse_onsets_ms": case["onsets"], "response_start_ms": case["response_start"],
                   "response_end_ms": case["response_end"]}
        if case["family"] != "ipi":
            step9.write_trial(output / "trials", name, current.tolist(), details)
        lock["cases"].append({"name": name, "family": case["family"], "amplitude": case["amplitude"],
                              "pulse_count": len(case["onsets"]), "onsets_ms": case["onsets"],
                              "timesteps": case["duration"], "response_window_ms": [case["response_start"], case["response_end"]],
                              "stimulus_sha256": hashlib.sha256(encoded.tobytes()).hexdigest(),
                              "cpu_archive_sha256": sha(output / "cpu" / f"{name}.npz")})
        print(f"CPU PASS: {name}, float={len(f.spike_times)}, fixed={len(q.spike_times)}", flush=True)
    (output / "protocol_lock.json").write_text(json.dumps(lock, indent=2) + "\n", encoding="utf-8")
    print(f"Prepared {len(lock['cases'])} cases; lock SHA-256 {sha(output / 'protocol_lock.json')}")


def captured_counts(output: Path, case: dict) -> tuple[pd.DataFrame, dict, Path]:
    name = case["name"]
    folder = (BASE_CAPTURE / f"{name}_summary_parsed" if case["family"] == "ipi"
              else output / "captures" / f"{name}_parsed")
    path = folder / "counts.csv"
    metadata_path = folder / "capture_metadata.json"
    if not path.is_file() or not metadata_path.is_file():
        raise FileNotFoundError(f"Missing board capture: {folder}")
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    if sha(path) != metadata["counts_csv_sha256"] or metadata["period_cycles"] != 200000:
        raise RuntimeError(f"Board capture checksum/clock mismatch: {name}")
    data = pd.read_csv(path)
    if len(data) != case["timesteps"] or not np.array_equal(data.timestep, np.arange(case["timesteps"])):
        raise RuntimeError(f"Incomplete board capture: {name}")
    return data, metadata, folder


def plot_curves(output: Path, response: pd.DataFrame, activity: pd.DataFrame, events: pd.DataFrame):
    fig, axes = plt.subplots(2, 2, figsize=(11, 7), sharex=True)
    ipi = response[response.family == "ipi"]
    for ax, group in zip(axes.flat, GROUPS):
        rows = ipi[ipi.group == group].sort_values("ipi_ms")
        for source, marker in (("float", "o"), ("fixed", "s"), ("fpga", "x")):
            ax.plot(rows.ipi_ms, rows[f"{source}_spikes_per_pulse"], marker=marker, label=source)
        ax.set_title(group)
        ax.set_ylabel("Response spikes / pulse")
        ax.grid(alpha=.25)
    for ax in axes[-1]:
        ax.set_xlabel("Inter-pulse interval (ms)")
    axes[0, 0].legend()
    fig.suptitle("Courtship-song IPI response: 40 equal pulses; three traces overlap")
    fig.tight_layout()
    fig.savefig(output / "response_curve.png", dpi=190)
    plt.close(fig)

    selected = response[response.family.isin(("intensity", "pattern")) & response.group.isin(("pC1", "pIP10", "pMP2"))]
    baseline = response[(response.case == "ipi_35") & (response.group.isin(("pC1", "pIP10", "pMP2")))].copy()
    selected = pd.concat([baseline, selected])
    fig, axes = plt.subplots(1, 3, figsize=(13, 4), sharey=False)
    for ax, group in zip(axes, ("pC1", "pIP10", "pMP2")):
        rows = selected[selected.group == group]
        x = np.arange(len(rows))
        for shift, source in ((-.25, "float"), (0, "fixed"), (.25, "fpga")):
            ax.bar(x + shift, rows[f"{source}_spikes_per_pulse"], width=.23, label=source)
        ax.set_xticks(x, rows.case, rotation=35, ha="right")
        ax.set_title(group)
        ax.set_ylabel("Response spikes / pulse")
    axes[0].legend()
    fig.suptitle("Input intensity and temporal-pattern controls")
    fig.tight_layout()
    fig.savefig(output / "intensity_pattern.png", dpi=190)
    plt.close(fig)

    fig, axes = plt.subplots(4, 1, figsize=(11, 8), sharex=True)
    signal = activity[activity.case == "ipi_35"]
    for ax, group in zip(axes, GROUPS):
        rows = signal[signal.group == group]
        for source in ("float", "fixed", "fpga"):
            ax.plot(rows.timestep, rows[source], linewidth=.8, label=source)
        ax.set_ylabel(group + " spikes/ms")
        ax.grid(alpha=.2)
    axes[0].legend()
    axes[-1].set_xlabel("Time (ms)")
    fig.suptitle("35-ms IPI population activity")
    fig.tight_layout()
    fig.savefig(output / "key_population_activity.png", dpi=190)
    plt.close(fig)

    fig, axes = plt.subplots(3, 1, figsize=(11, 8), sharex=True, sharey=True)
    colors = {"float": "#4472c4", "fixed": "#e69f00", "fpga": "#2ca02c"}
    for ax, source in zip(axes, ("float", "fixed", "fpga")):
        part = events[events.source == source]
        ax.scatter(part.timestep, part.neuron_index, s=1.1, alpha=.55, color=colors[source])
        ax.set_ylabel(f"{source}\nneuron index")
        ax.text(.98, .92, f"{len(part)} events", transform=ax.transAxes, ha="right", va="top")
    axes[-1].set_xlabel("Time (ms)")
    fig.suptitle("Short 35-ms IPI trial: exact spike raster")
    fig.tight_layout()
    fig.savefig(output / "spike_raster.png", dpi=190)
    plt.close(fig)

    with np.load(output / "cpu" / "raster_35_short.npz") as short:
        indices = short["trace_indices"]
        traces = short["float_voltage_traces"]
    fig, axes = plt.subplots(len(indices), 1, figsize=(11, 8), sharex=True)
    for ax, group, index, volts in zip(axes, GROUPS, indices, traces.T):
        ax.plot(np.arange(len(volts)), volts, color="#4472c4", linewidth=.8, label="float membrane")
        board_spikes = events[(events.source == "fpga") & (events.neuron_index == index)].timestep.to_numpy()
        ax.vlines(board_spikes, 1.0, 1.17, color="#2ca02c", linewidth=1, label="FPGA spike")
        ax.axhline(1.0, color="grey", linewidth=.6, linestyle="--")
        ax.set_ylabel(f"{group}\n#{index}")
        ax.set_ylim(min(-.05, float(np.min(volts)) - .05), max(1.2, float(np.max(volts)) + .05))
    axes[0].legend(loc="upper right")
    axes[-1].set_xlabel("Time (ms)")
    fig.suptitle("Representative neurons: float voltage and FPGA spike times")
    fig.tight_layout()
    fig.savefig(output / "key_neuron_activity.png", dpi=190)
    plt.close(fig)


def analyze(output: Path):
    lock_path = output / "protocol_lock.json"
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    if lock.get("schema") != "cns2fpga.step10" or len(lock["cases"]) != 13:
        raise ValueError("Invalid Step 10 protocol lock")
    for relative, digest in lock["source_sha256"].items():
        if sha(CODE / relative) != digest:
            raise RuntimeError(f"Frozen source changed: {relative}")
    responses, activities, event_rows, hardware = [], [], [], []
    for case in lock["cases"]:
        name = case["name"]
        cpu_path = output / "cpu" / f"{name}.npz"
        if sha(cpu_path) != case["cpu_archive_sha256"]:
            raise RuntimeError(f"CPU archive changed: {name}")
        board, meta, folder = captured_counts(output, case)
        status_path = (BASE_CAPTURE / f"{name}_summary" / "registers.csv" if case["family"] == "ipi"
                       else output / "captures" / name / "registers.csv")
        with status_path.open(newline="", encoding="ascii") as stream:
            registers = {row["name"]: row["hex32"] for row in csv.DictReader(stream)}
        if registers["STATUS"] != "00000002" or int(registers["COMPLETED_STEPS"], 16) != case["timesteps"]:
            raise RuntimeError(f"Board trial not cleanly completed: {name}")
        flags = ["state_saturation", "accumulator_saturation", "deadline_miss", "event_overflow"]
        if int(board[flags].to_numpy().sum()) != 0:
            raise RuntimeError(f"Board diagnostic flags set: {name}")
        if meta["max_latency_cycles"] >= 200000:
            raise RuntimeError(f"Board deadline exceeded: {name}")
        hardware.append({"case": name, "timesteps": len(board), "max_latency_cycles": meta["max_latency_cycles"],
                         "max_latency_us": meta["max_latency_cycles"] / 200,
                         "mean_latency_us": float(board.cycles.mean()) / 200,
                         "deadline_margin_cycles": 200000 - meta["max_latency_cycles"],
                         "total_synops": int(board.synops.sum()),
                         "compute_synops_per_s": float(board.synops.sum()) * 200_000_000 / int(board.cycles.sum()),
                         "real_time_synops_per_s": float(board.synops.sum()) * 1000 / len(board),
                         "max_synops_per_step": int(board.synops.max()),
                         "capture_sha256": sha(folder / "counts.csv")})
        with np.load(cpu_path) as cpu:
            if not (np.array_equal(cpu["float_spike_times"], cpu["fixed_spike_times"]) and
                    np.array_equal(cpu["float_spike_neurons"], cpu["fixed_spike_neurons"])):
                raise RuntimeError(f"Float/fixed event sequence differs: {name}")
            window = slice(*case["response_window_ms"])
            ipi = int(name[-2:]) if case["family"] == "ipi" else ""
            for group in GROUPS:
                float_series, fixed_series = cpu[f"float_{group}"], cpu[f"fixed_{group}"]
                fpga_series = board[group].to_numpy(dtype=np.int64)
                if not np.array_equal(fixed_series, fpga_series):
                    mismatch = int(np.flatnonzero(fixed_series != fpga_series)[0])
                    raise RuntimeError(f"Fixed/FPGA mismatch: {name}/{group} step {mismatch}")
                row = {"case": name, "family": case["family"], "ipi_ms": ipi,
                       "amplitude": case["amplitude"], "group": group,
                       "pulse_count": case["pulse_count"], "response_start_ms": window.start,
                       "response_end_ms": window.stop}
                for source, series in (("float", float_series), ("fixed", fixed_series), ("fpga", fpga_series)):
                    count = int(series[window].sum())
                    row[f"{source}_response_spikes"] = count
                    row[f"{source}_spikes_per_pulse"] = count / case["pulse_count"]
                row["float_fixed_abs_error_spikes"] = abs(row["float_response_spikes"] - row["fixed_response_spikes"])
                row["fixed_fpga_exact_per_timestep"] = True
                responses.append(row)
                if name == "ipi_35":
                    activities.extend({"case": name, "timestep": i, "group": group,
                                       "float": int(float_series[i]), "fixed": int(fixed_series[i]),
                                       "fpga": int(fpga_series[i])} for i in range(len(fpga_series)))
            if case["family"] == "raster":
                events_path = folder / "events.csv"
                if not events_path.is_file():
                    raise FileNotFoundError(events_path)
                actual = pd.read_csv(events_path)
                expected = pd.DataFrame({"timestep": cpu["fixed_spike_times"], "neuron_index": cpu["fixed_spike_neurons"]})
                if not np.array_equal(actual[["timestep", "neuron_index"]].to_numpy(), expected.to_numpy()):
                    raise RuntimeError("Short trial FPGA event raster differs from fixed CPU event sequence")
                for source, times, neurons in (("float", cpu["float_spike_times"], cpu["float_spike_neurons"]),
                                               ("fixed", cpu["fixed_spike_times"], cpu["fixed_spike_neurons"]),
                                               ("fpga", actual.timestep.to_numpy(), actual.neuron_index.to_numpy())):
                    event_rows.extend({"source": source, "timestep": int(t), "neuron_index": int(n)}
                                      for t, n in zip(times, neurons))
        print(f"Three-way PASS: {name}, max latency {meta['max_latency_cycles']} cycles", flush=True)
    response = pd.DataFrame(responses)
    activity = pd.DataFrame(activities)
    events = pd.DataFrame(event_rows)
    hw = pd.DataFrame(hardware)
    response.to_csv(output / "response_comparison.csv", index=False)
    activity.to_csv(output / "key_population_activity.csv", index=False)
    events.to_csv(output / "short_spike_raster.csv", index=False)
    hw.to_csv(output / "latency_throughput.csv", index=False)
    plot_curves(output, response, activity, events)
    status = dict(line.strip().split("=", 1) for line in (STEP9 / "reports" / "axku115_jtag_200mhz" / "final_status.txt").read_text().splitlines() if "=" in line)
    bitstream = STEP9 / "build" / "axku115_jtag_200mhz" / "cns2fpga_axku115_jtag_200mhz.bit"
    resources = {"clock_mhz": 200, "lut": None, "ff": None, "ramb36e2": 589, "ramb18e2": 3,
                 "dsp48e2": 4, "setup_wns_ns": float(status["wns_ns"]), "hold_whs_ns": float(status["whs_ns"]),
                 "setup_user_uncertainty_ns": float(status["setup_user_uncertainty_ns"]),
                 "hold_user_uncertainty_ns": float(status["hold_user_uncertainty_ns"]),
                 "bitstream_sha256": sha(bitstream)}
    util_text = (STEP9 / "reports" / "axku115_jtag_200mhz" / "post_route_utilization.rpt").read_text(errors="replace")
    import re
    for key, label in (("lut", "CLB LUTs"), ("ff", "CLB Registers")):
        match = re.search(r"^\|\s*" + re.escape(label) + r"\s*\|\s*([\d,]+)\s*\|", util_text, re.M)
        if match:
            resources[key] = int(match.group(1).replace(",", ""))
    (output / "resource_timing.json").write_text(json.dumps(resources, indent=2) + "\n", encoding="utf-8")
    max_error = int(response.float_fixed_abs_error_spikes.max())
    report = ["# Step 10 — Courtship-song 完整实验", "",
              "本实验保持 MaleCNS 子图、浮点模型、safe_wf24 定点模型与 FPGA bitstream 不变；新条件只改变输入刺激。",
              "长试次在 FPGA 上比较逐毫秒群组计数，短试次比较完整逐神经元事件顺序。", "",
              "## 结果", "",
              f"- {len(lock['cases'])} 个条件：9 个 IPI、2 个强度、1 个交替间隔模式、1 个短 raster。",
              "- 所有条件的 FPGA 与定点 CPU 群组计数逐毫秒一致；短试次的事件顺序完全一致。",
              "- 13 个条件的浮点与定点 CPU 逐神经元事件序列也完全一致。",
              f"- 浮点与定点响应窗群组计数最大绝对差：{max_error} spikes。",
              f"- 最慢板上 timestep：{int(hw.max_latency_cycles.max())} cycles（{hw.max_latency_us.max():.3f} µs），距 1 ms 截止线 {int(hw.deadline_margin_cycles.min())} cycles。",
              f"- 物理签核：WNS {resources['setup_wns_ns']:+.3f} ns，WHS {resources['hold_whs_ns']:+.3f} ns；setup/hold 额外裕量分别 0.200/0.050 ns。",
              f"- 资源：LUT {resources['lut']}，FF {resources['ff']}，BRAM36 {resources['ramb36e2']}，BRAM18 {resources['ramb18e2']}，DSP {resources['dsp48e2']}。", "",
              "## 图表与数据", "",
              "- `response_curve.png`：9 IPI 的三端 response 曲线。",
              "- `intensity_pattern.png`：输入强度和交替间隔对照。",
              "- `spike_raster.png`：短试次的三端事件散点图。",
              "- `key_neuron_activity.png`：代表性神经元浮点膜电位及板上 spike 时刻。",
              "- `key_population_activity.png`：35-ms IPI 的关键群体活动。",
              "- `response_comparison.csv`、`latency_throughput.csv`、`resource_timing.json`：机器可读数据。", "",
              "## 解释边界", "",
              "这证明 FPGA 对锁定计算模型的保真度，不把三端一致解释成实验果蝇神经活动的真实性。pC1 实验 ROI 与 MaleCNS 亚型映射仍是第四步记录的开放问题。",
              "长试次受事件 BRAM 容量限制，没有导出逐神经元全量 raster；相应结论只针对逐毫秒群组计数。",
              "本阶段没有板级功耗仪读数，不报告实测功耗。",
              "交替 20/50 ms 条件有 39 个间隔，最后一个脉冲比匀速 35 ms 早 15 ms；它是模式扰动示例，不是末脉冲时间严格配平的因果对照。",
              "响应窗计数可能受脉冲时序和观察窗长度影响；跨条件比较图按每脉冲归一化，不称其为钙成像读数或行为输出。", "",
              f"协议锁 SHA-256：`{sha(lock_path)}`；bitstream SHA-256：`{resources['bitstream_sha256']}`。", ""]
    table = ["## 响应与硬件测量表", "",
             "下表的 pC1 值为响应窗 spike 数；SynOps/s 是 `总突触操作数 / 实际核心执行周期 × 200 MHz`，不含 JTAG 传输。", "",
             "| 条件 | pC1 float | pC1 fixed | pC1 FPGA | 最慢步 (µs) | 核心 SynOps/s |",
             "| --- | ---: | ---: | ---: | ---: | ---: |"]
    for row in hw.itertuples(index=False):
        p = response[(response.case == row.case) & (response.group == "pC1")].iloc[0]
        table.append(f"| {row.case} | {p.float_response_spikes} | {p.fixed_response_spikes} | {p.fpga_response_spikes} | {row.max_latency_us:.3f} | {row.compute_synops_per_s:,.0f} |")
    table += ["", "| 频率 | LUT | FF | BRAM36 | BRAM18 | DSP | setup WNS | hold WHS |",
              "| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
              f"| 200 MHz | {resources['lut']} | {resources['ff']} | 589 | 3 | 4 | {resources['setup_wns_ns']:+.3f} ns | {resources['hold_whs_ns']:+.3f} ns |", ""]
    report[report.index("## 图表与数据"):report.index("## 图表与数据")] = table
    (output / "report.md").write_text("\n".join(report), encoding="utf-8")
    print("PASS: " + str(output / "report.md"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "analyze"))
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    if args.command == "prepare":
        prepare(args.output.resolve())
    else:
        analyze(args.output.resolve())


if __name__ == "__main__":
    main()
