# R71G01 NeuronBridge 搜索结果审计（v3）

**结论：MORPHOLOGY_CANDIDATE_OUTSIDE_FROZEN_SUBCIRCUIT。**

18 份用户导出的雄性 Brain R71G01 MCFO 查询表包含明确标成 MaleCNS `pC1*` 的候选；该结果是 R71G01 图像到 EM 形态的候选证据，不是 Zhou 2015 的 R71G01-LexA∩dsxGAL4 交集，也不是钙成像 ROI 的直接定义。

## 被明确标为 MaleCNS pC1 的候选

| bodyId | explicit_hit_count | best_explicit_rank | best_explicit_score | type | instance | somaSide | fruDsx | in_frozen_ir |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 10217 | 1 | 2135 | 1101.2965 | pC1x_b | pC1x_b_L | L | dsx_high | False |

`explicit_male_pc1_hits.csv` 保留每个显式命中行。一个 bodyId 的其他未标注结果可用来复查一致性，但不能独自升级为 pC1 证据。

## 对当前模型的影响

候选共有 1 个，其中当前冻结 IR 内为 0 个。因为 strict importer 只接受当前冻结 IR 内的 bodyId，本批候选不能导入当前模型；不能据此修改或冻结 Golden Model。

如果要研究该形态候选，需新建并独立锁定扩展子电路版本，随后再检查它与 IPI 输入、vPN1/mAL 机制和原读出群的连接关系。即便扩展成功，仍须获得 `R71G01∩dsx` 或 ROI 的直接证据，才能称为实验 ROI 映射。

## 来源与可追溯性

查询来源：用户在 NeuronBridge 以 R71G01 的 FlyLight Gen1 MCFO 雄性 Brain 资料进行的 6 个切片 × 3 通道搜索；原始 CSV 的哈希在 `protocol_lock.json`。完整 MaleCNS 注释版本与冻结 IR 同样已锁定。

lock: `e8663dd5baac5d53a73641af2c9b1db8d0d0444df0604ab7bb434d2976c139e9`。