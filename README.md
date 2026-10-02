# CNS2FPGA — 神经映芯

English first; a complete Chinese translation follows below.
英文在前，完整中文翻译见下文。

Connectome-constrained neural circuits compiled to a time-multiplexed FPGA engine.

The central idea is runtime graph deployment: compile a neural circuit to a
validated image, then load it into a fixed FPGA bitstream over Ethernet or
JTAG instead of rebuilding the bitstream for every network. Ethernet loading
of visual and courtship images on one programmed AXKU115 is board-verified in
two independently programmed sessions, with full visual and three long
courtship trials per session. The JTAG loading path also passed a physical
two-image and fault-recovery test.

This repository preserves the numbered research workflow from MaleCNS v1.0
subgraph extraction through CPU reference models, fixed-point compilation,
RTL checks, AXKU115 board measurements, robustness studies, a second
visual-to-steering circuit, Ethernet runtime image replacement, and a full
manuscript. The public layout numbers the implementation steps through 15;
`code/Paper/` collects the cross-cutting paper separately. Relative paths in
the release scripts and evidence indexes follow this public layout.

## What is verified

The current package is **V0.3**; see the [bilingual changelog](CHANGELOG.md).
The expanded-event image additionally passed a measured-100-Mbps session:
20/20 STATUS replies, a complete courtship image upload and 2,475 exact
ordered events over eight steps, with zero bad FCS. Further 1-Gbps tests are
deferred pending a cable/link check; cable capability is not a confirmed cause
of the earlier receive failures. The [100-Mbps audit](code/15_Ethernet_Runtime_Deployment/reports/expanded_bit_100m_audit_v1.json)
and [diagnosis](code/15_Ethernet_Runtime_Deployment/reports/ethernet_100m_vs_1g_diagnosis_20261001.md)
preserve the scope and evidence separately.

| Circuit | Neurons | Directed edges | 200 MHz AXKU115 result |
| --- | ---: | ---: | --- |
| Courtship-song candidate | 6,279 | 350,185 | 13 recorded conditions matched the fixed CPU at the available board readout; worst measured timestep 199,063/200,000 cycles |
| LC10a to DNa02 candidate | 226 | 1,730 | 560 ordered spike events matched fixed CPU in a left-input trial; worst measured timestep 4,439 cycles |
| Ethernet runtime bitstream, visual and courtship images | 226 / 6,279 | 1,730 / 350,185 | In each of two sessions: 250-step visual trial matched 560 ordered events; courtship `smoke8` matched 2,475; three 4,308-step courtship conditions matched fixed-CPU group counts; worst courtship step 199,699/200,000 cycles |
| Expanded-event Ethernet bitstream, courtship image | 6,279 | 350,185 | One successful campaign captured 40,868/74,765/99,349 complete ordered events across three 4,308-step stimuli; every event matched fixed CPU; first programming attempt had no UDP ACK before same-bit reprogramming |

These are implementation-fidelity results for a defined LIF model, **not** a
claim that the model reproduces measured fly activity or behavior. The full
evidence hierarchy and biological limits are in
[`code/Paper/manuscript_full_v2.md`](code/Paper/manuscript_full_v2.md).

## One bitstream, multiple network images (Step 15)

The 200 MHz [Ethernet runtime bitstream](hardware/bitstreams/cns2fpga_runtime_eth_200mhz.bit)
was programmed once in each of two independent AXKU115 sessions. Within each
session, a 226-neuron visual image and a 6,279-neuron courtship image were
uploaded over UDP and executed without FPGA resynthesis or reprogramming
between them. Visual matched 560 ordered events over 250 steps; courtship
matched 2,475 over eight steps and fixed-CPU response-window group counts in
three 4,308-step conditions. Interrupted/incomplete and invalid uploads were
rejected, followed by a successful valid-image recovery. The host NIC reported
1 Gbps during P0; the initial 28 September demonstration had negotiated
100 Mbps. Host-inclusive upload times were recorded, but neither observation
establishes sustained line-rate throughput. See [Step 15](code/15_Ethernet_Runtime_Deployment/README.md)
and the [independent P0 audit](code/15_Ethernet_Runtime_Deployment/reports/p0_board_audit_v1.json).

