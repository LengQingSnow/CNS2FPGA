# Changelog

English first; the complete Chinese translation follows.

## V0.3

The release extends runtime graph deployment with repeated board tests,
fault recovery, full long-trial event capture and an additional measured
100-Mbps session. Changing a network image still requires only Ethernet or
JTAG transfer within the engine's format and capacity; changes to engine
hardware, such as increasing the event buffer, require a separate bitstream.

- The JTAG runtime image passed visual/courtship switching and fault recovery
  after one programming operation. The original Ethernet runtime image passed
  two independently programmed sessions, each with a 250-step/560-event visual
  trial, an eight-step/2,475-event courtship trial, three 4,308-step courtship
  conditions, and rejection/recovery tests.
- The expanded-event Ethernet image stores 131,072 events. One successful
  campaign captured all 40,868/74,765/99,349 ordered events for IPI 15/35/65 ms;
  all 214,982 events matched independently generated fixed-CPU references.
  Its first Ethernet attempt failed and same-bit reprogramming recovered it.
- A separate measured-100-Mbps session on the same expanded image passed
  20/20 first-attempt STATUS probes, a 738,044-word courtship upload, and all
  2,475 ordered events over eight steps. Epoch was 1, checksum `45AEAAAE`,
  maximum core latency 199,699/200,000 cycles, and bad FCS, missed steps and
  fault flags were zero. This is a short trial, not a second long campaign.
- The manuscript adds Figures 8–10 and includes ten figures, seven main
  tables, 36 data snapshots, editable DOCX, PDF and hash-based provenance.
  Dedicated, original runtime and expanded-event bitstreams remain separately
  named and hash-pinned. Their output identity and differences in resources
  and core cycles are retained in the paper.
- The package adds offline audits, raw captures, selected public log excerpts
  and corrected reproduction instructions and Git log allowlists.

The prior 1-Gbps receive failures remain recorded. Cable capability has not
been independently checked; it is one possible explanation, not a confirmed
cause. Further 1-Gbps tests are deferred. Historical P0 observations at
1 Gbps do not establish reliable gigabit operation of the expanded image.
The results establish engineering fidelity for the stated LIF computation;
experimental biological validation remains open.

Evidence: [P0 audit](code/15_Ethernet_Runtime_Deployment/reports/p0_board_audit_v1.json),
[long-event audit](code/15_Ethernet_Runtime_Deployment/reports/long_event_board_audit_v1.json),
[100-Mbps audit](code/15_Ethernet_Runtime_Deployment/reports/expanded_bit_100m_audit_v1.json),
[receive-path diagnosis](code/15_Ethernet_Runtime_Deployment/reports/ethernet_100m_vs_1g_diagnosis_20261001.md),
[manuscript](code/Paper/manuscript_full_v2.pdf).

## V0.2

Separated FPGA engine compilation from graph loading: network images can be
transferred by JTAG or Ethernet without rebuilding the bitstream for each
network. Added the runtime loader, image preflight and deployment evidence.

## V0.1

Implemented MaleCNS courtship-song and visual-circuit extraction, reference
models, compilation, RTL verification and dedicated FPGA deployment.

## 中文更新日志

### V0.3

在运行时网络部署基础上，补齐重复上板、异常恢复、长试验全事件采集和新增的
实际 100 Mbps 会话。在引擎格式与容量范围内换网络，仅需通过网口或 JTAG
传输镜像；扩大事件缓冲等硬件修改仍需另一份 bit 文件。

- JTAG 运行时版本一次烧录后通过视觉／求偶换图与异常恢复。原网口运行时版本
  通过两次独立烧录会话，每轮完成视觉 250 步／560 事件、求偶八步／2,475 事件、
  三组 4,308 步求偶条件和异常拒绝／恢复测试。
- 扩展网口版本的事件容量为 131,072 条。一次成功长试验完整采集 IPI 15/35/65 ms
  的 40,868/74,765/99,349 个有序事件，共 214,982 个，全部匹配独立定点 CPU。
  首次网口测试失败，重新烧录同一 bit 文件后恢复，失败记录保留。
- 同一扩展 bit 文件另在实际 100 Mbps 下通过一次会话：20/20 次 STATUS 首次应答、
  738,044 字求偶网络上传、八步全部 2,475 个有序事件一致。epoch 为 1，checksum
  为 `45AEAAAE`，最大核心延迟 199,699/200,000 周期；坏 FCS、错过时间步和异常
  标志均为零。这是新增短试验，不是第二次长试验。
- 完整论文新增图 8–10，共十张图、七张正文表、36 份数据快照，提供可编辑 Word、
  PDF 和哈希溯源。专用版、原运行时版和扩展事件版分别保留并固定哈希；输出一致性、
  资源差异和核心周期差异仍在论文中明确记录。
- 补齐离线复核工具、原始采集、公开日志摘录，修正复现说明与 Git 日志例外规则。

此前千兆接收异常仍保留。网线能力尚未独立核验，是一种可能解释，不能视为已定位
原因；后续 1G 测试暂缓。历史 P0 的千兆观测不能代表扩展版千兆可靠性已通过。
这些结果验证指定 LIF 计算的工程一致性，生物学实验验证仍未完成。

证据：[P0 审计](code/15_Ethernet_Runtime_Deployment/reports/p0_board_audit_v1.json)、
[长事件审计](code/15_Ethernet_Runtime_Deployment/reports/long_event_board_audit_v1.json)、
[100M 审计](code/15_Ethernet_Runtime_Deployment/reports/expanded_bit_100m_audit_v1.json)、
[接收链路诊断](code/15_Ethernet_Runtime_Deployment/reports/ethernet_100m_vs_1g_diagnosis_20261001.md)、
[论文](code/Paper/manuscript_full_v2.pdf)。

### V0.2

将 FPGA 引擎编译与网络加载分离：通过 JTAG 或网口传输网络镜像即可换图，不必为
每张网络重新生成 bit 文件。加入运行时装载器、镜像预检和部署证据。

### V0.1

实现 MaleCNS 求偶鸣唱及视觉回路的抽取、参考模型、编译、RTL 校验和专用 FPGA 部署。
