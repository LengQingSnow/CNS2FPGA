# 外部实验 ROI → MaleCNS bodyId 映射输入契约

当前本地数据无法把 `R71G01∩dsx` 或 `dsxGAL4` 在 LPC 的成像 ROI 精确映射为 bodyId。
因此不允许用 pC1 type、`fruDsx`、历史别名、连接强度或模拟响应自动填补这一空缺。

提交一个 UTF-8 CSV，必须具有以下列：

```csv
experiment_id,bodyId,evidence_id,mapping_method,source_url,source_version,sex,age_or_stage,driver_or_roi,confidence
zhou2015_pC1_intersection,12345,figure_or_dataset_item,direct_expression_registration,https://...,version-or-DOI,male,adult,R71G01-LexA∩dsxGAL4,high
```

`experiment_id` 只能为：

- `zhou2015_vPN1_split_gal4`
- `zhou2015_pC1_intersection`
- `zhou2015_pC1_calcium_roi`

`mapping_method` 只能为 `direct_expression_registration` 或 `morphology_registration`。
每个 bodyId 必须存在于当前锁定 IR，且同一 experiment/bodyId 不能重复。
导入器还强制要求 male、明确年龄/阶段、证据编号、来源 URL 与版本。

```powershell
$py = 'C:\Users\20474\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
& $py '.\import_external_roi_map.py' `
  --mapping-csv '.\evidence\zhou2015_pC1_bodyids.csv' `
  --output-dir '.\outputs\courtship_song_roi_mapping_v3_direct'
```

导入只产生锁定的 bodyId 映射与 provenance，不会运行模拟或改动既有 IR / Golden Model。
导入成功后，才可用该目录重新定义专门的实验 ROI readout；它仍需要独立的刺激条件检验。
