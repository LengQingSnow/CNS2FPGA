# AXKU115 195 MHz bitstream 结果

## 最终产物

- bitstream：`build/axku115_195mhz/cns2fpga_axku115_195mhz.bit`
- routed checkpoint：`build/axku115_195mhz/post_route.dcp`
- SHA-256（bit）：`268CF143F1A82C2676FCEA2CB1A32DD579496FDF7FB883F0EA9E6D3C148B755A`
- SHA-256（DCP）：`10A738B7651C7B8AE49A51C256FEEB3197099C194E914F2CA8E4294DC437E76B`
- bit 文件大小：14,069,947 bytes

## 板卡依据

用户手册确认开发板为 ALINX AXKU115，器件为工业级
`XCKU115-2FLVA1517I`，Vivado part 为 `xcku115-flva1517-2-i`。

板级自检采用手册明确标注的单端 50 MHz 晶振：

| 信号 | 管脚 | I/O 标准 | 用途 |
|---|---|---|---|
| FPGA_REFCLK / clk_50m | AL14 | LVCMOS33 | MMCM 参考输入 |
| KEY1 | AL33 | LVCMOS18 | 低有效复位 |
| KEY2 | AG30 | LVCMOS18 | 去抖后启动 timestep |
| LED1 | AH21 | LVCMOS18 | busy 或 fault latch |
| LED2 | AJ23 | LVCMOS18 | done toggle 与 spike 签名 |

Bank 24/44 是 HP Bank，Vivado DRC 明确拒绝 LVCMOS33；因此 KEY/LED 使用 LVCMOS18。
配置接口按手册的 3.3 V QSPI 电源设置为 `CFGBVS=VCCO`、
`CONFIG_VOLTAGE=3.3`。

## 时钟与时序

MMCM 参数：50 MHz × 19.5 / 5 = 195 MHz，VCO 为 975 MHz。

| 指标 | 结果 |
|---|---:|
| WNS | +0.074 ns |
| TNS | 0.000 ns |
| setup failing endpoints | 0 |
| WHS | +0.030 ns |
| THS | 0.000 ns |
| 未路由网络 | 0 |
| 部分路由网络 | 0 |
| 路由错误 | 0 |

最坏仿真 timestep 为 192784 cycles，即 195 MHz 下 988.636 us，保留 11.364 us
的 1 ms 预算余量。

## 资源

| 资源 | 使用 | KU115 可用 | 利用率 |
|---|---:|---:|---:|
| RAMB36 | 503 | 2160 | 23.29% |
| DSP48E2 | 4 | 5520 | 0.07% |
| LUT as logic | 2009 | 663360 | 0.30% |
| LUT as memory | 4949 | 293760 | 1.68% |
| CLB registers | 691 | 1326720 | 0.05% |
| MMCM | 1 | 24 | 4.17% |

板级输入电流固定为零后，综合器进行常量优化，因此本 bitstream 使用 503 个 RAMB36；
OOC 通用输入版本使用 504 个。两者都低于 625 个 RAMB36 的工程预算。

## DRC 与 warning 判定

最终 `write_bitstream`：0 errors、0 critical warnings。保留 6 个 DPOP warning：2 个
PREG 和 4 个 MREG 流水线建议。这些是 DSP 性能/功耗建议，不是连线、电气、时序或
bitstream 完整性错误；当前 195 MHz 已通过 setup/hold。继续增加 DSP 内部流水线会改变
周期行为，必须重新做 bit-exact 和 1 ms 预算验证，因此本版不为消除建议而修改算法时序。

## 上板行为

1. 通过 JTAG 下载 `.bit`。
2. KEY1 为低有效复位。
3. 按下 KEY2 并稳定约 5.38 ms 后，产生一个 timestep 启动脉冲。
4. LED1 在核心 busy 时点亮；若出现状态或累加器饱和则保持点亮。
5. LED2 在每个 timestep 完成后翻转，并混入 spike/pC1 活动签名。

这是最小板级自检 bitstream。它验证时钟、复位、网络 ROM/RAM、完整计算核心和状态输出，
但尚未加入 UART/以太网/PCIe/FMC 等主机接口，运行时输入电流固定为零。
