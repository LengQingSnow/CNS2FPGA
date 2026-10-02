# AXKU115 board images: verified and candidate

These files were produced for the ALINX AXKU115 V1.0,
`xcku115-flva1517-2-i`, with a 200 MHz model core. They are hardware-specific
execution artifacts, not source code or biological validation.

| File | Circuit | SHA-256 | Recorded test |
| --- | --- | --- | --- |
| `cns2fpga_axku115_jtag_200mhz.bit` | 6,279-neuron courtship candidate | `0dfb8e09e9509c40cf5f48e616ddd3b31ccc279d03946446fbc21e80523a53a9` | 13 stimulus conditions; 199,063-cycle maximum step |
| `cns2fpga_visual_left_jtag_200mhz.bit` | 226-neuron visual candidate, left LC10a input | `aa11a5965beaef316c6a388bba3075294a5c4efe02616cdf2ed073d9af0cc572` | 560 ordered events; 4,439-cycle maximum step |
| `cns2fpga_runtime_jtag_200mhz.bit` | Reusable `safe_wf24` graph engine over JTAG | `95f9b50ee03804ddc211828a9fbd3b3171b45bc3ffb79f9f3b2407f0d3190e52` | One physical programming operation, visual 560 and courtship 2,475 exact ordered events; injected-fault rejection and valid-image recovery passed |
| `cns2fpga_runtime_eth_200mhz.bit` | Reusable `safe_wf24` graph engine over UDP | `581354a62c8c7aeb134f300e7ea1928d8b681b996807710c61e307b33530d8f8` | Two independent board sessions; each ran visual 250-step/560-event, courtship smoke8/2,475-event and three 4,308-step conditions; fault recovery passed; max 199,699 cycles |
| `cns2fpga_runtime_eth_long_events_200mhz.bit` | UDP graph engine with 131,072 event entries | `d4c9378d461147062fa5dc590cb3647d241c789b01cc6255f38da16cb21990df` | After a failed first-program Ethernet attempt and same-bit reprogramming, one successful campaign captured all 40,868/74,765/99,349 ordered courtship events in three 4,308-step conditions; exact fixed-CPU matches, no overflow or deadline fault |

The matching RTL, constraints, implementation scripts, timing reports,
stimulus protocol locks, and board captures are in Steps 9, 12, 14 and 15
under `code/`. The Ethernet bitstream is copied from the signed-off
`runtime_eth_portfilter_200mhz` build; older Ethernet diagnostic bitstreams
are intentionally excluded. This 200 MHz route has setup WNS +0.012 ns,
hold WHS +0.010 ns, no unrouted nets, and zero DRC errors. Its narrow
301-cycle measured deadline margin warrants more timing headroom in future designs. The
copied-file manifest under `docs/` records each binary's source and hash.
The expanded-event build separately routed at setup WNS +0.008 ns and hold
WHS +0.030 ns, using 618 BRAM36. Its first-program UDP failure is retained in
the [audit](../../code/15_Ethernet_Runtime_Deployment/reports/long_event_board_audit_v1.json).

The same expanded-event SHA-256 above also passed an additional measured
100-Mbps session: one programming operation, 20/20 STATUS replies, full
courtship graph upload and 2,475 exact ordered events over eight steps, with
zero bad FCS, deadline misses or faults. See the
[100-Mbps audit](../../code/15_Ethernet_Runtime_Deployment/reports/expanded_bit_100m_audit_v1.json).
This does not establish reliable 1-Gbps operation. Further gigabit tests are
deferred pending cable/link checks; cable capability is not a confirmed cause.
The original runtime image retains its P0 results and the expanded image
retains its separate long-event and 100-Mbps evidence.

## 中文说明：已验证的板卡镜像

这些文件均针对 ALINX AXKU115 V1.0（`xcku115-flva1517-2-i`）生成，
模型核心频率为 200 MHz。它们是板卡专用的工程执行产物，不属于源码，
也不构成生物学模型验证。

| 文件 | 回路 | SHA-256 | 已记录测试 |
| --- | --- | --- | --- |
| `cns2fpga_axku115_jtag_200mhz.bit` | 6,279 个神经元的求偶鸣唱候选回路 | `0dfb8e09e9509c40cf5f48e616ddd3b31ccc279d03946446fbc21e80523a53a9` | 13 个刺激条件；最长时间步 199,063 周期 |
| `cns2fpga_visual_left_jtag_200mhz.bit` | 226 个神经元的视觉候选回路，左侧 LC10a 输入 | `aa11a5965beaef316c6a388bba3075294a5c4efe02616cdf2ed073d9af0cc572` | 560 个有序事件；最长时间步 4,439 周期 |
| `cns2fpga_runtime_jtag_200mhz.bit` | 通过 JTAG 换图的通用 `safe_wf24` 引擎 | `95f9b50ee03804ddc211828a9fbd3b3171b45bc3ffb79f9f3b2407f0d3190e52` | 实板烧录一次后视觉 560、求偶 2,475 个有序事件匹配；异常拒绝及有效镜像恢复通过 |
| `cns2fpga_runtime_eth_200mhz.bit` | 通过 UDP 换图的通用 `safe_wf24` 引擎 | `581354a62c8c7aeb134f300e7ea1928d8b681b996807710c61e307b33530d8f8` | 双会话各完成视觉 250 步、求偶 8 步及三组 4,308 步长试验；异常恢复通过；最慢 199,699 周期 |
| `cns2fpga_runtime_eth_long_events_200mhz.bit` | 具有 131,072 条事件容量的 UDP 换图引擎 | `d4c9378d461147062fa5dc590cb3647d241c789b01cc6255f38da16cb21990df` | 首次烧录网口未应答，重新烧录同一文件后一次成功测试完整采集 40,868/74,765/99,349 个事件，均与定点 CPU 逐条一致，未溢出或错过截止时间 |

对应 RTL、约束、构建脚本及选定证据位于 `code/` 下的第 9、12、14、15 步。
网口 bit 文件来自已签核的 `runtime_eth_portfilter_200mhz` 构建；早期诊断版本不发布。
200 MHz 布线的 setup WNS 为 +0.012 ns、hold WHS 为 +0.010 ns，未布线网络和 DRC 错误均为零；
但实测截止余量仅 301 周期，未来设计仍应增加时序余量。
`docs/` 下的清单记录每份二进制文件的来源和哈希。
扩展事件版本另外完成了布线签核：setup WNS +0.008 ns、hold WHS +0.030 ns，
使用 618 个 BRAM36；首次网口失败也保留在[审计文件](../../code/15_Ethernet_Runtime_Deployment/reports/long_event_board_audit_v1.json)中。

同一哈希的扩展版另在实际 100 Mbps 下完成一次会话：一次烧录、20/20 次 STATUS、
完整求偶网络上传及八步 2,475 个有序事件核对均通过，坏 FCS、错过时间步和异常标志
均为零，详见[100M 审计](../../code/15_Ethernet_Runtime_Deployment/reports/expanded_bit_100m_audit_v1.json)。
这不证明千兆可靠性；后续 1G 测试待网线／链路核查后进行，网线能力尚未确认为原因。
原运行时版保留 P0 结果，扩展版分别保留长事件与新增 100M 证据。
