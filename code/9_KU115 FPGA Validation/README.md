# Step 9 — KU115 FPGA Validation

本目录包含 AXKU115 的时序实现、JTAG 刺激/读回、板上试次和参考对拍。

## 当前可写刺激版（CNS9）

- 器件：ALINX AXKU115 V1.0，`xcku115-flva1517-2-i`。
- 核心时钟：200 MHz；每个模型 timestep 对应 200000 个时钟。
- bitstream：`build/axku115_jtag_200mhz/cns2fpga_axku115_jtag_200mhz.bit`，已烧录并识别到 `hw_axi_1`。
- 完成布线后的 setup WNS `+0.073 ns`、hold WHS `+0.030 ns`、未布线网络 0、DRC 错误 0、JTAG CDC 总线偏斜通过。
- 约束为额外 setup 不确定度 200 ps、hold 不确定度 50 ps；早期统一 200 ps 约束导致 JTAG IP 内同片区 FIFO 路径出现人为 hold 违例，详见 `reports/axku115_jtag_200mhz/`。
- 板级资源：589 RAMB36E2、3 RAMB18E2、4 DSP48E2；XCKU115 器件提供 2160 个 RAMB36/FIFO 位点。
- 8 步实测：2475 个 `(timestep, neuron_index)` 事件按顺序与冻结 CPU 参考完全一致；最慢步 199063 周期（995.315 µs），无超时/饱和/溢出。
- 35 ms IPI 实测：4308 步，vPN1/pC1/pIP10/pMP2 响应窗计数 222/1735/109/9，与冻结参考一致，四类诊断标志均为 0。
- 15–95 ms（每隔 10 ms）共 9 个 IPI 条件全部通过板上对拍；累计 38772 个 timestep 无超时、饱和或溢出。

完整签核与实测表见 `docs/board_validation_200mhz.md`；机器可读的九组汇总在 `host/captures/sweep_response_200mhz.csv`；主机协议与复现命令见 `docs/host_protocol.md`；板上原始文件在 `host/captures/`。

## 历史基线：195 MHz 零输入自检版

- 最终开发板：ALINX AXKU115 V1.0
- 实际器件：`xcku115-flva1517-2-i`（XCKU115-2FLVA1517I）
- 该历史板级 bitstream：已生成
- 当时通过目标：`195 MHz`（50 MHz 板载晶振经 MMCM 生成）
- 板级布局布线：PASS，WNS `+0.074 ns`，TNS `0.000 ns`
- 板级 DRC：0 errors，6 个 DSP 流水线建议 warning
- 195 MHz OOC 布局布线：PASS，WNS `+0.142 ns`，TNS `0.000 ns`
- 200 MHz OOC 布局布线：未通过，WNS `-0.097 ns`
- 最坏步耗时：`192784 / 195 MHz = 988.636 us`，低于 `1 ms`
- 完整网络仿真：6279 个神经元、350185 条突触、8 个 timestep、0 mismatch
- 该历史版本资源：503 RAMB36、4 DSP、2009 logic LUT、4949 distributed-RAM LUT、691 registers
- 前期 OOC 通用输入版本使用 504 RAMB36；板级零输入自检版因常量优化减少为 503

详细证据见 `docs/axku115_bitstream_result.md` 和
`docs/implementation_result_195mhz.md`。

## 复现

```powershell
cd 'E:\Workspace\CNS2FPGA\code\9_KU115 FPGA Validation'
.\run_ooc_impl.ps1 -TargetMHz 195
```

`run_ooc_impl.ps1` 支持 195、200 和 250 MHz；这些是历史零输入/OOC 基线，不能替代上面的 CNS9 JTAG bitstream。

## bitstream 状态

历史零输入自检文件：

`build/axku115_195mhz/cns2fpga_axku115_195mhz.bit`

完整复现：

```powershell
.\run_axku115_bitstream.ps1
```

板级自检操作：KEY1 为低有效复位；按下 KEY2 启动一个 timestep；LED1 在 busy 或检测到
饱和错误时亮；LED2 在 timestep 完成后翻转，并混入 spike 活动签名。该 bitstream 的
`input_current` 固定为零，定位是第一版板级计算/时钟/存储自检，不包含主机运行时输入接口。
