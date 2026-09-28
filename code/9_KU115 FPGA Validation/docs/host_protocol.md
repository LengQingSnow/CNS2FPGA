# Step 9 主机刺激与回读协议（CNS9 v1）

## 冻结的输入

- 固定点格式：第 5 步 `safe_wf24`，有符号 34 位，24 位小数，最近舍入、正好半位时远离零。
- 每个 1 ms timestep 给 93 个 `is_input` 神经元同一个 `input_current`。
- 8 步功能试验：`[1.2, 1.2, 1.2, 0, 0, 0, 0, 0]`，生成的 `stimulus.mem` 与第 8 步参考文件逐字节一致。
- IPI 试验：15/25/35/45/55/65/75/85/95 ms，每个条件 40 个脉冲，宽 3 ms，幅度 1.2，从 100 ms 开始，每次 4308 步。各条件开始前需复位核心神经状态。

`host/step9_host.py generate` 对每个试验写出：

| 文件 | 格式 |
| --- | --- |
| `stimulus.mem` | 每行一个 9 位十六进制的 34 位补码；与 RTL `$readmemh` 一致 |
| `stimulus_words.bin` | 每步 8 字节：little-endian uint32 低位字，再接 little-endian uint32 高位字；高位字只用 bit[1:0] |
| `stimulus_words.csv` | 每步的 raw34、low32、high2 人可读值 |
| `metadata.json` | 源文件与产物 SHA-256、定点格式、脉冲时刻和响应窗 |

正电流 `1.2` 编码为 `001333333`，低字 `01333333`、高字 `0`。短试验还附带冻结的 `expected_spike.mem`。

## AXI 地址（字节地址，32 位数据）

| 地址 | 名称 | 语义 |
| --- | --- | --- |
| `0x0000` | ID | `0x434E5339`，ASCII `CNS9` |
| `0x0004` | CTRL | bit0 写 1 启动试验 |
| `0x0008` | STATUS | bit0 running、bit1 done、bit2 any deadline miss、bit3 event overflow、bit4 fault sticky、bit5 clearing |
| `0x000C` | LENGTH | 本次 timestep 数，1–8192 |
| `0x0010` | PERIOD_CYCLES | 200000 对应 200 MHz 下的 1 ms |
| `0x0014` | COMPLETED_STEPS | 已完成 timestep 数 |
| `0x0018` | GLOBAL_EVENT_COUNT | 已写入事件 BRAM 的事件数 |
| `0x001C` | MISSED_STEPS | 超时步数 |
| `0x0020` | MAX_LATENCY | 最大一步周期数 |
| `0x0024/28` | TOTAL_SYNOPS low/high | 突触操作总数，64 位 |
| `0x002C` | CONFIG | bit0 记录逐 spike 事件 |
| `0x10000 + step×8` | stimulus low32 | 34 位输入的低 32 位 |
| `0x10004 + step×8` | stimulus high2 | 输入 bit[33:32] 位于读写数据 bit[1:0] |
| `0x20000 + step×32` | summary | 8 个 32 位字，见下表 |
| `0x60000 + event×4` | events | 低 13 位为神经元索引；最多 65536 个事件 |

Summary 的 8 个字：

| 字号 | 内容 |
| --- | --- |
| 0 | 本步延迟 cycles |
| 1 | 本步 synops |
| 2 | 高 16 位 aPN1、低 16 位全网络 spike 数 |
| 3 | 高 16 位 pC1、低 16 位 vPN1 |
| 4 | 高 16 位 pMP2、低 16 位 pIP10 |
| 5 | 高 16 位本步记录事件数、低 16 位 flags |
| 6 | 本步事件在全局事件 BRAM 中的起始位置 |
| 7 | 保留，必须为 0 |

Summary flags：bit0 state saturation、bit1 accumulator saturation、bit2 本步 deadline miss、bit3 event overflow。

## 操作命令

以下示例中的 Python 可换成当前环境的 Python 3.10+。本机 bundled Python 路径见第 8 步 README。`generate` 拒绝覆盖非空输出目录。

