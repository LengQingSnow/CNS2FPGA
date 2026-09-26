# Full-network CPU–RTL bit-exact report

**PASS：完整 6,279-neuron 网络连续 8 个 timestep 与 CPU 定点参考逐位一致。**

- neuron-timestep states: 50,232
- compared per state: spike / voltage / syn_current / refractory
- total spikes: 2,475
- mismatches: 0
- saturation events: 0
- ModelSim compile/simulation: 0 errors, 0 warnings
- maximum synchronous-RTL cycles/timestep: 167,668
- minimum clock for observed 1-ms deadline: 167.668 MHz

结果证明同步存储状态机与第五步整数语义在该连续刺激上 bit-exact。它不等于 Vivado 综合、
时序收敛或全 4,308-timestep 生物学协议已经通过。单引擎在 100 MHz 下不能覆盖本测试的
峰值 timestep；下一步优化应减少每 edge 的流水周期或增加受控并行度。

protocol lock: `e16591cf464a6ce1f031e5b8f6c90c7437b7cfd7c012eed9e5d9ed0e3c2c7829`
