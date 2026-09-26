# CNS2FPGA

English first; a complete Chinese translation follows below.
英文在前，完整中文翻译见下文。

Connectome-constrained neural circuits compiled to a time-multiplexed FPGA engine.

This repository preserves the numbered research workflow from MaleCNS v1.0
subgraph extraction through CPU reference models, fixed-point compilation,
RTL checks, AXKU115 board measurements, robustness studies, a second
visual-to-steering circuit, and a full manuscript. The original directory
names under `code/` are retained because configurations and scripts use
relative paths between steps.

## What is verified

| Circuit | Neurons | Directed edges | 200 MHz AXKU115 result |
| --- | ---: | ---: | --- |
| Courtship-song candidate | 6,279 | 350,185 | 13 recorded conditions matched the fixed CPU at the available board readout; worst measured timestep 199,063/200,000 cycles |
| LC10a to DNa02 candidate | 226 | 1,730 | 560 ordered spike events matched fixed CPU in a left-input trial; worst measured timestep 4,439 cycles |

These are implementation-fidelity results for a defined LIF model, **not** a
claim that the model reproduces measured fly activity or behavior. The full
evidence hierarchy and biological limits are in
[`code/14_Paper/manuscript_full_v2.md`](code/14_Paper/manuscript_full_v2.md).

## Repository map

- [`code/`](code/) — numbered source, configurations, tests, selected
  intermediate representations, measurements, and paper sources.
- [`code/14_Paper/`](code/14_Paper/) — editable manuscript, six cited figures,
  selected CSV/JSON data, and the asset hash manifest.
- [`hardware/bitstreams/`](hardware/bitstreams/) — the two verified 200 MHz
  AXKU115 bitstreams; physical-design sources and reports remain in Steps 9
  and 12.
- [`support/`](support/) — MaleCNS source manifest and download instructions.
  The 1.05 GB original connectivity table is intentionally not in Git.
- [`scripts/`](scripts/) — download and repository validation helpers.
- [`docs/`](docs/) — the copied-file integrity manifest. Provenance and
  license-scope notes are at the repository root.

## First run

Use Python 3.12 or a compatible version and install
[`requirements.txt`](requirements.txt). Download MaleCNS with
`python scripts/download_malecns.py`, which verifies the pinned SHA-256 values.
Then follow [`REPRODUCING.md`](REPRODUCING.md) for read-only checks and new
versioned reruns. The existing `outputs/` directories are recorded results;
do not overwrite them during reproduction.

The KU115 bitstreams target the ALINX AXKU115 V1.0 with
`xcku115-flva1517-2-i`. Board programming is optional for CPU-only work.

## Data and publication status

MaleCNS v1.0 is credited to its original creators and marked CC BY on the
[official download page](https://male-cns.janelia.org/download/). Derived
tables retain that source attribution. Project-authored source and
documentation are released under MIT; see [`LICENSE`](LICENSE) and
[`LICENSE_NOTICE.md`](LICENSE_NOTICE.md). The dataset and other third-party
inputs retain their own terms. The raw MaleCNS tables, third-party image
exports, and board vendor manual are not bundled here.

## 中文说明

将连接组约束的神经回路编译到时分复用 FPGA 引擎。

本仓库保留了从 MaleCNS v1.0 子图抽取、CPU 浮点参考模型、定点编译、RTL
校验、AXKU115 板卡测量、鲁棒性研究，到第二个视觉到转向回路及完整论文的编号研究流程。
`code/` 下的原始步骤目录名保持不变，因为配置与脚本使用步骤之间的相对路径。

### 已验证的内容

| 回路 | 神经元数 | 有向边数 | 200 MHz AXKU115 结果 |
| --- | ---: | ---: | --- |
| 求偶鸣唱候选回路 | 6,279 | 350,185 | 在板卡可导出的观测量上，13 个记录条件与定点 CPU 一致；测得最慢时间步为 199,063/200,000 时钟周期 |
| LC10a 到 DNa02 候选回路 | 226 | 1,730 | 左侧输入试验中，560 个有序脉冲事件与定点 CPU 一致；测得最慢时间步为 4,439 周期 |

这些结果验证的是指定 LIF 模型的**工程实现一致性**，不意味着模型已经再现了
实测果蝇神经活动或行为。完整的证据层级和生物学限制见
[`code/14_Paper/manuscript_full_v2.md`](code/14_Paper/manuscript_full_v2.md)。

### 仓库目录

- [`code/`](code/)：按步骤编号的源码、配置、测试、选定的中间表示、测量结果和论文材料。
- [`code/14_Paper/`](code/14_Paper/)：可编辑论文、六张正式引用的图、选定的 CSV/JSON 数据和素材哈希清单。
- [`hardware/bitstreams/`](hardware/bitstreams/)：两份已验证的 200 MHz AXKU115 bit 文件；物理设计源码及报告保留在第 9、12 步。
- [`support/`](support/)：MaleCNS 原始数据清单与下载说明；1.05 GB 的原始连接表未放入 Git。
- [`scripts/`](scripts/)：下载及仓库完整性校验工具。
- [`docs/`](docs/)：复制文件的完整性清单；来源与许可范围说明位于仓库根目录。

### 首次使用

使用 Python 3.12 或兼容版本，安装 [`requirements.txt`](requirements.txt)。运行
`python scripts/download_malecns.py` 获取 MaleCNS 数据并校验固定的 SHA-256 值。
然后按照 [`REPRODUCING.md`](REPRODUCING.md) 做只读检查和新版本重跑。
现有 `outputs/` 目录是已记录结果，复现时不要覆盖。

KU115 bit 文件仅适用于采用 `xcku115-flva1517-2-i` 器件的 ALINX AXKU115 V1.0。
仅运行 CPU 流程不需要给板卡编程。

### 数据与发布状态

MaleCNS v1.0 的原始作者应获得署名；[官方下载页](https://male-cns.janelia.org/download/)
将数据标为 CC BY，衍生表仍须保留该来源署名。项目原创源码和文档采用 MIT，
详见 [`LICENSE`](LICENSE) 与 [`LICENSE_NOTICE.md`](LICENSE_NOTICE.md)。
MaleCNS 数据及其他第三方输入保留各自许可。本仓库不打包原始 MaleCNS 大表、
第三方图像导出或板卡厂商手册。
