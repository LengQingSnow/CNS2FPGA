# KU115 195 MHz 实现结果

> 说明：本文是板卡型号确认前的 OOC 初步记录，使用临时候选器件
> `xcku115-flva1517-2-e`。最终权威板级结果采用实际器件
> `xcku115-flva1517-2-i`，见 `axku115_bitstream_result.md`。

## 结论

当前 RTL 在临时候选器件 `xcku115-flva1517-2-e` 上完成 OOC 综合、布局和完整路由，
195 MHz 时序通过。该结果可作为板级集成前的实现基线；尚不能替代带真实管脚约束的板级
bitstream 构建。

## 功能与实时性

| 项目 | 结果 |
|---|---:|
| 神经元 | 6279 |
| 突触 | 350185 |
| bit-exact 检验 | 8 timestep，0 mismatch |
| 仿真错误/警告 | 0 / 0 |
| 最坏 timestep | 192784 cycles |
| 195 MHz 最坏耗时 | 988.636 us |
| 1 ms 余量 | 11.364 us |

最坏周期数来自 `sim/bit_exact_250mhz_transcript.log`。文件名保留了流水化 RTL 最初的
250 MHz 开发目标，不表示最终实现频率；同一 RTL 当前通过的实现频率是 195 MHz。

## 布局布线时序

约束：周期 `5.128 ns`，用户时钟不确定度 `0.200 ns`。

| 指标 | 结果 |
|---|---:|
| WNS | +0.142 ns |
| TNS | 0.000 ns |
| setup failing endpoints | 0 |
| WHS | +0.031 ns |
| THS | 0.000 ns |
| 未布线网络 | 0 |
| 部分路由网络 | 0 |
| 路由节点重叠 | 0 |

200 MHz 的完整路由结果为 WNS `-0.097 ns`、TNS `-0.559 ns`、10 个 setup failing
endpoints，因此没有把 200 MHz 标记为通过。195 MHz 使用默认、可重复的稳定实现流程，
没有依赖放宽时钟不确定度。

## 资源

| 资源 | 使用 | KU115 可用 | 利用率 |
|---|---:|---:|---:|
| RAMB36 | 504 | 2160 | 23.33% |
| DSP48E2 | 4 | 5520 | 0.07% |
| LUT as logic | 1891 | 663360 | 0.29% |
| LUT as distributed RAM | 4937 | 293760 | 1.68% |
| CLB registers | 789 | 1326720 | 0.06% |

按此前提出的 625 个 BRAM36 工程预算计算，504 个已满足预算，尚余 121 个。实际候选
KU115 器件本身有 2160 个 RAMB36。

## 产物与可追溯性

- routed checkpoint：`build/ooc_195mhz/post_route.dcp`
- timing：`reports/ooc_195mhz/post_route_timing_summary.rpt`
- utilization：`reports/ooc_195mhz/post_route_utilization.rpt`
- methodology：`reports/ooc_195mhz/methodology.rpt`
- machine-readable status：`reports/ooc_195mhz/run_status.txt`

关键 SHA-256：

```text
81BFDF69285733F07DCEDCF178C548E3F4303A618E244EDDE71A684EBF484101  rtl/cns2fpga_core_sync_250mhz.sv
F7DFD6DFFFA1071F02EBD2F9956A56160DDD2EA860B6ADB84950406B76DE2D49  rtl/cns2fpga_ku115_ooc_top.sv
DE573FB58A710F15DFF4DEAB6340AC8B4A130DBA406626618D52E1856B932E04  constraints/core_195mhz_ooc.xdc
BB3B084A4C52C66CCF8315A8CB4C0A2892AD44D1EC90EE9EEE1D07822F7AD4B5  build/ooc_195mhz/post_route.dcp
C31854A6D57620B36F50B2CCC0BE5DBD45E84EA0A014C19BFE387EBA5FB308EF  neuron_param.mem
562DC194AAC0C594AB2EFF6626951AE6BADB406973B19C98FAE8961B152A1A87  synapse.mem
DC168DA0C07111411AB5800842463EA6B0E414755E37C9FFE3ECBE4F88BBE2CC  offset.mem
CBACFA8B11ECD855F844F845BF51078F28BFF6DC4D216169C3D4A48C30660A2C  type_sign.mem
```

## 为什么尚无 `.bit`

OOC wrapper 的外部端口没有板卡 I/O pin、IOSTANDARD 和真实时钟源约束；方法学报告中的
输入/输出 delay 警告也来自这一事实。当前工程中也没有找到能确认实际板卡型号的官方
XDC。此时强行降低 `UCIO-1`/`NSTD-1` DRC 严重性只能得到不可安全上板的文件。

下一步必须先取得准确板卡型号或官方 master XDC，再建立板级 top（时钟/MMCM、复位同步、
控制接口），重新执行板级综合、布局布线、DRC 和 `write_bitstream`。
