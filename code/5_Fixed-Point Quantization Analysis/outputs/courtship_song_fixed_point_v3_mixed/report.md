# Courtship-song 定点化分析（v0）

本轮使用整数运算重放 9 个完整 IPI 条件及 35 ms 下 8 种回路干预。浮点事件只作为锁定参考，没有修改第四步结果。

## 结论

- 状态：`PASSING_FORMATS_FOUND`
- safe：`safe_s34w36a41`
- compact：`precision_boundary_s33w35a39`

验收要求：关键群体完整条件最大响应放电误差 ≤5%，8/8 个 pC1 调谐方向一致，24/24 个干预方向一致，且无运行时饱和。

## 格式汇总

| format_name | max_key_response_error_percent | tuning_direction_agreements | tuning_direction_comparisons | intervention_direction_agreements | intervention_direction_comparisons | state_saturation_events | accumulator_saturation_events | acceptance_pass | state_bits | state_frac | weight_bits | weight_frac | decay_bits | decay_frac | accumulator_bits | weight_quantization_saturations | decay_quantization_saturations |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| safe_s34w36a41 | 0 | 8 | 8 | 24 | 24 | 0 | 0 | True | 34 | 24 | 36 | 30 | 32 | 30 | 41 | 0 | 0 |
| compact_s33w36a40 | 0 | 8 | 8 | 24 | 24 | 0 | 0 | True | 33 | 24 | 36 | 30 | 32 | 30 | 40 | 0 | 0 |
| state_boundary_s32w36a40 | 0 | 8 | 8 | 24 | 24 | 673 | 0 | False | 32 | 24 | 36 | 30 | 32 | 30 | 40 | 0 | 0 |
| precision_boundary_s33w35a39 | 0 | 8 | 8 | 24 | 24 | 0 | 0 | True | 33 | 24 | 35 | 29 | 32 | 30 | 39 | 0 | 0 |

精确逐事件 F1 用于诊断，不作为群体级 FPGA 保真度的唯一门槛。当前结果是工程量化结论，不提高第四步的生物学证据等级。

protocol lock: `408ce78674e0bf27621ad4d0131a9d5d08403a985a9c5ac8dd532ee72d2c033f`