The old dedicated and new Ethernet-loaded courtship `smoke8` captures have
identical 2,475 ordered events and identical non-latency summary words, but the
new core takes 93–636 more cycles per step and uses more LUTs. The worst step
leaves 301 rather than 937 cycles before the 1-ms deadline. This is a
paired short-trial comparison; the P0 long trials add exact group-count and
per-step exported-summary agreement for three stimuli, not complete individual
event or internal-state identity. A later [expanded-event bitstream](hardware/bitstreams/cns2fpga_runtime_eth_long_events_200mhz.bit)
captured every ordered event in those three long trials and matched an
independent fixed-CPU reference. This was one successful board campaign after
an initial Ethernet failure and reprogramming of the same bitstream; it does
not establish cold-boot reliability or internal-state identity. See the
[long-event audit](code/15_Ethernet_Runtime_Deployment/reports/long_event_board_audit_v1.json).

The [paired comparison](code/15_Ethernet_Runtime_Deployment/reports/old_new_board_comparison_v1.json)
and [updated manuscript](code/Paper/manuscript_full_v2.pdf) report the
differences and limitations.

## Repository map

- [`code/`](code/) — numbered source, configurations, tests, selected
  intermediate representations, measurements, and paper sources.
- [`code/Paper/`](code/Paper/) — editable manuscript, PDF, ten cited
  figures, 36 data snapshots, raw event data, and the asset hash manifest.
- [`code/14_Runtime Reconfigurable Deployment/`](code/14_Runtime%20Reconfigurable%20Deployment/) —
  JTAG runtime graph loader, image preflight, RTL, and physical two-image/fault
  evidence.
- [`code/15_Ethernet_Runtime_Deployment/`](code/15_Ethernet_Runtime_Deployment/) —
  Ethernet RTL, protocol loader, vendor-licensed MAC sources, selected routed
  reports, repeated P0 board captures, fault logs, and public upload excerpts.
- [`hardware/bitstreams/`](hardware/bitstreams/) — two earlier dedicated
  bitstreams and both board-tested Ethernet runtime bitstreams.
- [`support/`](support/) — MaleCNS source manifest and download instructions.
  The 1.05 GB original connectivity table is intentionally not in Git.
- [`scripts/`](scripts/) — download and repository validation helpers.
- [`docs/`](docs/) — the copied-file integrity manifest. Provenance and
  license-scope notes are at the repository root.

The manifest's `path` is the public repository location; `source` records the
matching local development source for provenance.

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

神经映芯将连接组约束的神经回路编译到时分复用 FPGA 引擎。

本项目的核心思路是运行时部署网络图：先把神经回路编译为经过预检的镜像，
再通过网口或 JTAG 将其装入固定的 FPGA bit 文件，不必为每张网络重新生成 bit 文件。
同一块已烧录的 AXKU115 上，网口依次装载视觉与求偶镜像，并在两次独立烧录会话
中完成视觉全程与三组长求偶试验。JTAG 路径也通过了实板双镜像与异常恢复测试。

本仓库保留了从 MaleCNS v1.0 子图抽取、CPU 浮点参考模型、定点编译、RTL
校验、AXKU115 板卡测量、鲁棒性研究，到视觉到转向回路、网口运行时换图及完整论文的编号研究流程。
公开仓库把实现步骤编号至第 15 步；`code/Paper/` 单独汇集跨步骤论文。
发布脚本及证据索引中的相对路径已按公开目录布局更新。

### 已验证的内容

当前整理版本为 **V0.3**，详见[完整英中双语更新日志](CHANGELOG.md)。
扩展事件版另在实际 100 Mbps 会话中通过 20/20 次 STATUS、完整求偶网络上传和
八步 2,475 个有序事件核对，坏 FCS 为零。后续 1G 测试待网线／链路核查后再进行；
网线能力尚未证实，不能视作此前接收异常的确定原因。
[100M 审计](code/15_Ethernet_Runtime_Deployment/reports/expanded_bit_100m_audit_v1.json)
与[接收链路诊断](code/15_Ethernet_Runtime_Deployment/reports/ethernet_100m_vs_1g_diagnosis_20261001.md)
分别保留结果范围与证据。

