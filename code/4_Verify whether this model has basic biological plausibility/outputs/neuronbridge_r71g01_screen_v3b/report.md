# R71G01 NeuronBridge 搜索结果审计（v3）

**结论：MORPHOLOGY_CANDIDATE_OUTSIDE_FROZEN_SUBCIRCUIT。**

18 份用户导出的雄性 Brain R71G01 MCFO 查询表包含明确标成 MaleCNS `pC1*` 的候选；该结果是 R71G01 图像到 EM 形态的候选证据，不是 Zhou 2015 的 R71G01-LexA∩dsxGAL4 交集，也不是钙成像 ROI 的直接定义。

## 被明确标为 MaleCNS pC1 的候选

| bodyId | explicit_hit_count | all_result_appearances | best_explicit_rank | best_any_rank | best_explicit_score | best_any_score | type | instance | somaSide | fruDsx | in_frozen_ir |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 10217 | 1 | 3 | 2135 | 1466 | 1101.2965 | 2729.3433 | pC1x_b | pC1x_b_L | L | dsx_high | False |

`explicit_male_pc1_hits.csv` 保留每个显式命中行；`all_candidate_appearances.csv` 也保留同一 bodyId 在其他通道的未标注出现，用于复查一致性。未标注出现不能独自升级为 pC1 证据。

## 对当前模型的影响

候选共有 1 个，其中当前冻结 IR 内为 0 个。因为 strict importer 只接受当前冻结 IR 内的 bodyId，本批候选不能导入当前模型；不能据此修改或冻结 Golden Model。

如果要研究该形态候选，需新建并独立锁定扩展子电路版本，随后再检查它与 IPI 输入、vPN1/mAL 机制和原读出群的连接关系。即便扩展成功，仍须获得 `R71G01∩dsx` 或 ROI 的直接证据，才能称为实验 ROI 映射。

## 来源与可追溯性

查询来源：用户在 NeuronBridge 以 R71G01 的 FlyLight Gen1 MCFO 雄性 Brain 资料进行的 6 个切片 × 3 通道搜索；原始 CSV 的哈希在 `protocol_lock.json`。完整 MaleCNS 注释版本与冻结 IR 同样已锁定。

lock: `d9aaadf3baf0b442713a5d3cb448221bf4fd68251f85a3e16c3cc55da7c52cb4`。