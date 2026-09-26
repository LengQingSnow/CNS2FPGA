# CNS2FPGA Hardware IR v1 compile report

**PASS：冻结的 courtship-song IR 已编译为可回读的 FPGA 十六进制存储镜像。**

- neurons: 226
- synapses: 1,730
- input mappings: 109
- fixed format: `safe_wf24` (`safe` role)
- logical storage: 152,752 bits
- BRAM36 aggregate lower bound: 5
- BRAM36 with each file independently allocated: 9
- round-trip checks: 8/8 PASS

`synapse.mem` 以 CSR source 顺序保存 post index 和二补码权重；pre index 由
`offset.mem` 的 start/count 隐式确定。`.mem` 文件为定宽大写十六进制，每行一条记录。
BRAM 数为逻辑容量估算，不含双口复制、跨宽拼接损耗、事件队列和控制缓冲。

protocol lock: `eb2ebf9fca38d83818049b687fd151c63dd15ffa6d07edae3daabd9f85ffdc5a`
