# Courtship-song 定点化分析（v0）

本轮使用整数运算重放 9 个完整 IPI 条件及 35 ms 下 8 种回路干预。浮点事件只作为锁定参考，没有修改第四步结果。

## 结论

- 状态：`NO_FORMAT_MET_ALL_ACCEPTANCE_GATES`
- safe：`None`
- compact：`None`

验收要求：关键群体完整条件最大响应放电误差 ≤5%，8/8 个 pC1 调谐方向一致，24/24 个干预方向一致，且无运行时饱和。

## 格式汇总

| format_name | max_key_response_error_percent | tuning_direction_agreements | tuning_direction_comparisons | intervention_direction_agreements | intervention_direction_comparisons | state_saturation_events | accumulator_saturation_events | acceptance_pass | state_bits | state_frac | weight_bits | weight_frac | decay_bits | decay_frac | accumulator_bits | weight_quantization_saturations | decay_quantization_saturations |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| q34_refined | 5.66038 | 8 | 8 | 24 | 24 | 0 | 0 | False | 34 | 22 | 34 | 28 | 32 | 30 | 62 | 0 | 0 |
| q32_refined | 18.1818 | 8 | 8 | 24 | 24 | 0 | 0 | False | 32 | 20 | 32 | 26 | 32 | 30 | 60 | 0 | 0 |
| q30_refined | 5.66038 | 8 | 8 | 24 | 24 | 0 | 0 | False | 30 | 18 | 30 | 24 | 30 | 28 | 58 | 0 | 0 |
| q28_refined | 54.717 | 8 | 8 | 22 | 24 | 0 | 0 | False | 28 | 16 | 28 | 22 | 28 | 26 | 56 | 0 | 0 |

精确逐事件 F1 用于诊断，不作为群体级 FPGA 保真度的唯一门槛。当前结果是工程量化结论，不提高第四步的生物学证据等级。

protocol lock: `2223f35d3b670500fea21d278077facc5f8fd3d05c16097da29d3ddf9861cbe2`
