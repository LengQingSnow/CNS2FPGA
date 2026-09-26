# v2：解释 v1 矛盾，不通过调参改变结论

## 为什么做

v1 中 pC1 的长 IPI 衰减依赖读出方式，且 vPN1 消融效应较弱。
进一步核查发现：MaleCNS 的 11 个 vPN1 均预测为 GABA 能神经元，IR 的
抑制符号与源数据一致。不能未经验证就把它们视为兴奋性串行中继。
v1 的因果方向要求是项目假设，而不是已验证的逐连接生物事实。

本轮分析在看到 v1 结果后设计，属于探索性机制诊断。v2 不替换 v1 的主读出，
不调整 gain、阈值、膜时间常数或神经递质符号，也不选择“最容易通过”的亚型。

## 代码分类

- `configs/courtship_song_mechanism_v2.json`：数据来源、干预设计、读出敏感性参数。
- `run_mechanism_diagnostics.py`：哈希核验、协议锁定、运行、审计与导出。
- `src/cns2fpga_plausibility/diagnostics_v2.py`：切边、图遍历、分组、观测代理等可测试函数。
- `src/cns2fpga_plausibility/reporting_v2.py`：图表和中文报告。
- `tests/test_mechanism_diagnostics.py`：单元测试。
- `outputs/courtship_song_mechanism_v2/`：本次锁定实验；不可覆盖。

## 执行协议

1. 核验 v1 锁定的所有原始输入和源代码；核对原始 NT feather 与 IR。
2. 固定 40 脉冲、9 个 IPI、原有刺激及模型参数。
3. 写入 v2 配置/分组/切边/源文件/输入哈希锁，再开始模拟。
4. 定义 A 为 vPN1→pC1 出边，B 为 vPN1→非 pC1 出边（包含 vPN1 自身相关边）。
   分别切 A、切 B、切 A+B；另做 aPN1 消融。每项跑全部 9 个 IPI，共 36 次刺激。
5. 复用 v1 完整网络和 vPN1 消融各 9 次，共 18 个事件文件。
   原版 v1 的文件内容本身未提供逐 NPZ 事先锁定哈希；v2 在本轮开始时锁定这些文件，
   并重跑完整网络 35 ms、逐事件核验一致，重新计算全部群体读出核对 v1 表格。
6. A+B 切断与 vPN1 神经元消融应在 vPN1 以外全部神经元上逐事件一致，逐 IPI 强制核验。
7. 完整网络、3 种切边和 aPN1 消融各跑 1 次零刺激检查，共 5 次静默。
8. 全部分组按注释/解剖定义：6 个原群组、pC1 直接受体/非直接受体、全部 type 和 fruDsx
   标签。报告全部单细胞、全部类型，包括基线不活跃者；分组彼此可能重叠，不是独立样本。

只改变指定执行权重为零，不删除 IR 行、不重新计算归一化、也不修改共享原网络。
支持原始 CSR 与 event traversal 两种执行后端的一致切边语义。

## 分析定义与限制

- 窗口：与 v1 一致，从刺激起点至最后脉冲结束后 500 ms；半开区间。
- 干预指标：100 ms 峰值、累计 spikes/neuron/pulse，分母含所有组员而非仅活跃者。
- 百分比：100×(完整−干预)/完整；完整响应为零时记 NaN，不当作零效应。
- 交互：R(A+B)−R(A)−R(B)+R(完整)。非线性存在时不能把两个单独干预相加解释全消融。
- 突触驱动：用完整网络的预突触放电数乘原始有符号权重，计入 1 step 传递延迟；
  只是送达积分器之前的驱动总量，不包括不应期丢弃、膜衰减等，不能当作因果贡献。
- 旁路：在当前已截取的 IR 上去掉 vPN1 后做有向 BFS，分别用非零符号边和全正边。
  可达性不是动物中的生理激活证据，不构成最小通路或通路必要性分析。
- 读出敏感性：峰值窗口 20/50/100/200 ms、累计量、rise 50 ms / decay 200/500/1000 ms
  的三种因果双指数滤波；单 spike 核峰值归一为 1。
  使用响应窗内脉冲列，尾部补 5 个 decay 时间常数以检查迟发峰值。
  核常数为工程敏感性选择；没有饱和、非线性钙动力学、表达水平或 ROI 校准，不是 ΔF/F。
- `observation_directions.csv` 对所有群组列出相同的 35>15/25 与 35>85/95 数值比较；
  只有 pC1 对应 v1 中这两组方向，其他群组是探索性参照，均不作为新增生物验收项。
- 新指标和刺激试次不是独立动物样本，不据此做生物学 p 值。

参考：[Zhou et al., 2015](https://pmc.ncbi.nlm.nih.gov/articles/PMC4575990/)。
本文讨论峰值钙信号、指示剂动力学与成像部位差异；不为本项目的滤波常数提供校准。

## 运行

从第四步目录执行（已有输出时必须指定新目录）：

```powershell
$py = 'C:\Users\20474\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$env:PYTHONIOENCODING = 'utf-8'
& $py '.\run_mechanism_diagnostics.py' --output-dir '.\outputs\courtship_song_mechanism_v2_repeat'
& $py -m pytest '.\tests' -q -p no:cacheprovider
```

完成状态固定为 `DIAGNOSTIC_ONLY_NOT_BIOLOGICAL_PASS`，脚本 exit 0 仅代表计算成功。
`run_metadata.json` 中 `model_freeze_recommended=false`。原默认 v1 验证器保留历史算法；
不得只凭其 `CONDITIONAL_SUPPORT` 文字而忽略本轮诊断限制。

## 文献驱动的 v2b 补充

v2 完成后补充检索了 MaleCNS 论文关于 `vPN1 -| mAL -| pC1` 的解释。
`run_mal_followup.py` 使用 `configs/courtship_song_mal_v2b.json`，对当前子图中
全部符合注释和两段负权重连接的 mAL 候选做第一段、第二段、两段切断，
在全部 9 个 IPI 下新增 27 次刺激和 3 次静默。先锁定协议、再仿真，原参数不变。
输出 `outputs/courtship_song_mal_v2b/`，同样拒绝覆盖。

```powershell
& $py '.\run_mal_followup.py' --output-dir '.\outputs\courtship_song_mal_v2b_repeat'
```

该候选集合不是论文具体细胞/驱动系的已验证一对一映射，不作为生物学验收项。
选取不使用模型响应或效应大小；完整单细胞输出包括不活跃者。
