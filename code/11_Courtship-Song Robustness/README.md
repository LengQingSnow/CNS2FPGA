# Step 11 — Courtship-Song Robustness

以第十步已冻结的 35 ms IPI、40 脉冲试次为基线，考察回路和输入扰动。正式结果在 `outputs/courtship_song_robustness_v2/`。扰动适配器位于本目录的 `src/`，第三、第五步冻结源码的 SHA-256 已恢复。基础网络为 6279 个神经元、350185 条突触。

## 扰动与测量

- 随机删除突触、随机使神经元失效：5/10/20%，每档 5 个固定种子；无放回抽样。
- 权重扰动：每条边独立乘以非负 `max(0, 1 + N(0,p))`，`p` 为 5/10/20%，每档 5 个固定种子。
- 输入噪声：每毫秒向 35 ms IPI 输入波形加入 `N(0, 1.2p)` 标量电流，5/10/20%，每档 5 个固定种子；每档 `r0` 还在 AXKU115 上执行。
- 关键节点全量消融：`auditory_input`、`aPN1`、`vPN1`、`pIP10`。
- 量化敏感性：第五步的四种锁定格式在 35 ms IPI 下重放，另对照第五步完整 IPI 扫描的最坏误差。

主要读数为 vPN1、pC1、pIP10、pMP2 响应窗（100–1968 ms）的 spike 数。曲线纵轴定义为相对完整回路的响应绝对偏差百分比；它是计算读数，不是行为准确率。随机重复仅用于描述实验波动。

## 复现

在本目录运行：

```powershell
$py = 'python'
& $py '.\run_robustness.py' prepare
& '.\run_board_noise.ps1' -Python $py # 已有采集可跳过
& $py '.\run_robustness.py' analyze
& $py '.\verify_board_noise.py'
& $py '.\compare_quantization_envelope.py'
```

`prepare` 不会覆盖非空输出目录；板上脚本拒绝覆盖已有捕获。v2 默认复用 v1 已采集的三条板上噪声数据，并在分析时逐个核对新旧刺激文件 SHA-256；若要独立重测，可运行板上脚本生成 v2 捕获，分析会优先使用它。`analyze` 还会检查源码、配置、IR、基线档案和捕获的哈希、时钟与状态。

当前 CNS9 bitstream 只开放运行时刺激输入。突触删除、神经元失效和权重扰动由 CPU 浮点与定点模型比较；要在 FPGA 上执行它们，需要编译新的硬件 IR 和 bitstream。板上输入噪声每步只提供一个电流值，由 93 个输入神经元共同接收。

详细解释与不能外推的结论见 [result_interpretation.md](docs/result_interpretation.md)。
