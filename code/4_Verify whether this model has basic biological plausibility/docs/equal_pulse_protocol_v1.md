# 第四步：40 脉冲完整 IPI 协议 v1

新版在看到结果前锁定判据、读出、模型、代码及输入哈希。`outputs/courtship_song_plausibility_v0/` 是之前的三点探索结果，不能作为完整调谐验证通过的证据。

## 运行

在第四步目录执行：

```powershell
$py = 'C:\Users\20474\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
& $py '.\run_plausibility_validation.py'
# 直接入口；另存一次运行，并在核心判据未通过时返回退出码 2：
& $py '.\run_equal_pulse_validation.py' --output-dir '.\outputs\equal_pulse_v1_repeat' --require-pass
& $py -m pytest '.\tests' -q -p no:cacheprovider
```

默认输出 `outputs/courtship_song_equal_pulse_v1/`。锁定目录不允许覆盖；重复实验请指定新的 `--output-dir`。程序执行成功与生物学判据通过分开记录；不用 `--require-pass` 时，方向检查失败仍正常生成完整报告。

## 运行前固定的协议

- IPI：15、25、35、45、55、65、75、85、95 ms，每组 40 个脉冲。
- 100 ms 静默前段，3 ms 脉冲宽，幅度 1.2。所有试次 4308 ms；读出窗口为刺激开始至最后一个脉冲结束后 500 ms，逐条件导出边界。
- 主读出：窗口内完整 100 ms 滑窗的最大平均神经元放电率，扣除对应静默轨迹。
- 次读出/消融读出：响应窗口内净放电数 / 群组全部神经元数 / 40。另报刺激期间 Hz、尾部末端 Hz、等长完整试次的净放电量。
- 100 ms 窗口是工程选择，不是 GCaMP 拟合时间常数；spike rate 不等于峰值 ΔF/F。确定性模型不伪造动物重复或实验 correlation。
- 核心调谐方向：vPN1 的 35 ms 高于 15 ms；pC1 的 35 ms 高于 15/25 ms，以及 85/95 ms。35–65 ms 均在文献强响应区，不要求 35 高于 55/65。
- 不使用事后调整的 5 Hz 或 20% 调制门槛；1e-12 仅为数值容差。
- vPN1、pC1、听觉输入消融各跑 9 组 IPI。夹断细胞钳制复位且禁止放电，不改变其余权重。35 ms 时 vPN1 消融降低 pC1 是事先声明的回路因果假设。
- vPN1/pC1 各 24 组随机对照在 35 ms 运行，匹配细胞数及正/负/未知符号组成，排除观测群。未匹配度数、连接权重或活跃度，95 分位仅为描述性参考。
- pIP10、pMP2 独立报告；合并读出 `output_combined_exploratory` 不设生物学验收阈值，其与 chaining 的关系仍未验证。

第三步参数固定为已有 `raw_linear`、gain=0.015、dt=1 ms、膜时间常数=20 ms、阈值=1、复位=0、refractory=2 ms、bias/noise=0。引擎只增加可选 `silenced_indices` 和非有限电位报错；无消融的普通仿真行为不变。IR/拓扑不变。

## 文件分类

| 文件 | 用途 |
| --- | --- |
| `configs/courtship_song_equal_pulse_v1.json` | 协议、方向判据、参考文献及控制抽样设置 |
| `src/cns2fpga_plausibility/protocol.py` | 刺激、统计窗口、指标 |
| `src/cns2fpga_plausibility/evaluation_v1.py` | 核心判定、消融量、对照统计 |
| `src/cns2fpga_plausibility/reporting_v1.py` | 中文报告及图表 |
| `run_equal_pulse_validation.py` | 完整实验、可复现锁定 |
| `tests/test_equal_pulse_protocol.py` | 脉冲完整性、边界、缺失响应、平台带通和控制抽样测试 |
| 输出 `protocol_lock.json` | 仿真前记录的配置、源代码/输入哈希、群组和随机成员 |
| 输出 `stimulus_manifest.json` | 每个脉冲时刻、电流积分、试次与读出窗口 |
| 输出 `group_mapping.csv`、`pathway_connectivity.csv` | 名称/bodyId 映射及真实群组间边数/突触数 |
| 输出 `baseline_response.csv` | 9 个 IPI × 7 个观测群组的全部完整网络指标 |
| 输出 `ablation_response.csv`、`ablation_effects.csv` | 消融指标和相对完整网络的变化 |
| 输出 `ablation_membership.json`、`random_control_summary.csv` | 抽样列表、种子及描述性分布 |
| 输出 `population_activity/*.npz` | 完整/定向消融的刺激、逐步群组活动、全网 spike event，可重算指标 |
| 输出 `validation_checks.csv`、`simulation_integrity.csv` | 生物学方向与数值/夹断执行检查分开记录 |
| 输出 `output_readout_scope.json` | 保留旧输出警告对应的未验证行为映射 |
| 输出 `report.md`、三幅 PNG、`run_metadata.json` | 可审阅结果、结论和软件版本 |

## 判定边界

`NOT_SUPPORTED`：至少一个核心检查失败。`INCOMPLETE`：核心检查不可评估。`CONDITIONAL_SUPPORT`：固定放电代理通过所有核心方向/执行检查。最后一种结论仍不代表复现实验钙信号或行为。次指标若与主指标冲突也会保留。

参考：[Zhou et al., eLife 2015](https://elifesciences.org/articles/08477)（Fig 5H、6K、6E）、[Shiu et al., Nature 2024](https://doi.org/10.1038/s41586-024-07763-9)。
