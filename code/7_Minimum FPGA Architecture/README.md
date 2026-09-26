# Step 7 — Minimum FPGA Architecture

本目录实现单 PE、事件驱动、时间复用的最小 CNS2FPGA RTL。第一版全部面向片上 BRAM，
不使用 DDR、NoC 或多 PE。输入文件来自第六步 `cns2fpga.hardware_ir`。

目录：

- `rtl/cns2fpga_core.sv`：neuron update、spike queue、CSR propagation 和饱和诊断；
- `sim/tb_cns2fpga_core.sv`：两神经元一周期传播自检；
- `sim/fixtures/`：最小 `.mem` 测试镜像；
- `docs/architecture_v1.md`：执行语义、边界和周期模型。

ModelSim 运行：

```powershell
vsim -c -do sim/run_modelsim.do
vsim -c -do sim/run_full_image_load.do
```

测试必须分别输出 `PASS two-neuron one-cycle propagation` 和 `PASS full image load`。
