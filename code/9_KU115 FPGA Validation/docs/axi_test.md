# AXI4-Lite adapter 独立仿真

测试对象为 `rtl/cns2fpga_axi_lite_slave.sv`，测试平台为 `sim/tb_axi_lite_slave.sv`。测试平台用有延迟的同步 bus 模型代替 trial engine，仅检验 AXI4-Lite 适配器协议与 bus 请求；它不替代完整试次或上板 JTAG 测试。

## 已执行的测试

ModelSim SE-64 2020.4：`vlog -sv` 编译 0 error、0 warning；`vsim -c` 运行至 1170 ns，打印 `PASS AXI4-LITE AW/W order, sequential reads/writes, backpressure, SLVERR, WSTRB, blocked writes`，退出码 0。

| 场景 | 验收条件 | 结果 |
| --- | --- | --- |
| AW 先于 W | W 未到时无 bus 写/B 响应；两通道齐备后只写一次 | PASS |
| W 先于 AW | AW 未到时无 bus 写/B 响应；地址与数据不串单 | PASS |
| AW/W 同拍与四次连续写 | 每次仅一个 bus 写，地址与数据顺序正确 | PASS |
| BREADY 延迟 | BVALID/BRESP 稳定，等待期间不再接收新 AW/W | PASS |
| 同步读延迟与 RREADY 延迟 | bus 返回数据前无 RVALID；RVALID/RDATA/RRESP 稳定到握手 | PASS |
| 三次连续读 | 地址与返回数据逐项匹配，无丢失 | PASS |
| 读写同时发生 | 读与写都完成，互不覆盖 | PASS |
| 高于 20 位地址范围 | 写 BRESP=SLVERR 且无 bus 写；读 RRESP=SLVERR、数据零且无 bus 读 | PASS |
| 非 `4'hf` WSTRB（含零） | BRESP=SLVERR，不把写请求送往 engine | PASS |
| `write_blocked=1` 时写 | BRESP=SLVERR，bus 无写脉冲；解除阻塞后正常写可继续 | PASS |

## 复现

在 PowerShell 中使用独立的临时运行目录，避免 ModelSim 的 `work` 和 `transcript` 覆盖现有实验记录：

```powershell
$axiRunDir = Join-Path $env:TEMP 'cns2fpga_axi_lite_qa'
New-Item -ItemType Directory -Force -Path $axiRunDir | Out-Null
Set-Location -LiteralPath $axiRunDir
vlib work
vlog -sv 'E:\Workspace\CNS2FPGA\code\9_KU115 FPGA Validation\rtl\cns2fpga_axi_lite_slave.sv' 'E:\Workspace\CNS2FPGA\code\9_KU115 FPGA Validation\sim\tb_axi_lite_slave.sv'
vsim -c tb_axi_lite_slave -do 'onerror {quit -code 1}; run -all; quit -code 0'
```

## 接口边界

适配器将顶层的 `trial_running` 作为 `write_blocked`：试次运行时所有 AXI 写返回 SLVERR，且不会到达 trial engine。适配器同时检查地址高 12 位和 WSTRB 是否全字；20 位地址范围内由 trial engine 解释。20 位范围内未映射读地址目前返回零与 OKAY；若要以 SLVERR 检出主机地址错误，需要扩展 bus 错误反馈。这一点不是本独立总线仿真的通过项。
