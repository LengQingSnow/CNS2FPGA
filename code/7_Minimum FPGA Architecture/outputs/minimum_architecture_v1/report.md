# Minimum FPGA Architecture v1 report

**FUNCTIONAL PASS：单引擎 RTL 的一周期突触传播和完整第六步镜像加载均通过 ModelSim。**

- two-neuron propagation: PASS
- full image load: PASS (6,279 neurons / 350,185 synapses / 93 inputs / 112 pC1)
- DDR: disabled; on-chip memory image only
- maximum observed cycle estimate: 58,618 cycles/timestep
- minimum clock for observed 1-ms deadline: 58.618 MHz
- theoretical all-neuron/all-edge bound: 369,022 cycles/timestep (369.022 MHz)

周期估算来自 9 个锁定 intact IPI 事件档案。它是单引擎算法周期数，不包含同步 BRAM
新增流水级、主机接口和时钟收敛裕量。当前没有宣称综合通过或板上实时；第八步必须显式加入
同步 BRAM 延迟并与 CPU 定点模型逐周期对拍。

protocol lock: `1124938d837349cb7d21eb244fe14832d292f2077e32cb33ad55f66190297484`
