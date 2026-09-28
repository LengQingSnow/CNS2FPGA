# Step 6 — CNS2FPGA Connectome Compiler

本目录把第二步冻结子图和第五步定点格式编译为独立于具体 RTL 实现的硬件 IR。默认选择
第五步的 `safe` 格式，并生成可供 Verilog/SystemVerilog `$readmemh` 使用的定宽十六进制文件。

默认产物：

- `neuron_param.mem`：阈值、复位、衰减、不应期、递质符号和锚点标记；
- `synapse.mem`：CSR 顺序的 post index 与定点权重；
- `offset.mem`：每个 pre neuron 的 edge start/count；
- `type_sign.mem`：输入、aPN1、vPN1、pC1、pIP10、pMP2 和递质符号位；
- `input_mapping.mem`：外部输入槽到 neuron index 的映射；
- `global_config.mem`、`cns2fpga_config.svh`：全局计数和 RTL 编译常量；
- `compiler_manifest.json`：版本化布局定义；
- `verification.csv`：从 `.mem` 解码回源表的逐字段检查。

运行：

```powershell
$py = 'python'
& $py '.\compile_hardware_ir.py'
& $py '.\verify_compiled_ir.py'
& $py -m pytest -p no:cacheprovider '.\tests' -q
```

默认输出为 `outputs/courtship_song_hw_ir_v1`；非空目录不会被覆盖。

当前 v1 结果为 23,518,944 个逻辑位；聚合容量下界为 638 个 BRAM36，各文件独立
分配时为 641 个 BRAM36。该数值尚未计入端口复制、宽度拼接损耗、事件队列和控制缓冲。
