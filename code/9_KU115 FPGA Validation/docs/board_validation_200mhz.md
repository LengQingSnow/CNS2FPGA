# Step 9：AXKU115 上板验证（CNS9，200 MHz）

日期：2026-09-25。板卡：ALINX AXKU115 V1.0，器件 `xcku115-flva1517-2-i`，JTAG 目标 `localhost:3121/xilinx_tcf/Digilent/210512180081`，器件 `xcku115_0`，JTAG AXI 核 `hw_axi_1`。Vivado 2021.2。

## 交付状态

已将 `build/axku115_jtag_200mhz/cns2fpga_axku115_jtag_200mhz.bit` 烧录到板卡，并完成 8 步逐神经元事件对拍及 9 个 IPI 的群组响应扫频。bitstream SHA-256：`0dfb8e09e9509c40cf5f48e616ddd3b31ccc279d03946446fbc21e80523a53a9`（15,488,180 字节）。输入文件的 SHA-256 写在各 `host/trials/*/metadata.json`，捕获文件的 SHA-256 写在各 `host/captures/*_parsed/capture_metadata.json`。

| 物理实现指标 | 结果 |
| --- | ---: |
| 时钟 | 200 MHz（50 MHz 板载晶振经 MMCM） |
| setup WNS / hold WHS | +0.073 ns / +0.030 ns |
| 额外 setup / hold uncertainty | 0.200 ns / 0.050 ns |
| 未布线 / 部分布线网络 | 0 / 0 |
| DRC 错误 | 0 |
| JTAG CDC bus-skew | 12 项均通过；见 `reports/axku115_jtag_200mhz/final_bus_skew.rpt` |
| RAMB36E2 / RAMB18E2 / DSP48E2 | 589 / 3 / 4 |
| XCKU115 可用 RAMB36/FIFO 位点 | 2160 |

上述数据来自 `reports/axku115_jtag_200mhz/final_status.txt`、`final_timing_summary.rpt`、`final_bus_skew.rpt`、`final_drc.rpt` 和 `post_route_utilization.rpt`。DRC 仍有 19 条非错误 warning，主要来自 Xilinx JTAG/FIFO IP 的 BRAM 碰撞与无负载网络提示；没有把 warning 写成 0。

最初用同一条 0.200 ns 用户 uncertainty 同时约束 setup 和 hold 时，setup 已通过但 JTAG IP 内部同片区 SRL→FF 路径 hold 为 −0.085 ns。普通及增强物理 hold 修复没有消除此类不可绕行短路径。最终设计把额外不确定度明确分项：setup 仍保留 0.200 ns，相关的同一 MMCM/BUFG 时钟域 hold 保留 0.050 ns 用户裕量；在这一约束下重新签核得到 WHS +0.030 ns。**原先更严的 0.200 ns hold 用户裕量并未通过**；若后续要求该裕量，需要重构或重放置 JTAG IP，而不能把本报告当作已达到该目标。

## 输入与测量

主机通过 JTAG AXI-Lite 向 FPGA 内 8192×34-bit stimulus BRAM 写入每个 1 ms 的电流值（低 32 位、高 2 位）。每步的同一输入施加给连接组中 93 个 `is_input` 神经元。格式为有符号 34 位、24 位小数，`1.2` 编码 `0x01333333`。每次开始前硬件顺序清空 6279 个神经元的电压、突触电流和不应期状态，防止试次串扰；没有使用 DDR。

FPGA 以 200000 个系统周期调度一个模型 timestep，硬件逐步记录核心完成周期、突触操作数、全网络 spike 数、aPN1/vPN1/pC1/pIP10/pMP2 群组 spike 数，以及饱和、超时和溢出标志。JTAG 往返时间仅影响装载和导出，不计入 FPGA 的步计算延迟。短试次启用事件 BRAM（最多 65536 项）记录逐神经元事件；长 IPI 试次仅导出每步摘要。

## 板上结果

8 步输入为 `[1.2, 1.2, 1.2, 0, 0, 0, 0, 0]`，与第 8 步刺激文件逐字节一致。两次独立板上运行完成；开启事件记录的一次读回 2475 个 `(timestep, neuron_index)` 事件，按输出顺序与冻结 CPU/RTL 参考全部相同，`first_difference=null`。8 步 spike 总数依次为 `93, 138, 322, 636, 616, 346, 227, 97`。最大延迟 199063 周期，即 995.315 µs；距 1 ms 界限还有 937 周期（4.685 µs）。状态 `0x00000002`、完成步数 8、超时 0、饱和 0、溢出 0。

IPI 刺激按冻结的第四/第五步协议：每条件 40 个脉冲、每脉冲宽 3 ms、幅度 1.2、首个起点 100 ms；条件为 15–95 ms、间隔 10 ms。每个条件运行 4308 步。下表为相应响应窗内板上 spike 数；九个条件均与第五步 `safe_wf24 / intact` 冻结值逐组相同。

| IPI (ms) | vPN1 | pC1 | pIP10 | pMP2 | 对拍 |
| ---: | ---: | ---: | ---: | ---: | :---: |
| 15 | 25 | 611 | 36 | 4 | PASS |
| 25 | 62 | 1020 | 62 | 4 | PASS |
| 35 | 222 | 1735 | 109 | 9 | PASS |
| 45 | 255 | 1910 | 121 | 11 | PASS |
| 55 | 236 | 2125 | 95 | 51 | PASS |
| 65 | 244 | 2326 | 83 | 57 | PASS |
| 75 | 244 | 2308 | 84 | 63 | PASS |
| 85 | 232 | 2180 | 101 | 53 | PASS |
| 95 | 250 | 2238 | 85 | 67 | PASS |

所有九组的状态寄存器都是 `0x00000002`，完成步数均为 4308，最大延迟均为 199063 周期；全部 38772 个 timestep 的 `state_saturation`、`accumulator_saturation`、`deadline_miss`、`event_overflow` 逐步标志均为 0。汇总表另存为 `host/captures/sweep_response_200mhz.csv`；已从各组 `counts.csv` 独立重算响应窗计数并核对一致。每条件独立的原始 `registers.csv`、`summary_words.hex` 和解析后的 `counts.csv` 在 `host/captures/ipi_<IPI>_summary*` 目录。

## 解读与边界

本次证明的是 AXKU115 板上执行与冻结的定点计算/刺激协议一致，不等于证明该回路模型与果蝇实验生物学结果一致。第四步所述驱动系/成像 ROI 到 MaleCNS 亚型的映射问题仍需独立证据；不能由 FPGA 对拍通过消除。200 MHz 下的最慢步距 1 ms 仅 4.685 µs，当前冻结刺激均无超时，但新刺激或更多活动模式必须继续监视 deadline 计数。IPI 扫频只对每步群组摘要做了冻结参考核对；逐神经元完整事件顺序的板上对拍范围是 8 步短试次。

复现入口：`host/run_jtag_trial.ps1`、`host/run_ipi_sweep.ps1`、`host/step9_host.py` 与 `docs/host_protocol.md`。抓取脚本拒绝覆盖已有目录；重复测量可给扫频脚本新的 `-CaptureTag`。
