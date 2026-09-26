# 最小 FPGA 架构 v1

## 执行顺序

每个 1 ms 模型 timestep 分为两个串行阶段：

1. `UPDATE` 顺序扫描全部 neuron，读取膜电位、上一周期累积的突触电流、定点参数和
   type/sign，执行衰减、外部输入、饱和、阈值和不应期更新；spike 写入 queue，同时清空
   该 neuron 的突触电流槽。
2. `PROPAGATE` 读取每个 spiking pre-neuron 的 CSR offset，顺序遍历 `synapse.mem`，
   将权重累加到 post-neuron 的下一周期电流槽。全部事件传播完毕后产生 `timestep_done`。

该顺序与第五步 CPU 定点模型一致：t 时刻产生的 spike 在 t+1 时刻影响 post-neuron。

## 第一版边界

- 单个物理 neuron engine，时间复用 6,279 个虚拟神经元；
- 单个 synapse accumulation engine，天然避免多写端口冲突；
- 所有静态图和动态状态均面向片上 BRAM，不使用 DDR；
- 输入电流由外部 stimulus controller 每 timestep 提供；
- 输出逐 spike 给出 neuron index 和 pC1 标志；
- 饱和标志为每 timestep 的粘滞诊断信号。

当前 RTL 是最小正确性架构，不宣称最终吞吐率。直接数组访问先用于行为与综合可行性基线；
第八步逐周期对拍时，应把各存储访问显式流水化为目标器件同步 BRAM 延迟，并保持本状态机
可观察顺序不变。

## 周期上界

不考虑后续 BRAM 流水延迟时，一个 timestep 约需：

`N_neuron + 2 × N_spike + N_traversed_edge`

周期。最坏情况所有神经元放电并遍历全部 350,185 条边，约为 369k 周期；实际取决于
spike 稀疏度。第八、九步需要基于真实事件档案统计周期分布并确定目标时钟。
