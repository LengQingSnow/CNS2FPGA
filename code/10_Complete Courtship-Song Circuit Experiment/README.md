# Step 10 — Complete Courtship-Song Circuit Experiment

本目录将已冻结的 MaleCNS courtship-song 子图、CPU 浮点模型、`safe_wf24` CPU 定点模型和 AXKU115 200 MHz bitstream 放在同一个输入协议下比较。没有修改模型参数或 FPGA RTL。

## 实验矩阵

- 9 个 IPI：15、25、35、45、55、65、75、85、95 ms；各 40 个 3 ms 脉冲，幅度 1.2。
- 2 个输入强度：在 35 ms IPI 下使用 0.8 和 1.4，其他条件不变。
- 1 个脉冲模式：20/50 ms 间隔交替，40 个等宽、等幅脉冲；与 35 ms IPI 有相同的平均间隔，但响应窗终点依实际最后脉冲计算。
- 1 个短时 raster：35 ms IPI 的前 8 个脉冲、350 ms，总事件量适合 FPGA 事件 BRAM。

长试次采用第九步的 8192-step stimulus BRAM 和逐毫秒摘要。9 个旧 IPI 的板上数据来自第九步，只重新计算 CPU 两端并校验其冻结档案；另外 4 个条件在第十步新采集。短时试次额外读出逐神经元事件。所有试次独立清空 FPGA 状态，不使用 DDR。

## 复现

```powershell
$py = 'C:\Users\20474\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
& $py '.\run_experiment.py' prepare
& '.\run_board_trials.ps1' -Python $py
& $py '.\run_experiment.py' analyze
& $py -m unittest discover -s '.\tests' -v
```

上述命令在本目录运行。`prepare` 不覆盖已有非空实验目录，JTAG 采集也拒绝覆盖已有捕获；重复实验请用新的 `--output` 路径，并相应修改采集脚本的 `$output`。板上执行前需连接并烧录第九步 `CNS9` bitstream。

结果在 `outputs/courtship_song_v1/`：`report.md`、5 张 PNG 图、`response_comparison.csv`、`latency_throughput.csv`、`resource_timing.json`、`short_spike_raster.csv`、协议锁、CPU 档案、刺激文件与新板上捕获。结果说明的是工程模型的浮点/定点/FPGA 一致性，不等于完成实验 ROI 的生物学映射验证。长试次没有完整 FPGA 逐神经元事件，不能据此声称长试次全事件对拍。
