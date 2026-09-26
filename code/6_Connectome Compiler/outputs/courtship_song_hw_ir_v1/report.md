# CNS2FPGA Hardware IR v1 compile report

**PASS：冻结的 courtship-song IR 已编译为可回读的 FPGA 十六进制存储镜像。**

- neurons: 6,279
- synapses: 350,185
- input mappings: 93
- fixed format: `safe_wf24` (`safe` role)
- logical storage: 23,518,944 bits
- BRAM36 aggregate lower bound: 638
- BRAM36 with each file independently allocated: 641
- round-trip checks: 8/8 PASS

`synapse.mem` 以 CSR source 顺序保存 post index 和二补码权重；pre index 由
`offset.mem` 的 start/count 隐式确定。`.mem` 文件为定宽大写十六进制，每行一条记录。
BRAM 数为逻辑容量估算，不含双口复制、跨宽拼接损耗、事件队列和控制缓冲。

protocol lock: `c5673c0e76b3443a01c102ca1c0331f18c90e3804f91ae9425230a62301f237c`
