"""Separate exploratory diagnosis from the historical v1 acceptance report."""
from __future__ import annotations

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


LABELS = {"intact": "Intact", "silence_vPN1": "Silence vPN1",
          "cut_vPN1_to_pC1": "Cut vPN1 -> pC1", "cut_vPN1_to_other": "Cut other vPN1 outputs",
          "cut_vPN1_all_output": "Cut all vPN1 outputs", "silence_aPN1": "Silence aPN1"}


def table(frame):
    """Small dependency-free Markdown table."""
    def cell(value):
        if isinstance(value, (float, np.floating)):
            return f"{value:.5g}" if np.isfinite(value) else "N/A"
        return str(value).replace("|", " / ")
    return "\n".join(["| " + " | ".join(frame.columns) + " |",
                      "| " + " | ".join(["---"] * len(frame.columns)) + " |",
                      *["| " + " | ".join(map(cell, row)) + " |" for row in frame.itertuples(index=False, name=None)]])


def make_figures(output, summary, observations, effects, cfg):
    with plt.rc_context({"font.size": 9, "axes.spines.top": False, "axes.spines.right": False}):
        fig, axes = plt.subplots(1, 3, figsize=(16, 4.8), constrained_layout=True)
        for metric, rows in observations[observations.group.eq("pC1")].groupby("metric", sort=True):
            rows = rows.sort_values("ipi_ms")
            peak = rows.value.max()
            axes[0].plot(rows.ipi_ms, rows.value / peak if peak > 0 else rows.value, marker=".", label=metric)
        axes[0].set(title="pC1: readout sensitivity (no fitting)", xlabel="IPI (ms)", ylabel="Each curve / its own maximum")
        axes[0].legend(fontsize=7)
        for name, rows in summary[summary.group.eq("pC1") & ~summary.condition_id.eq("cut_vPN1_all_output")].groupby("condition_id"):
            rows = rows.sort_values("ipi_ms")
            axes[1].plot(rows.ipi_ms, rows.evoked_spikes_per_neuron_per_pulse, marker=".", label=LABELS[name])
        axes[1].set(title="pC1: edge vs neuron interventions", xlabel="IPI (ms)", ylabel="Spikes / neuron / pulse")
        axes[1].legend(fontsize=7)
        key = ["pC1", "pC1_direct_vPN1_recipient", "pC1_no_direct_vPN1"]
        data = effects[effects.group.isin(key) & effects.ipi_ms.eq(cfg["reference_ipi_ms"]) &
                       effects.metric.eq("evoked_spikes_per_neuron_per_pulse") &
                       effects.condition_id.isin(["silence_vPN1", "cut_vPN1_to_pC1", "cut_vPN1_to_other"])].copy()
        labels = ["silence_vPN1", "cut_vPN1_to_pC1", "cut_vPN1_to_other"]
        for k, group in enumerate(key):
            rows = data[data.group.eq(group)].set_index("condition_id")
            axes[2].bar(np.arange(3)+(k-1)*.25, [rows.loc[name, "drop_percent"] for name in labels], width=.25,
                        label=group.replace("pC1_", ""))
        axes[2].set_xticks(np.arange(3), ["Silence vPN1", "Cut direct", "Cut other"], rotation=15)
        axes[2].axhline(0, color="black", lw=.7)
        axes[2].set(title="35 ms: positive = response reduction", ylabel="Integrated response drop (%)")
        axes[2].legend(fontsize=7)
        fig.suptitle("v2 exploratory diagnosis | unchanged LIF parameters and neurotransmitter signs", fontsize=12)
        fig.savefig(output / "mechanism_diagnostics.png", dpi=170)
        plt.close(fig)

        rows = summary[summary.group.str.startswith("pC1_type:") & summary.condition_id.eq("intact")]
        matrix = rows.pivot(index="group", columns="ipi_ms", values="evoked_spikes_per_neuron_per_pulse").sort_index()
        scale = matrix.max(axis=1).replace(0, 1)
        normalized = matrix.div(scale, axis=0)
        drop = effects[effects.group.str.startswith("pC1_type:") & effects.condition_id.eq("silence_vPN1") &
                       effects.metric.eq("evoked_spikes_per_neuron_per_pulse")].pivot(index="group", columns="ipi_ms", values="drop_percent").reindex(matrix.index)
        fig, axes = plt.subplots(1, 2, figsize=(12, 13), constrained_layout=True)
        im = axes[0].imshow(normalized.to_numpy(), aspect="auto", cmap="viridis", vmin=0, vmax=1)
        axes[0].set_title("Intact: each subtype / own maximum")
        fig.colorbar(im, ax=axes[0], label="Normalized integrated response", shrink=.6)
        # Symmetric log color scale keeps large low-baseline effects visible without clipping.
        from matplotlib.colors import SymLogNorm
        finite = drop.to_numpy()[np.isfinite(drop.to_numpy())]
        bound = max(100., float(np.max(np.abs(finite)))) if finite.size else 100.
        im = axes[1].imshow(np.ma.masked_invalid(drop.to_numpy()), aspect="auto", cmap="RdBu_r",
                            norm=SymLogNorm(linthresh=10., vmin=-bound, vmax=bound))
        axes[1].set_title("vPN1 silencing: drop %, gray = inactive baseline")
        axes[1].set_facecolor("#dddddd")
        fig.colorbar(im, ax=axes[1], label="Drop % (symmetric log scale)", shrink=.6)
        sizes = rows.groupby("group").neurons.first()
        for ax in axes:
            ax.set_yticks(np.arange(len(matrix)), [f"{name.split(':', 1)[1]} (n={sizes[name]})" for name in matrix.index], fontsize=8)
            ax.set_xticks(np.arange(len(matrix.columns)), [f"{value:g}" for value in matrix.columns])
            ax.set_xlabel("IPI (ms)")
        fig.suptitle("All pC1 type labels; alphabetical order; no post-hoc responder selection", fontsize=12)
        fig.savefig(output / "pC1_all_subtypes.png", dpi=150)
        plt.close(fig)