```powershell
$base = 'E:\Workspace\CNS2FPGA\code\9_KU115 FPGA Validation'
$py = 'python'
& $py "$base\host\step9_host.py" selftest
& $py "$base\host\step9_host.py" generate --profile smoke8 --output-dir "$base\host\trials"
& $py "$base\host\step9_host.py" generate --profile ipi --output-dir "$base\host\trials"
```

板上已经配置包含 CNS9 JTAG AXI 接口的 bitstream 后，用 PowerShell 包装脚本启动 Vivado Hardware Manager。包装脚本先核对源文件 SHA-256、路径和许可证，只在子进程中设置 `XILINXD_LICENSE_FILE`。`-ValidateOnly` 可在不连接板卡时检查命令。目标设备或 AXI 核有多个时，可以传入 `-TargetPattern`、`-DevicePattern`、`-AxisPattern`。Tcl 脚本检查固件 ID、每次 AXI 传输的完成与 OKAY 响应、完成步数和抽样刺激回读，然后把原始 AXI 字保存到独立目录。

```powershell
& "$base\host\run_jtag_trial.ps1" -TrialDir "$base\host\trials\smoke8" -CaptureDir "$base\host\captures\smoke8_raw" -CaptureEvents -ValidateOnly
& "$base\host\run_jtag_trial.ps1" -TrialDir "$base\host\trials\smoke8" -CaptureDir "$base\host\captures\smoke8_raw" -CaptureEvents
& $py "$base\host\step9_host.py" parse-dump --summary-words "$base\host\captures\smoke8_raw\summary_words.hex" --event-words "$base\host\captures\smoke8_raw\event_words.hex" --timesteps 8 --output-dir "$base\host\captures\smoke8_parsed"
& $py "$base\host\step9_host.py" compare-events --events "$base\host\captures\smoke8_parsed\events.csv"
```

`compare-events` 要求事件按 `(timestep, neuron_index)` 的完整硬件输出顺序与第 8 步参考完全一致；不仅比较总数。对于 IPI：

```powershell
& "$base\host\run_jtag_trial.ps1" -TrialDir "$base\host\trials\ipi_35" -CaptureDir "$base\host\captures\ipi_35_raw"
& $py "$base\host\step9_host.py" parse-dump --summary-words "$base\host\captures\ipi_35_raw\summary_words.hex" --timesteps 4308 --output-dir "$base\host\captures\ipi_35_parsed"
& $py "$base\host\step9_host.py" compare-groups --counts "$base\host\captures\ipi_35_parsed\counts.csv" --ipi-ms 35
```

`compare-groups` 对 `[100 ms, 最后脉冲结束 + 500 ms)` 内 vPN1、pC1、pIP10、pMP2 的 spike 计数，与第 5 步 `safe_wf24 / intact` 冻结表中的 `fixed_response_spikes` 逐组比较，同时要求饱和、超时和事件溢出为 0。它提供群组汇总核对；完整 4308 步逐神经元事件核对需要足够大的事件存储和额外参考事件文件。

批量运行可用 `host/run_ipi_sweep.ps1`；默认运行 15、25、45、55、65、75、85、95 ms（35 ms 的独立试次示例如上），全新空抓取目录可用 `-IpiMs @(15,25,35,45,55,65,75,85,95)` 跑全部九组。重复测量请指定新的 `-CaptureTag`，例如 `-CaptureTag repeat1`，以保留原始捕获。每组会自动执行 `parse-dump` 和 `compare-groups`，一旦不一致就停止。

`run_jtag_trial.tcl` 当前为每个 AXI 字使用一个读写事务，兼容 AXI4-Lite。长试验的数据传输时间主要由 JTAG 速度决定，FPGA 内部周期计数仍是计算延迟的依据。

可写刺激的 JTAG 版使用 200 MHz 分级乘法流水线，8 步仿真最慢一步为 199063 周期（995.315 µs）；它与前期 195 MHz、输入固定为零的板级自检 bitstream 是两个不同设计，不能混用。

Vivado 命令与状态属性已在本机 Vivado 2021.2 `help` 核查；AMD [UG835 `reset_hw_axi`](https://docs.amd.com/r/2021.2-English/ug835-vivado-tcl-commands/reset_hw_axi) 也列出 `AXI_READ_DONE`、`AXI_WRITE_DONE`、`RRESP` 和 `BRESP`。
