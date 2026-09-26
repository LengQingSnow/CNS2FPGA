"""Audit and intervene on the literature-motivated vPN1 -| mAL -| pC1 motif."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from run_mechanism_diagnostics import sha256, write_json, verify
from cns2fpga_plausibility.diagnostics_v2 import cut_edges, population_counts
from cns2fpga_plausibility.protocol import build_equal_pulse_conditions, summarize_activity
from cns2fpga_plausibility.reporting_v2 import table


def select_mal_bridge(neurons, synapses, vpn, pc, regex):
    mal = neurons.loc[neurons.type.fillna("").str.match(regex), "neuron_index"].to_numpy(np.int32)
    incoming = synapses.pre_index.isin(vpn) & synapses.post_index.isin(mal) & synapses.nt_model_sign.lt(0)
    outgoing = synapses.pre_index.isin(mal) & synapses.post_index.isin(pc) & synapses.nt_model_sign.lt(0)
    bridge = np.intersect1d(synapses.loc[incoming, "post_index"], synapses.loc[outgoing, "pre_index"]).astype(np.int32)
    first = incoming.to_numpy() & synapses.post_index.isin(bridge).to_numpy()
    second = outgoing.to_numpy() & synapses.pre_index.isin(bridge).to_numpy()
    return mal, bridge, {"cut_vPN1_to_mAL_bridge": first, "cut_mAL_bridge_to_pC1": second,
                         "cut_both_bridge_segments": first | second}


def run(config_path, output_dir=None):
    config_path = config_path.resolve()
    cfg = json.loads(config_path.read_text(encoding="utf-8"))
    parent = (config_path.parent / cfg["parent_run"]).resolve()
    parent_lock = json.loads((parent / "protocol_lock.json").read_text(encoding="utf-8"))
    tracked = dict(parent_lock["input_and_source_sha256"])
    verify(tracked)
    for name, digest in json.loads((parent / "artifact_sha256.json").read_text()).items():
        if sha256(parent / name) != digest:
            raise RuntimeError(f"Parent artifact changed: {name}")
    base_lock_path = next(Path(p) for p in tracked if Path(p).name == "protocol_lock.json")
    baseline = base_lock_path.parent
    base_lock = json.loads(base_lock_path.read_text(encoding="utf-8"))
    golden_path = next(Path(p) for p in tracked if Path(p).name == "courtship_song_lif_v0.json")
    golden = base_lock["golden_config"]
    sys.path.insert(0, str(golden_path.parent.parent / "src"))
    from cns2fpga_golden.analysis import select_groups
    from cns2fpga_golden.model import FloatLIFNetwork
    paths = {key: (golden_path.parent / relative).resolve() for key, relative in golden["ir"].items()}
    n, s, offsets = (pd.read_csv(paths[key]) for key in ["neuron_table", "synapse_table", "offset_table"])
    groups = select_groups(n, golden["observations"])
    mal, bridge, masks = select_mal_bridge(n, s, groups["vPN1"], groups["pC1"], cfg["mal_type_regex"])
    if not len(bridge) or set(cfg["interventions"]) != set(masks):
        raise ValueError("Empty motif or incomplete interventions")
    groups.update(mAL_all=mal, mAL_bridge=bridge)
    conditions = build_equal_pulse_conditions(base_lock["config"]["protocol"], base_lock["effective_model"]["dt_ms"])
    reused = {(kind, c.ipi_ms): baseline / "population_activity" / f"{kind}_ipi_{c.ipi_ms:g}.npz"
              for kind in ["intact", "silence_vPN1"] for c in conditions}
    for path in [Path(__file__), config_path, parent / "protocol_lock.json", parent / "artifact_sha256.json", *reused.values()]:
        tracked[str(path.resolve())] = sha256(path)
    output = (output_dir or ROOT / "outputs" / cfg["name"]).resolve()
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(f"Refusing to overwrite results: {output}")
    output.mkdir(parents=True, exist_ok=True)
    (output / "population_activity").mkdir()
    write_json(output / "protocol_lock.json", dict(locked_at_utc=datetime.now(timezone.utc).isoformat(), config=cfg,
        effective_model=base_lock["effective_model"], input_and_source_sha256=tracked,
        groups={name: ids.tolist() for name, ids in groups.items()},
        interventions={name: np.flatnonzero(mask).tolist() for name, mask in masks.items()}))
    lock_digest = sha256(output / "protocol_lock.json")
    print(f"mAL follow-up locked: {lock_digest}", flush=True)
    mapping = n.iloc[bridge][["neuron_index", "bodyId", "type", "consensus_nt", "nt_model_sign", "dimorphism"]].copy()
    for label, mask, index in [("from_vPN1_synapses", masks["cut_vPN1_to_mAL_bridge"], "post_index"),
                               ("to_pC1_synapses", masks["cut_mAL_bridge_to_pC1"], "pre_index")]:
        mapping[label] = mapping.neuron_index.map(s.loc[mask].groupby(index).synapse_count.sum())
    mapping.to_csv(output / "bridge_mapping.csv", index=False)
    s.loc[masks["cut_both_bridge_segments"]].to_csv(output / "bridge_edges.csv", index=False)
    net = FloatLIFNetwork(n, s, offsets, base_lock["effective_model"])
    frozen_weights = net.weights.copy()
    empty = np.empty(0, dtype=np.int32)
    quiet = np.zeros_like(conditions[0].current)
    files, integrity = dict(reused), []
    for name in cfg["interventions"]:
        mask = masks[name]
        altered = cut_edges(net, mask)
        if len(altered.simulate(quiet, groups["auditory_input"], groups, empty).spike_times):
            raise AssertionError("Nonquiescent intervention")
        for c in conditions:
            result = altered.simulate(c.current, groups["auditory_input"], groups, empty)
            path = output / "population_activity" / f"{name}_ipi_{c.ipi_ms:g}.npz"
            np.savez_compressed(path, dt_ms=np.array([c.dt_ms]), input_current=c.current,
                                spike_times=result.spike_times, spike_neurons=result.spike_neurons,
                                **{f"{key}_counts": value for key, value in result.group_activity.items()})
            files[(name, c.ipi_ms)] = path
            integrity.append(dict(condition_id=name, ipi_ms=c.ipi_ms, removed_edges=int(mask.sum()),
                removed_synapses=int(s.loc[mask].synapse_count.sum()), finite=bool(np.isfinite(result.max_abs_voltage)),
                max_abs_voltage=result.max_abs_voltage, network_spikes=len(result.spike_times),
                uncut_weights_equal=bool(np.array_equal(altered.weights[~mask], frozen_weights[~mask])),
                cut_weights_zero=bool(np.all(altered.weights[mask] == 0))))
        print(f"Completed {name}: 9 trials", flush=True)
    rows, single = [], []
    for (name, ipi), path in files.items():
        c = next(c for c in conditions if c.ipi_ms == ipi)
        with np.load(path) as data:
            np.testing.assert_array_equal(data["input_current"], c.current)
            t, ids = data["spike_times"], data["spike_neurons"]
            counts = np.bincount(ids[(t >= c.start) & (t < c.response_end)], minlength=len(n))
            each = mapping.copy()
            each["condition_id"], each["ipi_ms"] = name, ipi
            each["response_spikes"] = counts[bridge]
            single.append(each)
            for group, members in groups.items():
                activity = population_counts(t, ids, members, len(c.current))
                if f"{group}_counts" in data:
                    np.testing.assert_array_equal(activity, data[f"{group}_counts"])
                rows.append(dict(condition_id=name, ipi_ms=ipi, group=group, neurons=len(members),
                                 **summarize_activity(activity, quiet, len(members), c, 100.)))
    summary = pd.DataFrame(rows)
    summary.to_csv(output / "response_summary.csv", index=False)
    pd.concat(single, ignore_index=True).to_csv(output / "bridge_single_cell_response.csv", index=False)
    pd.DataFrame(integrity).to_csv(output / "simulation_integrity.csv", index=False)
    motif = []
    for c in conditions:
        frame = summary[summary.ipi_ms.eq(c.ipi_ms)].pivot(index="condition_id", columns="group", values="response_spikes")
        motif.append(dict(ipi_ms=c.ipi_ms,
            bridge_increase_after_first_cut=int(frame.loc["cut_vPN1_to_mAL_bridge", "mAL_bridge"]-frame.loc["intact", "mAL_bridge"]),
            pC1_drop_after_first_cut=int(frame.loc["intact", "pC1"]-frame.loc["cut_vPN1_to_mAL_bridge", "pC1"]),
            pC1_drop_after_first_cut_with_second_removed=int(frame.loc["cut_mAL_bridge_to_pC1", "pC1"]-frame.loc["cut_both_bridge_segments", "pC1"])))
    motif = pd.DataFrame(motif)
    motif.to_csv(output / "motif_direction_diagnostics.csv", index=False)
    np.testing.assert_array_equal(net.weights, frozen_weights)
    verify(tracked)
    if sha256(output / "protocol_lock.json") != lock_digest:
        raise AssertionError("Protocol changed")
    meta = dict(verdict="EXPLORATORY_MOTIF_AUDIT_NOT_BIOLOGICAL_PASS", model_freeze_recommended=False,
                protocol_lock_sha256=lock_digest, model_parameter_changes={}, frozen_inputs_unchanged=True,
                new_stimulus_trials=27, reused_stimulus_trials=18, quiet_trials=3, mAL_all_neurons=len(mal),
                mAL_bridge_neurons=len(bridge), mAL_bridge_type_labels=mapping.type.unique().tolist(),
                first_segment_edges=int(masks["cut_vPN1_to_mAL_bridge"].sum()),
                second_segment_edges=int(masks["cut_mAL_bridge_to_pC1"].sum()),
                first_segment_synapses=int(s.loc[masks["cut_vPN1_to_mAL_bridge"], "synapse_count"].sum()),
                second_segment_synapses=int(s.loc[masks["cut_mAL_bridge_to_pC1"], "synapse_count"].sum()),
                completed_at_utc=datetime.now(timezone.utc).isoformat())
    write_json(output / "run_metadata.json", meta)
    reference = summary[summary.ipi_ms.eq(cfg["reference_ipi_ms"]) & summary.group.isin(["mAL_bridge", "pC1"])].pivot(
        index="condition_id", columns="group", values="response_spikes").reset_index()
    reference.columns.name = None
    report = ["# mAL 去抑制通路专项补充（v2b）", "",
        "**通路审计与消融已执行；不据此宣布第四步通过。**", "",
        "MaleCNS 论文提出 vPN1 抑制雄性特有 mAL，再解除 mAL 对 pC1 的抑制，可能解释早期功能实验的净兴奋效应。[原文与 Figure S5G](https://doi.org/10.1016/j.cell.2026.08.015)", "",
        "这使我们优先检查具名的去抑制通路，而不是更改 vPN1 的预测递质。当前选取全部满足两段负权重连接的 mAL，是注释加拓扑定义的候选集合，未验证与论文图中细胞的一对一对应。", "",
        f"在当前子图的 {len(mal)} 个 mAL 中，{len(bridge)} 个符合 vPN1 −| mAL −| pC1 的两跳连接条件；第一段 {meta['first_segment_edges']} 条边、{meta['first_segment_synapses']} 个聚合突触，第二段 {meta['second_segment_edges']} 条边、{meta['second_segment_synapses']} 个聚合突触。**候选中继已在子图中，并非整体漏掉 mAL。**", "",
        "分别切第一段、第二段、两段，共 27 次新试次（全部 9 个 IPI）；复用 18 次完整/vPN1 消融事件，另做 3 次静默检查。全部模型参数不变，未重新归一化，未补造外部 mAL 驱动。", "",
        "## 35 ms 的累计群体放电数", "", table(reference), "",
        "## 完整 IPI 的方向性诊断", "", table(motif), "",
        "理想孤立去抑制链下，切第一段应使中继放电增加、pC1 降低；若第二段切断，该 pC1 效应应减弱。当前为递归网络：mAL 还有其他输出与反馈，方向相符只支持模型内该机制，不能证明唯一中介。计数为单个确定性模型的放电数，不是动物重复样本。", "",
        "`bridge_single_cell_response.csv` 保存所有候选的全部条件，允许检查沉默中继、相反方向和弱响应；没有按活跃程度筛选。`motif_direction_diagnostics.csv` 保留全部方向结果，不把不符合简化假设的 IPI 隐去。", "",
        "结论应结合 [v2 诊断报告](../courtship_song_mechanism_v2/report.md)：模型拓扑含去抑制候选，但其实际作用受神经元驱动、反馈及读出方式影响。不能仅凭连接存在就声称该机制已复现，也不应删掉其他真实边以制造单一路径。", "",
        f"协议哈希：`{lock_digest}`。输入/源代码哈希与原网络权重在运行前后保持一致。", ""]
    (output / "report.md").write_text("\n".join(report), encoding="utf-8")
    write_json(output / "artifact_sha256.json", {str(p.relative_to(output)): sha256(p) for p in sorted(output.rglob("*")) if p.is_file()})
    print(json.dumps(meta, indent=2), flush=True)
    print(table(reference), flush=True)
    print(table(motif), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "configs/courtship_song_mal_v2b.json")
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    run(args.config, args.output_dir)
