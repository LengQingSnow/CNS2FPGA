# Courtship-song 定点化分析（v0）

本轮使用整数运算重放 9 个完整 IPI 条件及 35 ms 下 8 种回路干预。浮点事件只作为锁定参考，没有修改第四步结果。

## 结论

- 状态：`PASSING_FORMATS_FOUND`
- safe：`weight28_s33w34a38`
- compact：`weight26_s33w32a36`

验收要求：关键群体完整条件最大响应放电误差 ≤5%，8/8 个 pC1 调谐方向一致，24/24 个干预方向一致，且无运行时饱和。

## 格式汇总

| format_name | max_key_response_error_percent | tuning_direction_agreements | tuning_direction_comparisons | intervention_direction_agreements | intervention_direction_comparisons | state_saturation_events | accumulator_saturation_events | acceptance_pass | state_bits | state_frac | weight_bits | weight_frac | decay_bits | decay_frac | accumulator_bits | weight_quantization_saturations | decay_quantization_saturations |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| weight28_s33w34a38 | 0 | 8 | 8 | 24 | 24 | 0 | 0 | True | 33 | 24 | 34 | 28 | 32 | 30 | 38 | 0 | 0 |
| weight27_s33w33a37 | 0 | 8 | 8 | 24 | 24 | 0 | 0 | True | 33 | 24 | 33 | 27 | 32 | 30 | 37 | 0 | 0 |
| weight26_s33w32a36 | 0 | 8 | 8 | 24 | 24 | 0 | 0 | True | 33 | 24 | 32 | 26 | 32 | 30 | 36 | 0 | 0 |

精确逐事件 F1 用于诊断，不作为群体级 FPGA 保真度的唯一门槛。当前结果是工程量化结论，不提高第四步的生物学证据等级。

protocol lock: `48e15461e97a12ac3829ea943357fc51dc1a53e97b202ad5d59c96e0a7555a16`
