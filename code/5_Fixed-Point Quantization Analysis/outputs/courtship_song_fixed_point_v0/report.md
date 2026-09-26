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
| wide_q24 | 40.3226 | 7 | 8 | 15 | 24 | 0 | 0 | False | 24 | 14 | 24 | 18 | 24 | 22 | 48 | 0 | 0 |
| q18 | 80 | 7 | 8 | 6 | 24 | 0 | 0 | False | 18 | 9 | 18 | 12 | 18 | 16 | 36 | 0 | 0 |
| q16 | 109.091 | 8 | 8 | 6 | 24 | 0 | 0 | False | 16 | 7 | 16 | 10 | 16 | 14 | 32 | 0 | 0 |
| q14 | 90.4 | 4 | 8 | 11 | 24 | 0 | 0 | False | 14 | 5 | 14 | 8 | 14 | 12 | 30 | 0 | 0 |
| q12 | 96.3115 | 7 | 8 | 7 | 24 | 492 | 0 | False | 12 | 4 | 12 | 6 | 14 | 12 | 28 | 0 | 0 |
| q8 | 372.277 | 3 | 8 | 13 | 24 | 527902 | 0 | False | 8 | 0 | 8 | 2 | 10 | 8 | 20 | 0 | 0 |

精确逐事件 F1 用于诊断，不作为群体级 FPGA 保真度的唯一门槛。当前结果是工程量化结论，不提高第四步的生物学证据等级。

protocol lock: `64d61ea2c52d72603ea628a73fd01101d5f9474f00dbd6391b07d96b63d56775`
