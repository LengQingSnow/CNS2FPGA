# CNS2FPGA Hardware IR v1 compile report

**PASS：冻结的 courtship-song IR 已编译为可回读的 FPGA 十六进制存储镜像。**

- neurons: 226
- synapses: 1,730
- input mappings: 220
- fixed format: `safe_wf24` (`safe` role)
- logical storage: 154,528 bits
- BRAM36 aggregate lower bound: 5
- BRAM36 with each file independently allocated: 9
- round-trip checks: 8/8 PASS

`synapse.mem` 以 CSR source 顺序保存 post index 和二补码权重；pre index 由
`offset.mem` 的 start/count 隐式确定。`.mem` 文件为定宽大写十六进制，每行一条记录。
BRAM 数为逻辑容量估算，不含双口复制、跨宽拼接损耗、事件队列和控制缓冲。

protocol lock: `080f46463cd66f0e3b5ccd2dbce80b997d24c786b3d7ebad01ef480c5aec20c2`
