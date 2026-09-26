# Step 5 — Fixed-Point Quantization Analysis

该目录把第三步浮点 LIF 模型转换为明确的整数运算契约，并使用第四步锁定的事件档案进行
量化误差、调谐方向和干预方向对比。它不会修改浮点模型，也不会提高生物学结论等级。

运算顺序固定为：上一周期 spike 传播、累加器饱和、权重到状态格式重量化、膜电位衰减、
加入突触与外部驱动、状态饱和、阈值判断与复位。所有量均为有符号整数；舍入为最近值且
中点远离零，溢出采用饱和。

运行：

```powershell
$py = 'C:\Users\20474\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
& $py '.\run_quantization_analysis.py'
& $py -m pytest -p no:cacheprovider '.\tests' -q
```

默认输出在 `outputs/courtship_song_fixed_point_v0`。已有非空目录不会被覆盖。

## 最终结果

最终边界扫描见
[`outputs/courtship_song_fixed_point_v6_final/report.md`](outputs/courtship_song_fixed_point_v6_final/report.md)。
在 17 个锁定条件（9 个完整 IPI + 35 ms 下 8 种干预）中：

- `safe`：状态 S34.24、权重 S30.24、衰减 S32.30、累加器 S35.24；
- `compact`：状态 S33.24、权重 S28.22、衰减 S32.30、累加器 S32.22；
- 两者均为 0 群体响应误差、8/8 调谐方向一致、24/24 干预方向一致、逐事件 F1=1，且无饱和；
- 权重降到 S27.21 后最大关键群体误差为 24.53%，因此拒绝；
- 状态降到 S32.24 时出现 673 次饱和，即使该批 spike 尚未改变也拒绝。

这里的 `compact` 表示本轮已验证搜索空间中的最小通过格式，不代表后续综合后的全局最小
硬件面积。衰减系数仍保守固定为 S32.30；如需继续压缩，应另建锁定扫描版本。
