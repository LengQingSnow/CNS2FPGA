# pC1 候选读出鲁棒性审计（v3d）

**结论：已完成读出集合敏感性分析；结果用于判断工程结论对 pC1 定义的依赖程度，不构成实验 ROI 映射或新的生物学通过判定。**

本审计从 81 个锁定事件文件重算 6 个 pC1 候选集合的群体活动，共生成 486 条条件×IPI×读出摘要；新增仿真为 0。所有 81 个文件中，全体 pC1 事件重算均与原存档 `pC1_counts` 逐时间步完全一致。

## 候选集合

| candidate_id | neurons |
| --- | --- |
| pC1_type_all | 112 |
| pC1_fruDsx_nonmissing | 111 |
| pC1_fruDsx_coexpress | 65 |
| pC1_pMP_alias | 63 |
| pC1_neuronbridge_any_hit | 107 |
| pC1_neuronbridge_best_rank_le_100 | 15 |

NeuronBridge 任意命中和最佳名次≤100子集来自 R71G01 MCFO 搜索，只用于敏感性分析；其他三个子集来自注释字段。任何集合都未被标记为 Zhou 2015 的 R71G01∩dsx 或钙成像 ROI。

## 与全体 pC1 的一致性

| candidate_id | tuning_agreements | tuning_comparisons | tuning_agreement_fraction | intervention_35ms_direction_agreements | intervention_35ms_direction_comparisons | intervention_35ms_direction_agreement_fraction |
| --- | --- | --- | --- | --- | --- | --- |
| pC1_fruDsx_coexpress | 6 | 8 | 0.75 | 23 | 24 | 0.958 |
| pC1_fruDsx_nonmissing | 8 | 8 | 1 | 24 | 24 | 1 |
| pC1_neuronbridge_any_hit | 7 | 8 | 0.875 | 24 | 24 | 1 |
| pC1_neuronbridge_best_rank_le_100 | 4 | 8 | 0.5 | 16 | 24 | 0.667 |
| pC1_pMP_alias | 6 | 8 | 0.75 | 23 | 24 | 0.958 |
| pC1_type_all | 8 | 8 | 1 | 24 | 24 | 1 |

调谐一致性比较固定的 35 ms 对 15、25、85、95 ms，并同时检查 100-ms 峰值和每脉冲累计放电。干预一致性比较 35 ms 下 8 类 vPN1/aPN1/mAL 干预的三种指标方向。分数 1.0 表示方向模式与全体 pC1 完全一致；它不表示与实验完全一致。

## 产物

- `candidate_membership.csv`：112 个冻结 pC1 对六个候选集合的成员关系。
- `response_summary.csv`：全部重算读出。
- `tuning_checks.csv` / `intervention_effects.csv`：IPI 和干预敏感性。
- `candidate_tuning.png` / `intervention_effects_35ms.png`：可视化。
- lock: `3d202b1f04743098e84bcbb27658ec09e4b795fb263d5921ecfc5948fb0d2932`。