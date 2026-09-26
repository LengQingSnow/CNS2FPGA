# CPU–RTL 逐周期对拍契约 v1

对拍使用完整 courtship-song 硬件镜像和第五步 `safe_wf24` 格式。初始状态为零，连续输入
3 个幅度 1.2 的 timestep，随后 5 个零输入 timestep。

每个 timestep 完成后，对全部 6,279 个神经元比较：

- spike bit；
- reset 后的膜电位 S34.24；
- 已为下一 timestep 累积的突触电流 S35.24；
- 8 位 refractory counter；
- 状态和累加器饱和标志。

RTL 静态图来自第六步 `.mem`，CPU 参考从第二步表重新量化。参考数据按
`address = timestep × 6279 + neuron_index` 展平，测试平台不允许容差：任何一位差异均失败。

同步访问流水线为：

- neuron update：`READ → EXEC`，2 cycles/neuron；
- spike offset：queue、offset read/execute，3 cycles/spike；
- synapse accumulation：edge read、accumulator read、write，3 cycles/edge。

这一定义验证功能和整数时序语义，不代替 Vivado 综合、静态时序或板上验证。
