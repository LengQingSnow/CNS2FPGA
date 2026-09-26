# 实验驱动系 / ROI 与 MaleCNS 映射审计（v3）

**结果：vPN1 可作精确的命名注释映射；pC1 的 R71G01∩dsx 和钙成像 ROI 不能由当前本地 IR 精确映射。**

这是有效的阻断结论：当前 pC1 全体或任一 annotation-derived 子集只能用于敏感性分析，不能称为 Zhou 2015 实验驱动的同一细胞集合。该审计不修改模型、刺激或既有 verdict。

## 文献与局部数据能支持什么

| id | readout | driver | mapping_status | local_mapping_result | source |
| --- | --- | --- | --- | --- | --- |
| zhou2015_vPN1_split_gal4 | vPN1 cell-body GCaMP6m and vPN1 perturbation | R72E10-GAL4AD ∩ VT9665-GAL4DBD; fruM-positive vPN1 | EXACT_ANNOTATION_NAME_MATCH | 11 cells; soma sides={'L': 6, 'R': 5} | https://pmc.ncbi.nlm.nih.gov/articles/PMC4575990/ |
| zhou2015_pC1_intersection | pC1 anatomy and inactivation | R71G01-LexA ∩ dsxGAL4 | NOT_IDENTIFIABLE_FROM_LOCAL_ANNOTATIONS | UNRESOLVED: no driver/ROI expression field; see candidate sets and required evidence | https://pmc.ncbi.nlm.nih.gov/articles/PMC4575990/ |
| zhou2015_pC1_calcium_roi | peak GCaMP6m ΔF/F in dsxGAL4 pC1 neurites in LPC | dsxGAL4; selected pC1 neurites in the lateral protocerebral complex | NOT_IDENTIFIABLE_FROM_LOCAL_ANNOTATIONS | UNRESOLVED: no driver/ROI expression field; see candidate sets and required evidence | https://pmc.ncbi.nlm.nih.gov/articles/PMC4575990/ |

R71G01-LexA∩dsxGAL4 的表达在文献中被用作 pC1 交集；独立报告称雄性约每半球 23 个细胞。该计数是合理性约束，不能反推哪 46 个 bodyId。

本地 `neuron_table.csv` 有 type、历史 synonym、fru/dsx 注释和 soma side，但没有 R71G01、GAL4/LexA 表达，也没有 neurite/LPC ROI membership。`fruDsx` 来自跨数据集 fruitless/doublesex annotation，不是 R71G01 驱动表达测量。[MaleCNS annotation provenance](https://github.com/flyconnectome/flywire_annotations/blob/main/README.md)

## 仅供敏感性分析的候选集（不是驱动映射）

| candidate_id | rule | status | neurons | soma_left | soma_right | soma_other | matches_reported_male_count_per_side | type_labels |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| pC1_type_all | type starts with pC1 | TYPE_IDENTITY_REFERENCE_ONLY | 112 | 62 | 50 | 0 | False | 43 |
| pC1_fruDsx_nonmissing | type starts with pC1 and fruDsx is nonempty | ANNOTATION_COMPATIBLE_CANDIDATE_NOT_DRIVER_MAP | 111 | 61 | 50 | 0 | False | 42 |
| pC1_fruDsx_coexpress | type starts with pC1 and fruDsx starts with coexpress | P1_RELATED_CANDIDATE_NOT_DRIVER_MAP | 65 | 37 | 28 | 0 | False | 24 |
| pC1_pMP_alias | type starts with pC1 and synonym has pMP-e or pMP4 | HISTORICAL_ALIAS_CANDIDATE_NOT_DRIVER_MAP | 63 | 36 | 27 | 0 | False | 23 |

`matches_reported_male_count_per_side=False` 说明不能仅靠数目把一个候选集伪装为 R71G01∩dsx ROI；即使数目碰巧相同，也仍需表达或形态证据。所有 candidate 的 bodyId 都在 `pC1_candidate_sets.csv` 中导出，供外部证据到位后逐项比对。

## 下一步所需证据

- A versioned, sex- and age-matched R71G01∩dsx expression-to-bodyId table, or an explicit morphology registration protocol with one-to-one bodyId assignments.
- For calcium comparison, an ROI/neurite mask or an explicit bodyId-to-ROI membership rule in the same template space.
- For quantitative calibration, raw or digitized experimental traces plus acquisition/normalization metadata; no values may be silently inferred from a plot.

在这些证据到位前，后续模型可报告：`pC1_type_all` 是类型级工程读出，`pC1_fruDsx_*` / `pC1_pMP_alias` 是 annotation-compatible 敏感性读出；不能报告为“实验 pC1 ROI”。

## 产物

- `experimental_mapping_registry.csv`：每个实验的 driver、读出、映射状态。
- `pC1_candidate_sets.csv`：候选集合、左右侧计数和全量 bodyId。
- `all_pC1_annotation_rows.csv` / `vPN1_exact_annotation_rows.csv`：逐细胞证据。
- `external_evidence_required.csv`：完成精确映射的输入契约。
- lock: `4bfa197e634db670d49809fe9613934eebad76e6bfd0daff3dfb9c28f2ff2fc5`。

文献：[Zhou et al., 2015](https://pmc.ncbi.nlm.nih.gov/articles/PMC4575990/)；[R71G01-LexA construct record](https://flybase.org/reports/FBtp0079698.html)；[R71G01∩dsx male-count report](https://pmc.ncbi.nlm.nih.gov/articles/PMC10882504/)。