def write_report(output, summary, observations, directions, effects, connectivity, nt, cfg, meta):
    ipi = cfg["reference_ipi_ms"]
    metric = "evoked_spikes_per_neuron_per_pulse"
    pc = summary[summary.group.eq("pC1") & summary.ipi_ms.eq(ipi)].copy()
    drops = effects[effects.group.eq("pC1") & effects.ipi_ms.eq(ipi) & effects.metric.eq(metric)].set_index("condition_id")
    pc["drop_percent"] = [0. if name == "intact" else drops.loc[name, "drop_percent"] for name in pc.condition_id]
    pc = pc[["condition_id", "response_spikes", metric, "peak_rate_hz", "drop_percent"]]
    sensitivity = directions[directions.group.eq("pC1")].pivot(index="metric", columns="comparison", values="supported").reset_index()
    sensitivity.columns.name = None
    anatomy = summary[summary.ipi_ms.eq(ipi) & summary.group.isin(["pC1_direct_vPN1_recipient", "pC1_no_direct_vPN1"]) &
                      summary.condition_id.isin(["intact", "silence_vPN1", "cut_vPN1_to_pC1", "cut_vPN1_to_other"])][
                          ["group", "neurons", "condition_id", "response_spikes", metric]]
    effect = effects[effects.group.eq("pC1") & effects.condition_id.eq("silence_vPN1") & effects.metric.eq(metric)]
    reductions = int(effect.drop_percent.gt(0).sum())
    increases = int(effect.drop_percent.lt(0).sum())
    longs = sensitivity.long_85_95.sum()
    all_pass = (sensitivity.long_85_95 & sensitivity.short_15_25).sum()
    interaction = pd.read_csv(output / "factorial_interactions.csv")
    joint = interaction[interaction.group.eq("pC1") & interaction.ipi_ms.eq(ipi) & interaction.metric.eq(metric)].iloc[0]
    subtype = effects[effects.group.str.startswith("pC1_type:") & effects.condition_id.eq("silence_vPN1") &
                      effects.ipi_ms.eq(ipi) & effects.metric.eq(metric)]
    zero = int(subtype.baseline.le(cfg["numerical_tolerance"]).sum())
    lowered = int((subtype.baseline.gt(cfg["numerical_tolerance"]) & subtype.perturbed.lt(subtype.baseline-cfg["numerical_tolerance"])).sum())
    raised = int((subtype.baseline.gt(cfg["numerical_tolerance"]) & subtype.perturbed.gt(subtype.baseline+cfg["numerical_tolerance"])).sum())
    lines = [
        "# v2 机制诊断与结果解读", "",
        "**结论：诊断执行完成，但第四步尚不宜宣布生物学验证无保留通过，也不建议冻结最终 Golden Model。**", "",
        "本轮解释 v1 的矛盾，不以调参消除警告。v1 的原始数据、自动结论与判据不变；本报告是看过 v1 后设计的探索性分析，不是独立验证。", "",
        "## 1. 最重要的修正：不要把 vPN1 默认当作兴奋性串行中继", "",
        f"原始 MaleCNS 递质表与 IR 一致：{len(nt)} 个 vPN1 的 consensus_nt 均为 GABA，模型符号为 -1。单细胞预测置信度为 {nt.predicted_nt_confidence.min():.3f}–{nt.predicted_nt_confidence.max():.3f}；ground_truth 非空 {meta['vPN1_nonmissing_ground_truth']} 个。这是数据集预测与建模约定，不是逐连接受体或电生理验证。", "",
        "因此，v1 的“vPN1 消融应使 pC1 累计放电下降”只能是项目假设，不能用作未经条件限定的文献事实。直接抑制、间接作用、反馈都可能参与；行为受损也不等同于某一群体平均放电必然下降。保留递质符号，不为符合直觉而翻成兴奋性。", "",
        "## 2. 真正执行的因果区分", "",
        "把 vPN1 出边分成：A=到 pC1 的直接边，B=其余出边（包括可能的反馈相关边）。执行 A 切断、B 切断、A+B 切断，加上 aPN1 神经元消融；每种跑完整 9 个 IPI，共 36 次新刺激试次。其余权重完全不变，不重新归一化。", "",
        f"复用 18 次 v1 事件记录；另重跑 1 次完整网络核对，及 5 次静默检查。参考试次与 v1 spike event 逐项相同；A+B 切断在全部 9 个 IPI 下，对 vPN1 以外所有神经元产生与 vPN1 神经元消融完全相同的事件。", "",
        f"### {ipi:g} ms：pC1 定量结果", "", table(pc), "",
        "drop_percent 为正表示下降，为负表示增加。峰值与累计响应是不同问题，不能择优报告。", "",
        f"累计响应的 2×2 交互量 R(A+B)-R(A)-R(B)+R(intact)={joint.interaction:.6g} spikes/neuron/pulse。非零交互表示网络非线性，不能简单把两个消融百分比相加，或把差值当作唯一的间接通路贡献。切直接抑制边也不保证全网络累计放电单调增加。", "",
        f"完整 IPI 扫描中，vPN1 消融使 pC1 累计响应在 {reductions}/9 个条件下降、{increases}/9 个条件增加；这限制了统一的“正向中继必要性”解释。", "",
        "## 3. pC1 群体混合与旁路", "",
        f"当前 pC1 包含 {meta['pC1_neurons']} 个神经元、{meta['pC1_type_labels']} 个 type 标签。vPN1→pC1 有 {meta['vPN1_direct_pC1_edges']} 条边、{meta['vPN1_direct_pC1_synapses']} 个聚合突触，直接覆盖 {meta['vPN1_direct_pC1_recipients']} 个 pC1，仅占全部 pC1 入突触的 {100*meta['vPN1_fraction_all_pC1_incoming_synapses']:.3f}%。这是解剖计数占比，不是有效电流或因果贡献占比。", "",
        f"删除 vPN1 后，{meta['pC1_reachable_without_vPN1_positive_only']}/{meta['pC1_neurons']} 个 pC1 仍存在从听觉输入出发、全正权重边的有向路径。它说明提取子图存在旁路，不证明这些路径在动物中被激活、占主导或解释了全部残余响应。路径逐细胞保存。", "",
        table(anatomy), "",
        f"在 {ipi:g} ms，43 个 type 标签中：基线活跃且 vPN1 消融后下降 {lowered} 个、增加 {raised} 个；基线为零 {zero} 个（百分比不可定义）。剩余为基线活跃但数值无变化。所有 type、fruDsx 标签分组、全部单细胞结果均导出，不事后挑选符合预期的亚型作为通过依据。", "",
        "MaleCNS 的 type/fruDsx 标签不能自动等同于 2015 年实验驱动系和成像 ROI；目前没有建立这种精确映射。", "",
        "## 4. 读出敏感性：峰值不等于累计量，更不等于 ΔF/F", "",
        "固定检查 20/50/100/200 ms 峰值窗口、每脉冲累计量、三种双指数代理（rise=50 ms；decay=200/500/1000 ms）。代理的单 spike 核峰值归一为 1，单位为任意单位；参数仅用于工程敏感性分析，不是拟合的 GCaMP6m 时间常数。", "",
        "下表 True 仅表示 35 ms 响应严格高于所列比较点；不是显著性、独立验证或新的生物学 PASS。", "", table(sensitivity), "",
        f"pC1 长 IPI 衰减在 {int(longs)}/{len(sensitivity)} 个读出下成立；短、长两组方向同时成立 {int(all_pass)}/{len(sensitivity)}。全部曲线均保留，没有选择最有利核函数来替换 v1 主读出。", "",
        "实验本身测量峰值钙信号，并指出慢指示剂动力学、vPN1 胞体与 pC1 神经突起成像部位差异可能影响调谐。当前滤波只能检查结论对观测方式是否敏感，不能据此声称复现钙信号，也不能计算未经校准的实验相关系数。[Zhou et al., 2015](https://pmc.ncbi.nlm.nih.gov/articles/PMC4575990/)", "",
        "## 5. 当前可接受的结论与下一步", "",
        "- 工程侧：固定数据、浮点仿真、定向消融和复现检查可用。", 
        "- 生物学侧：存在 IPI 敏感性和网络因果效应，但串行兴奋性回路、强 vPN1 特异必要性、稳定 pC1 带通以及行为输出映射尚未得到充分支持。", 
        "- 当前代码更适合作为 **connectome-constrained 工程参考候选**，不是已经校准的行为预测模型。", 
        "- 后续优先建立实验驱动系/ROI 与 MaleCNS 亚型的可核查映射，并取得可用的实验数值约束；若引入细胞动力学或观测模型改动，另立版本、预先限定参数并保留独立刺激条件测试。不能只挑响应好的亚型或调整抑制符号。", 
        "- 本轮不开始第五步，不改第二、三步 IR/权重/神经元参数，也不把历史失败项改成通过。", "",
        "## 复现与证据", "",
        f"v1 lock: `{meta['baseline_lock_sha256']}`；v2 lock: `{meta['protocol_lock_sha256']}`。全部旧输入及源文件哈希在运行前后核验一致。", "",
        "- `vPN1_raw_nt_audit.csv`：原始递质字段、预测置信度、ground_truth 与 IR 对照。",
        "- `edge_interventions.csv` / `simulation_integrity.csv`：切边与运行完整性。",
        "- `response_summary.csv` / `intervention_effects.csv` / `factorial_interactions.csv`：完整消融与交互量。",
        "- `pC1_connectivity.csv` / `pC1_single_cell_response.csv` / `pC1_subtype_connectivity.csv`：全部细胞、亚型、旁路。",
        "- `pC1_offered_drive.csv`：按源符号分解的原始突触驱动总和；未考虑膜衰减和不应期丢弃，不是实际积分电流或因果贡献。",
        "- `observation_sensitivity.csv` / `observation_directions.csv`：所有读出组合，包含响应窗后峰值标记。",
        "- `population_activity/`：36 次新增仿真的完整 spike events。",
        "- `artifact_sha256.json`：本轮生成文件的内容校验清单。", "",
        "![机制诊断](mechanism_diagnostics.png)", "", "![全部 pC1 类型](pC1_all_subtypes.png)", "",
    ]
    (output / "report.md").write_text("\n".join(lines), encoding="utf-8")
