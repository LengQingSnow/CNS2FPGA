# 250 MHz implementation target

后续 KU115 实现采用 **250 MHz / 4.000 ns** 作为首选时钟目标，并预留
`0.200 ns` clock uncertainty。约束文件为
`constraints/cns2fpga_250mhz.xdc`。

第八步观测到的峰值为 `167,668 cycles/timestep`，因此在理想 250 MHz
时钟下：

- 峰值计算时间：`670.672 us`
- 1 ms 截止时间余量：`329.328 us`
- 截止时间利用率：`67.0672%`

这里的 `PASS` 仅表示周期预算满足 1 ms，不表示 250 MHz 已经时序收敛。
是否能在 KU115 上实际达到 250 MHz，必须以确定器件型号后的 Vivado
place-and-route `WNS >= 0` 为准。
