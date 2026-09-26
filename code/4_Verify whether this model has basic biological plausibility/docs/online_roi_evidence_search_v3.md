# R71G01 / pC1 实验 ROI 的在线证据检索记录

检索日期：2026-09-18。目标是取得能把 Zhou 2015 的实验 driver 或成像 ROI
一对一落到当前 MaleCNS v1.0 IR `bodyId` 的公开证据。结论是：**公开资料确认了
driver 的生物学含义，但没有提供足以直接导入 bodyId 的逐细胞对应表。**

## 已确认的在线证据

| 资源 | 可确认内容 | 对 bodyId 映射的用途 | 结论 |
| --- | --- | --- | --- |
| [Zhou et al., 2015](https://pmc.ncbi.nlm.nih.gov/articles/PMC4575990/) | vPN1 使用特异 split-GAL4；pC1 解剖/消融使用 R71G01-LexA∩dsxGAL4；pC1 钙成像为 dsxGAL4 标记神经突起的峰值 ΔF/F。 | 给出实验定义，未给 MaleCNS bodyId 或可执行 ROI mask。 | vPN1 仍可用命名注释精确定位；两个 pC1 集合不可精确映射。 |
| [FlyBase R71G01-LexA 构建记录](https://flybase.org/reports/FBtp0079698.html) | 记录 R71G01-LexA 构建；并说明它与 dsx 交集标记 adult pC1。 | 证明 driver 语义，未给 EM cell ID。 | 不足以创建 bodyId map。 |
| [Jiang et al., 2024](https://pmc.ncbi.nlm.nih.gov/articles/PMC10882504/) | R71G01∩dsx 在雄性约 23 个/侧。 | 只可作数目合理性检查；不能从 46 个总数反演 ID。 | 不足以选择当前 112 个 pC1 中的任意 46 个。 |
| [Deutsch et al., 2020](https://pmc.ncbi.nlm.nih.gov/articles/PMC7787663/) | **雌性** pC1-S（R71G01.AD∩DSX.DBD）可能只含 pC1a/b；pC1-A 是另一套 split driver。 | 提醒 R71G01 相关的不同 driver 构成并不相同。 | 不能跨性别、跨 driver 外推到雄性 Zhou 2015 的 R71G01-LexA∩dsxGAL4。 |
| [Virtual Fly Brain 的 R71G01 条目](https://www.virtualflybrain.org/term/r71g01-vfb_00100zoe/) | 提供已配准的 R71G01 confocal 表达图与 NeuronBridge 链接。 | 可作为将来形态注册的输入影像。 | 原始表达图不是逐 bodyId 注册结果。 |
| [NeuronBridge](https://neuronbridge.janelia.org/) / [release notes](https://github.com/JaneliaSciComp/neuronbridge/blob/master/public/RELEASENOTES.md) | MaleCNS 已可做形态搜索；新版 curated matches 是专家标注的 **Split-GAL4 line → cell type** 关联，带置信度、脑区、来源。 | 适合产生/核对 type 候选，不等同于 bodyId 映射。 | 若需使用，必须保存检索导出、版本和每个候选的注册证据；仅 cell-type 结果仍不能通过本项目的 direct-map 校验。 |

## 未获证据与原因

- 未找到公开、版本化的 `R71G01∩dsx → MaleCNS bodyId` 对照表。
- 未找到 Zhou 2015 中 dsxGAL4-LPC 成像 neurite ROI 到 MaleCNS bodyId 的掩码或映射规则。
- NeuronBridge 搜索页要求登录；未代表用户登录。其公开资料描述 curated matches 的输出单位是 cell type，不能单独满足 bodyId 级要求。
- 为确认接口字段，尝试只读访问 NeuronBridge 的公开 curated-match API；本环境到其 AWS API 的 TLS 握手失败。即使接口可访问，公开 release notes 描述的 curated 输出也需要再与可复核的单细胞形态注册相结合。

## 不能做的推断

下列做法均会制造虚假的“精确 ROI”，因此禁止作为 Golden Model 校准或新生物学通过项：

- 从约 23 个/侧的文献计数，在 112 个 type-pC1 中任意挑出 46 个；
- 以 `fruDsx=coexpress_*`、`pMP-e/pMP4` 别名、连接强度、35 ms 响应或 vPN1 输入比例替代 driver 表达；
- 把雌性 pC1-S（R71G01.AD∩DSX.DBD）的 pC1a/b 推断套用到雄性 R71G01-LexA∩dsxGAL4；
- 把 NeuronBridge 的形态分数或 type-level curated match 当成已验证的一对一 bodyId 对应。

## 可执行的下一条证据路径

1. 用户在 NeuronBridge 登录后检索 R71G01，导出可共享的 curated/morphology 结果及来源；不得只截屏，需保留版本、查询条件和候选 ID。
2. 针对每个候选，以同模板空间的 R71G01 或 split-GAL4 单细胞/分割表达影像与 MaleCNS skeleton 做形态注册，写明评分、阈值、人工复核和不确定性。
3. 导出确认的 `bodyId`、driver/ROI、直接证据编号、性别、年龄、版本，按 [外部映射输入契约](external_roi_mapping_contract_v3.md) 导入。
4. 将 pC1 driver ROI 固定为新版本的 readout；另留未用于选择映射的 IPI / 输入条件验证，才讨论改动力学或观测模型。

本记录的作用是关闭未经证据支持的自动映射路线，并为可审计的人工/形态注册路线保留输入契约。
