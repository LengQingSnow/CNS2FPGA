# Step 8 — RTL Bit-Exact Co-Simulation

本目录把第七步功能 RTL 改为显式同步存储流水线，并与第五步 CPU 定点语义进行完整状态对拍。

运行：

```powershell
$py = 'C:\Users\20474\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
& $py '.\generate_reference.py'
vsim -c -do sim/run_bit_exact.do
```

验收输出必须包含 8 个 `PASS timestep`，以及
`PASS BIT-EXACT full-network timesteps=8 neurons=6279`。
