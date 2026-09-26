# Verified board images

Both files were produced for the ALINX AXKU115 V1.0,
`xcku115-flva1517-2-i`, with a 200 MHz model core. They are hardware-specific
execution artifacts, not source code or biological validation.

| File | Circuit | SHA-256 | Recorded test |
| --- | --- | --- | --- |
| `cns2fpga_axku115_jtag_200mhz.bit` | 6,279-neuron courtship candidate | `0dfb8e09e9509c40cf5f48e616ddd3b31ccc279d03946446fbc21e80523a53a9` | 13 stimulus conditions; 199,063-cycle maximum step |
| `cns2fpga_visual_left_jtag_200mhz.bit` | 226-neuron visual candidate, left LC10a input | `aa11a5965beaef316c6a388bba3075294a5c4efe02616cdf2ed073d9af0cc572` | 560 ordered events; 4,439-cycle maximum step |

The matching RTL, constraints, implementation scripts, timing reports,
stimulus protocol locks, and board captures are in `code/9_KU115 FPGA
Validation/` and `code/12_Visual-to-Steering Circuit/`. The copied-file
manifest under `docs/` records the original path of each binary.

## 中文说明：已验证的板卡镜像

两份文件均针对 ALINX AXKU115 V1.0（`xcku115-flva1517-2-i`）生成，
模型核心频率为 200 MHz。它们是板卡专用的工程执行产物，不属于源码，
也不构成生物学模型验证。

| 文件 | 回路 | SHA-256 | 已记录测试 |
| --- | --- | --- | --- |
| `cns2fpga_axku115_jtag_200mhz.bit` | 6,279 个神经元的求偶鸣唱候选回路 | `0dfb8e09e9509c40cf5f48e616ddd3b31ccc279d03946446fbc21e80523a53a9` | 13 个刺激条件；最长时间步 199,063 周期 |
| `cns2fpga_visual_left_jtag_200mhz.bit` | 226 个神经元的视觉候选回路，左侧 LC10a 输入 | `aa11a5965beaef316c6a388bba3075294a5c4efe02616cdf2ed073d9af0cc572` | 560 个有序事件；最长时间步 4,439 周期 |

对应的 RTL、引脚与时序约束、实现脚本、时序报告、刺激协议锁及板卡采集结果位于
`code/9_KU115 FPGA Validation/` 和 `code/12_Visual-to-Steering Circuit/`。
`docs/` 下的复制文件清单记录了每份二进制文件在原项目中的路径。
