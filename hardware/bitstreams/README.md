# AXKU115 board images: verified and candidate

These files were produced for the ALINX AXKU115 V1.0,
`xcku115-flva1517-2-i`, with a 200 MHz model core. They are hardware-specific
execution artifacts, not source code or biological validation.

| File | Circuit | SHA-256 | Recorded test |
| --- | --- | --- | --- |
| `cns2fpga_axku115_jtag_200mhz.bit` | 6,279-neuron courtship candidate | `0dfb8e09e9509c40cf5f48e616ddd3b31ccc279d03946446fbc21e80523a53a9` | 13 stimulus conditions; 199,063-cycle maximum step |
| `cns2fpga_visual_left_jtag_200mhz.bit` | 226-neuron visual candidate, left LC10a input | `aa11a5965beaef316c6a388bba3075294a5c4efe02616cdf2ed073d9af0cc572` | 560 ordered events; 4,439-cycle maximum step |
| `cns2fpga_runtime_jtag_200mhz.bit` | Reusable `safe_wf24` graph engine over JTAG | `95f9b50ee03804ddc211828a9fbd3b3171b45bc3ffb79f9f3b2407f0d3190e52` | Offline timing/simulation pass |
| `cns2fpga_runtime_eth_200mhz.bit` | Reusable `safe_wf24` graph engine over UDP | `581354a62c8c7aeb134f300e7ea1928d8b681b996807710c61e307b33530d8f8` | Visual and courtship images committed without reprogramming; courtship `smoke8` matched 2,475 ordered events, max 199,699 cycles |

The matching RTL, constraints, implementation scripts, timing reports,
stimulus protocol locks, and board captures are in Steps 9, 12, 14 and 15
under `code/`. The Ethernet bitstream is copied from the signed-off
`runtime_eth_portfilter_200mhz` build; older Ethernet diagnostic bitstreams
are intentionally excluded. This 200 MHz route has setup WNS +0.012 ns,
hold WHS +0.010 ns, no unrouted nets, and zero DRC errors. Its narrow
301-cycle measured deadline margin merits longer repeat trials. The
copied-file manifest under `docs/` records each binary's source and hash.

## 中文说明：已验证的板卡镜像

这些文件均针对 ALINX AXKU115 V1.0（`xcku115-flva1517-2-i`）生成，
模型核心频率为 200 MHz。它们是板卡专用的工程执行产物，不属于源码，
也不构成生物学模型验证。

| 文件 | 回路 | SHA-256 | 已记录测试 |
| --- | --- | --- | --- |
| `cns2fpga_axku115_jtag_200mhz.bit` | 6,279 个神经元的求偶鸣唱候选回路 | `0dfb8e09e9509c40cf5f48e616ddd3b31ccc279d03946446fbc21e80523a53a9` | 13 个刺激条件；最长时间步 199,063 周期 |
| `cns2fpga_visual_left_jtag_200mhz.bit` | 226 个神经元的视觉候选回路，左侧 LC10a 输入 | `aa11a5965beaef316c6a388bba3075294a5c4efe02616cdf2ed073d9af0cc572` | 560 个有序事件；最长时间步 4,439 周期 |
| `cns2fpga_runtime_jtag_200mhz.bit` | 通过 JTAG 换图的通用 `safe_wf24` 引擎 | `95f9b50ee03804ddc211828a9fbd3b3171b45bc3ffb79f9f3b2407f0d3190e52` | 离线时序和仿真通过 |
| `cns2fpga_runtime_eth_200mhz.bit` | 通过 UDP 换图的通用 `safe_wf24` 引擎 | `581354a62c8c7aeb134f300e7ea1928d8b681b996807710c61e307b33530d8f8` | 不重新烧录而提交视觉与求偶镜像；求偶 8 步与 2,475 个有序事件一致，最长 199,699 周期 |

对应 RTL、约束、构建脚本及选定证据位于 `code/` 下的第 9、12、14、15 步。
网口 bit 文件来自已签核的 `runtime_eth_portfilter_200mhz` 构建；早期诊断版本不发布。
200 MHz 布线的 setup WNS 为 +0.012 ns、hold WHS 为 +0.010 ns，未布线网络和 DRC 错误均为零；
但实测截止余量仅 301 周期，仍需更长时间的重复试验。
`docs/` 下的清单记录每份二进制文件的来源和哈希。
