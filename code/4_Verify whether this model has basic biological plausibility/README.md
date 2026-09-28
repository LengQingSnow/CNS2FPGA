# Step 4 — Basic biological-plausibility verification

**最新结果解读：v2 机制诊断（不是新的生物学通过结论）。**
优先阅读 [综合结果解读](docs/result_interpretation_v2.md)，包括后续完成的 mAL 专项实验。
见 [v2 诊断协议](docs/mechanism_diagnostics_v2.md) 和
[诊断报告](outputs/courtship_song_mechanism_v2/report.md)。v2 复用 v1 的事件，
新增 36 个边/神经元干预试次，核查 vPN1 的原始递质预测、全部 pC1 类型、
旁路及读出敏感性。原模型参数、递质符号和 v1 判据不变。
正式冻结模型前，应先阅读 v2 对 v1 因果假设的限制说明。

v3 已将实验 driver / ROI 的证据分层，结果与后续可导入的 bodyId 映射契约见
[ROI 映射审计](outputs/courtship_song_roi_mapping_v3/report.md) 与
[外部证据输入契约](docs/external_roi_mapping_contract_v3.md)。公开资源检索及边界见
[在线证据记录](docs/online_roi_evidence_search_v3.md)。

用户导出的 R71G01 雄性 MCFO-NeuronBridge 搜索表已完成全量注释补齐与路径审计。
21,930 条 MaleCNS 结果全部能对上 v1.0 注释；共检出 148 个 pC1，其中 107 个已在
冻结子图、41 个在子图外。`bodyId=10217` 是 CSV 自带 pC1 标签时显式可见的候选，
补全注释后并非唯一候选；它因输入距离 3 + 输出距离 2 超过 `max_hops=4` 被排除。
以 [v3c 全量审计](outputs/neuronbridge_r71g01_annotation_audit_v3c/report.md) 为准；
[v3b 初筛](outputs/neuronbridge_r71g01_screen_v3b/report.md) 保留为过程记录。

v3d 已在不重新仿真、不调整参数的前提下，从 81 个锁定事件文件重算 6 种 pC1
候选读出。宽口径的 NeuronBridge 任意命中集合（107 个）与全体 pC1 的 35 ms
干预方向 24/24 一致；但最佳名次 ≤100 的窄集合（15 个）仅 16/24 一致，且多项
vPN1/aPN1 干预出现符号反转。这说明工程结论对宽读出较稳定，却不能把排名靠前的
少数形态命中直接当作实验 ROI。详见
[v3d 候选读出鲁棒性审计](outputs/courtship_song_roi_robustness_v3d/report.md)。

`run_mal_followup.py` / `configs/courtship_song_mal_v2b.json` 另外审计并切断
文献提出的 `vPN1 -| mAL -| pC1` 去抑制候选链（27 个新增试次），结果另存
[v2b 专项报告](outputs/courtship_song_mal_v2b/report.md)，不会覆盖 v2 或 v1。

**当前默认：v1 等脉冲数完整验证。** 使用 `run_plausibility_validation.py`
或 `run_equal_pulse_validation.py`，详细协议、命令与输出解释见
[v1 协议说明](docs/equal_pulse_protocol_v1.md)。默认输出
`outputs/courtship_song_equal_pulse_v1/`。已锁定运行不覆盖，重跑请指定新的
`--output-dir`。v0 的“16 项通过”属于三点探索结果，不能作为完整验证通过的证据。

以下保留 v0 说明与显式重跑方法，历史输出不变。

This stage audits the frozen step-2 subgraph and step-3 floating-point LIF model. It does **not** tune the model until it passes, and it does not claim to reproduce a fly brain. Its purpose is to expose which biological constraints are satisfied and which are not.

## What is checked

- structural presence of auditory input, aPN1, vPN1, pC1, pIP10 and pMP2;
- agreement between neurotransmitter annotations and the sign convention used by the published whole-brain LIF model;
- whether IPI changes the response;
- qualitative pC1 band-pass constraints at the available 16/36/56-ms points;
- pC1 and auditory-input in-silico ablations;
- pC1 ablation against matched-size random-neuron controls.

The current three-point sweep supports only a trend test. A numerical correlation with experiment is deliberately not reported because the local eLife paper provides the plotted curve but not raw per-fly numeric source data. The tool never invents or hand-digitizes values silently.

## Run

```powershell
$py = 'python'
& $py '.\run_plausibility_validation.py' --config '.\configs\courtship_song_plausibility_v0.json' --output-dir '.\outputs\v0_repeat'
& $py -m pytest '.\tests' -q
```

Outputs are written to `outputs/courtship_song_plausibility_v0/`:

- `report.md`: verdict, every check and next corrections;
- `validation_checks.csv`: machine-readable PASS/FAIL/WARN table;
- `baseline_response.csv`: intact responses for each IPI;
- `ablation_results.csv`: targeted and random-control perturbations;
- `neurotransmitter_sign_audit.csv`: transmitter/sign breakdown;
- `reference_constraints.csv`: exact qualitative constraints and citations;
- `ipi_tuning_audit.png`, `ablation_audit.png`, `validation_dashboard.png`;
- `run_metadata.json`: input hashes, versions and runtime.

## Interpretation

A failed audit is a useful result: it blocks premature FPGA claims and identifies what must change in extraction, annotation mapping, stimulation protocol or model dynamics. Step 4 leaves the step-2 IR and step-3 model untouched so the diagnosis remains reproducible.
