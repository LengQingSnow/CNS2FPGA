# Data provenance and redistribution scope

## MaleCNS source

The graph source is MaleCNS v1.0, downloaded from the
[official MaleCNS download page](https://male-cns.janelia.org/download/).
Its three required original Feather files, exact URLs, sizes, and local
SHA-256 values are recorded in `support/data_sources.json`. The full
1.05 GB connectivity file is not committed; `scripts/download_malecns.py`
restores it and refuses a checksum mismatch. The official site marks the
MaleCNS dataset CC BY. Attribute the source paper and dataset when reusing
derived graphs or results.

## Project-derived material

The `code/<step>/outputs/` directories contain project-derived graph tables,
model responses, memory images, and verification records. The selected
publication figures and tables are in `code/Paper/`; its
`paper_data/manifest.json` links each item to the source result file and hash.
Two board-specific bitstreams are included separately in
`hardware/bitstreams/`, with SHA-256 values in its README.

## Deliberate exclusions

- Original MaleCNS Feather files: too large for ordinary Git distribution;
  restore from the pinned official links.
- Vivado `.Xil`, `build`, simulation work libraries, route checkpoints,
  journals, and transient logs: generated locally and not source material.
- Step-4 third-party/user-supplied NeuronBridge image exports: omitted pending
  an independent redistribution-rights check. The analysis docs and derived
  outputs remain, but image-level reruns require those inputs separately.
- Vendor AXKU115 user guide: obtain from the board vendor; it is not a
  project-authored document.

No external fly neural/behavioral dataset, board power trace, or independent
hardware replication dataset is implied by this repository.

## 中文说明：数据来源与再分发范围

### MaleCNS 原始数据

图数据来自 [MaleCNS 官方下载页](https://male-cns.janelia.org/download/)发布的
MaleCNS v1.0。所需三个原始 Feather 文件的准确链接、大小和本地 SHA-256 记录在
`support/data_sources.json`。仓库不提交 1.05 GB 的完整连接表；
`scripts/download_malecns.py` 可恢复该文件，并在校验不一致时拒绝使用。
官方网站将 MaleCNS 数据标为 CC BY。复用衍生图或结果时，请署名原始论文和数据集。

### 项目衍生材料

`code/<step>/outputs/` 包含项目生成的图表、模型响应、存储镜像及验证记录。
选定的论文图表和数据位于 `code/Paper/`；其中 `paper_data/manifest.json`
把每个素材关联到原始结果文件和哈希。两份板卡专用 bit 文件单独放在
`hardware/bitstreams/`，其 SHA-256 见该目录的 README。

### 有意排除的内容

- MaleCNS 原始 Feather 文件：体积不适合普通 Git 分发，可从固定的官方链接恢复。
- Vivado `.Xil`、`build`、仿真工作库、布线检查点、日志及临时文件：均为本机生成内容。
- 第 4 步的第三方或用户提供的 NeuronBridge 图像导出：在独立核实再分发权利前不公开；分析文档和衍生输出保留，但图像层面的重跑须另行取得这些输入。
- AXKU115 厂商用户手册：请向板卡厂商获取，并非项目原创文档。

本仓库不暗示存在外部果蝇神经或行为数据集、板卡功耗轨迹、或独立的硬件复现数据集。
