# Step 11 — courtship-song 回路鲁棒性

35 ms IPI、40 个 3 ms 脉冲、幅度 1.2；网络与动力学沿用第十步。
随机突触删除、随机神经元失效、权重高斯扰动和输入高斯噪声各用 5/10/20% 三档、每档 5 个预先固定种子。
比例为被删元素比例或噪声标准差相对标称值的比例；全量关键节点消融另列。

## 结果

- CPU 执行 65 条完整 4308-step 试次；浮点/定点响应窗关键群体计数最大绝对差 0 spikes。
- 三条输入噪声试次上板：定点 CPU 与 FPGA 响应窗群组计数 全部一致；诊断标志合计 0。
- 上板最慢步 199063 / 200000 cycles。
- 原始/汇总数据：`condition_metrics.csv`、`degradation_summary.csv`、`fpga_noise_comparison.csv`、`quantization_sensitivity.csv`。
- 图：`degradation_curve.png`、`ablation_response.png`、`quantization_sensitivity.png`、`fpga_noise.png`。

## 解释范围

性能变化定义为相对完整模型的响应窗 spike 数绝对偏差，并非行为准确率。
当前 CNS9 bitstream 的运行时接口只能更新刺激；突触删除、神经元失效和权重扰动的 FPGA 实现需要重新编译 IR 与 bitstream，本次仅做 CPU 浮点/定点对照。
上板输入噪声为每毫秒一个标量电流值，由 93 个输入神经元共同接收；不表示每个神经元独立噪声。
随机试次仅 5 个重复；图中的标准差是这 5 个样本的描述性波动，不是总体置信区间。
实验 ROI 与 MaleCNS 亚型映射尚待独立生物学证据。

协议锁 SHA-256：`0107797de5475d30950630a526df89afcd63351f3d05b8e9fbd876bd56fc95a2`。