| 回路 | 神经元数 | 有向边数 | 200 MHz AXKU115 结果 |
| --- | ---: | ---: | --- |
| 求偶鸣唱候选回路 | 6,279 | 350,185 | 在板卡可导出的观测量上，13 个记录条件与定点 CPU 一致；测得最慢时间步为 199,063/200,000 时钟周期 |
| LC10a 到 DNa02 候选回路 | 226 | 1,730 | 左侧输入试验中，560 个有序脉冲事件与定点 CPU 一致；测得最慢时间步为 4,439 周期 |
| 网口运行时 bit 文件加载视觉与求偶镜像 | 226 / 6,279 | 1,730 / 350,185 | 两轮各完成视觉 250 步、560 个有序事件及求偶 8 步、2,475 个事件；三组 4,308 步长试验的群体计数匹配定点 CPU；求偶最慢 199,699/200,000 周期 |
| 扩展事件容量的网口 bit 文件加载求偶镜像 | 6,279 | 350,185 | 一次成功测试完整采集三组 4,308 步试验的 40,868/74,765/99,349 个有序事件，并与定点 CPU 逐条一致；首次烧录后网口未应答，重烧录同一 bit 文件后通过 |

这些结果验证的是指定 LIF 模型的**工程实现一致性**，不意味着模型已经再现了
实测果蝇神经活动或行为。完整的证据层级和生物学限制见
[`code/Paper/manuscript_full_v2.md`](code/Paper/manuscript_full_v2.md)。

### 同一 bit 文件切换网络（第 15 步）

在两次独立会话中，各烧录一次 200 MHz [网口运行时 bit 文件](hardware/bitstreams/cns2fpga_runtime_eth_200mhz.bit)，
随后通过 UDP 依次上传并执行 226 神经元视觉镜像和 6,279 神经元求偶镜像，
会话内换图无需重新综合或烧录 FPGA。视觉 250 步匹配 560 个有序事件；求偶
8 步匹配 2,475 个事件，另有三组 4,308 步长试验的群体计数与定点 CPU 一致。
中断、不完整和无效镜像被拒绝，随后有效镜像恢复通过。P0 时主机网卡显示
1 Gbps，9 月 28 日初始试验曾协商 100 Mbps；计入上位机开销的上传耗时已
记录，但不能据此声称达到线速。详见[第 15 步](code/15_Ethernet_Runtime_Deployment/README.md)
与[P0 审计数据](code/15_Ethernet_Runtime_Deployment/reports/p0_board_audit_v1.json)。

旧专用版与新网口版的求偶 `smoke8` 共 2,475 个有序事件完全一致，非延迟摘要字段也一致；
但新版每步多用 93–636 个周期，LUT 占用也增加，最慢一步的 1 ms 截止余量从 937 降到 301 周期。
这是短试验的配对对照；P0 的三组长试验进一步验证群体计数和逐步输出摘要，
当时尚未采集全部单细胞事件。后续[扩展事件容量 bit 文件](hardware/bitstreams/cns2fpga_runtime_eth_long_events_200mhz.bit)
已完整采集这三组长试验的事件并逐条匹配独立 CPU 参考。其首次烧录后网口未应答，
重新烧录同一 bit 文件后的一次板上测试成功；这不证明冷启动可靠性或内部状态完全相同。
详见[长事件审计](code/15_Ethernet_Runtime_Deployment/reports/long_event_board_audit_v1.json)、[逐步对比数据](code/15_Ethernet_Runtime_Deployment/reports/old_new_board_comparison_v1.json)
和[更新后的论文](code/Paper/manuscript_full_v2.pdf)。

### 仓库目录

- [`code/`](code/)：按步骤编号的源码、配置、测试、选定的中间表示、测量结果和论文材料。
- [`code/Paper/`](code/Paper/)：可编辑论文、PDF、十张正式引用的图、36 份数据快照和素材哈希清单。
- [`code/14_Runtime Reconfigurable Deployment/`](code/14_Runtime%20Reconfigurable%20Deployment/)：JTAG 换图装载器、镜像预检、RTL 和实板双镜像/异常恢复证据。
- [`code/15_Ethernet_Runtime_Deployment/`](code/15_Ethernet_Runtime_Deployment/)：网口 RTL、装载器、第三方许可的 MAC 源码、布线报告、P0 双会话板卡采集、异常日志与上传记录。
- [`hardware/bitstreams/`](hardware/bitstreams/)：此前的专用 bit 文件及两份已上板验证的网口运行时 bit 文件。
- [`support/`](support/)：MaleCNS 原始数据清单与下载说明；1.05 GB 的原始连接表未放入 Git。
- [`scripts/`](scripts/)：下载及仓库完整性校验工具。
- [`docs/`](docs/)：复制文件的完整性清单；来源与许可范围说明位于仓库根目录。

清单中的 `path` 是公开仓库位置；`source` 记录对应的本地开发文件，供追溯来源。

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
