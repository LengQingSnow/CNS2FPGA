# Step 15 — AXKU115 Ethernet runtime deployment / 网口运行时部署

This step adds an RGMII/UDP graph loader to the existing 200 MHz runtime
engine. A single FPGA bitstream can accept different preflighted network images
without being recompiled or reprogrammed. The JTAG AXI path remains available
for register access and experiments; host software must not use JTAG and UDP
concurrently. The initial 28 September demonstration negotiated 100 Mbps and
passed both image commits plus a courtship eight-step trial. The 30 September
P0 campaign then passed two independently programmed sessions, each including
full visual and three long courtship trials, injected upload faults, and
valid-image recovery. A host-adapter query during P0 reported a 1-Gbps link.

本步骤给原有 200 MHz 运行时核心增加 RGMII/UDP 网络图加载器。烧录一次后，
不同网络镜像可通过网口更换，无需重新综合或烧录 FPGA。JTAG AXI 通道仍保留，
但上位机不能同时使用 JTAG 与 UDP 访问。9 月 28 日初始试验协商为
100 Mbps，通过两张镜像提交和求偶 8 步事件测试；9 月 30 日 P0 又在两次
独立烧录会话中验证完整视觉、三组长求偶、异常镜像拒绝与恢复。P0 期间
主机网卡查询显示 1 Gbps 协商速率。

## Hardware and address / 硬件与地址

- Board: ALINX AXKU115 V1.0, `xcku115-flva1517-2-i`.
- PHY: KSZ9031RNX, 1.8 V RGMII, board pinout from `support/AXKU115_UG.pdf`.
- FPGA/PHY port: 192.168.1.128/24, UDP 4321, MAC `02:00:00:00:00:15`.
- Configure the host Ethernet adapter to a free address such as
  192.168.1.10/24. Connect directly or through a Gigabit-capable switch.
- The protocol has no authentication or encryption. Use an isolated lab link;
  do not attach this control port to an untrusted network.
- The 50 MHz board oscillator drives 200 MHz engine and 125 MHz RGMII clocks;
  the forwarded TX clock is shifted by 95.625 degrees. The PHY provides RX clock;
  five fixed input delays compensate its RXC global-buffer insertion.
- Runtime graph capacity remains 6,279 neurons and 350,185 synapses.

板卡 IP 固定为 `192.168.1.128/24`、UDP 端口 `4321`；建议将电脑网卡手动设置
为 `192.168.1.10/24`。该协议没有认证或加密，只应在隔离的实验网络使用。
核心容量仍是 6,279 个神经元、350,185 条突触。

## Build and program / 构建与烧录

To program the currently verified artifact, run `program_ethernet_bitstream.ps1`.
For a fresh build from the current RTL, use `build_ethernet_bitstream.ps1`
with a distinct `CNS2FPGA_BUILD_NAME`, inspect its timing/DRC reports, and
explicitly select that new bitstream only after signoff. The programming
script checks that exactly one xcku115 target and one JTAG AXI
core are present. It does not upload a network image. The default programming
artifact is now `build/runtime_eth_portfilter_200mhz/cns2fpga_runtime_eth_portfilter_200mhz.bit`
(SHA-256 `581354A62C8C7AEB134F300E7EA1928D8B681B996807710C61E307B33530D8F8`).
The old `runtime_eth_200mhz` image predates the receive-side fix and must not
be used for deployment tests.

The repaired 200 MHz image passes routed setup/hold timing (WNS +0.012 ns,
WHS +0.010 ns), has no unrouted nets, and has zero DRC errors. See
`reports/runtime_eth_portfilter_200mhz/run_status.txt`. The route uses 32,422
LUTs, 11,670 flip-flops, 592 RAMB36, six RAMB18, and four DSPs. Narrow
timing margins still warrant repeated board trials.

执行 `build_ethernet_bitstream.ps1`，再执行
`program_ethernet_bitstream.ps1`。烧录脚本检查唯一的 xcku115 目标及 JTAG AXI
核心，不上传网络镜像。默认烧录的已修复镜像为
`build/runtime_eth_portfilter_200mhz/cns2fpga_runtime_eth_portfilter_200mhz.bit`；
旧的 `runtime_eth_200mhz` 镜像存在接收阻塞问题，不应再用于部署测试。
修复镜像满足 200 MHz 静态时序、完成布线且 DRC 0 错误，但余量较小，
网络镜像上传、求偶短试验及 P0 双会话重复试验已通过；时序余量仍小。

## Upload protocol / 上传协议

The host-side program is `host/upload_image_udp.py`. It validates an image
using the Step 14 preflight tool before opening a socket. Every datagram
contains a 16-byte little-endian `CNSE` header (`<4sBBHII>`: magic, opcode,
region, word count, sequence, value) and, for DATA, up to 64 little-endian
32-bit words. The FPGA replies only after performing writes and reading back
`IMAGE_STATUS`, using a 16-byte `CNSA` ACK (`<4sBBBBII>`). Opcodes are
BEGIN=1, DATA=2, COMMIT=3, STATUS=4. ACK status values are OK=0,
INVALID=1, SEQUENCE=2, ENGINE=3, DUPLICATE=4. The sender retries timed-out
datagrams; sequence numbers prevent reapplying DATA or COMMIT. After COMMIT,
the sender issues an independent STATUS check.

上位机脚本先运行第 14 步镜像预检，再通过 UDP 发送。每个数据包最多包含 64 个
32 位字，设备处理完成并读回 `IMAGE_STATUS` 后才应答；超时可重发，序号避免
重复写入。COMMIT 后还会独立查询状态。

For a later board trial, for example:

```powershell
python .\host\upload_image_udp.py "<validated image directory>" --board-ip 192.168.1.128 --source-ip 192.168.1.10
```

Only run a graph upload after the read-only STATUS probe succeeds. Do not
upload concurrently with JTAG access. The verified upload scripts temporarily
added 192.168.1.10 and removed it afterwards.
只有只读 STATUS 连通测试通过后才运行镜像上传，且不能与 JTAG 同时访问。

## Verified board result / 上板结果

- Visual left image: 226 neurons, 1,730 edges, 4,816 words/81 packets,
  checksum `6C233D31`; COMMIT passed and a corrected independent STATUS
  returned image status 1. The visual wrapper's first extra STATUS used a
  stale sequence number and printed FAIL; the raw log is preserved.
- Courtship image, without reprogramming: 6,279 neurons, 350,185 edges,
  738,044 words/11,538 packets, checksum `45AEAAAE`; COMMIT and independent
  STATUS passed, image epoch 2. The 8-step smoke trial matched all 2,475
  ordered fixed-CPU events, had zero missed steps/fault flags, and reached
  199,699/200,000 cycles at the slowest step.
- Rebuild the initial audit snapshot with `scripts/build_deployment_evidence.py`;
  `reports/deployment_evidence_v1.json` links its raw logs, captures, CPU
  reference, bitstream hash, and routed reports. Its earlier 250-step visual
  and 13-condition courtship references were from other implementations;
  the later P0 campaign below directly repeated visual and three long
  courtship conditions on this Ethernet bitstream.
- `scripts/build_old_new_board_comparison.py` independently compares the
  dedicated and Ethernet-loaded courtship `smoke8` raw captures. It records
  byte-identical 2,475-event files and eight unchanged seven-word summary
  fields, while each step's cycle count increases by its spike count. See
  `reports/old_new_board_comparison_v1.json`. This is an observed short-trial
  relation, not proof of a specific RTL cause or of long individual-event equality.

视觉镜像和求偶镜像已在同一 bit 文件上依次加载、校验和执行；中间未重新综合或
烧录 FPGA。原专用版的 13 条求偶长试验仍是独立证据；新网口版 P0 又完成其中
15、35、65 ms 三个长条件，并在两次会话中重复。

### P0 repeated physical validation / P0 双会话上板验证

On 30 September 2026, the same bitstream SHA-256
`581354A62C8C7AEB134F300E7EA1928D8B681B996807710C61E307B33530D8F8`
was programmed once per session. Each session loaded visual at epoch 1 and
matched all 560 ordered events in 250 steps, then loaded courtship at epoch 2
without reprogramming and matched all 2,475 smoke8 events. Three 4,308-step
courtship conditions (IPI 15/35/65 ms) matched fixed-CPU response-window
population counts and 34,464 per-step non-cycle fields against the older
dedicated capture. At this P0 stage, no long individual-event raster was captured. The maximum
courtship core step was 199,699/200,000 cycles with no missed deadline or
fault flag. Both sessions rejected interrupted/incomplete and invalid-index
uploads, then restored the full visual trial at epoch 3. Corresponding raw
event and summary files were byte-identical across sessions.

Host-inclusive visual upload durations were 0.173/0.135 s and courtship
durations 1.360/1.848 s. These are not line-rate measurements; the host NIC
reported 1 Gbps during P0. The separately recorded initial run negotiated
100 Mbps. Audit: `reports/p0_board_audit_v1.json`; link observation:
`reports/p0_host_link_observation_20260930.md`. The physical protocol is
`host/run_ethernet_p0_campaign.ps1`, and
`scripts/audit_p0_campaign.py` independently rechecks the captures offline.

P0 两轮试验的视觉 250 步各匹配 560 个有序事件，求偶 8 步各匹配 2,475 个；
每轮还运行 15、35、65 ms 的 4,308 步求偶条件。异常上传均被拒绝，有效视觉
镜像恢复后再次通过。P0 长试验仅比对群体计数与逐步摘要；之后扩展事件容量并完成全事件采集。

## Expanded-event physical campaign / 扩展事件容量实测

A separate 200 MHz runtime bitstream expands the event store from 65,536 to
131,072 entries (SHA-256 `D4C9378D461147062FA5DC590CB3647D241C789B01CC6255F38DA16CB21990DF`).
Route signoff was positive (setup +0.008 ns, hold +0.030 ns; 618 BRAM36).
The first programming attempt had no UDP ACK and bad received FCS frames;
reprogramming the *same* bitstream restored STATUS and upload. Without any
further reprogramming, the board then loaded the courtship graph and ran
IPI 15/35/65 ms for 4,308 steps each. Complete ordered event lists contained
40,868/74,765/99,349 entries, respectively, and matched independently
generated fixed-CPU events exactly (zero mismatches). All per-step group and
synapse-operation fields also matched the earlier dedicated board captures;
no overflow, deadline miss, or fault was flagged. This is one successful
campaign after a failed first attempt, not a reliability-rate estimate.
Evidence: `reports/long_event_board_audit_v1.json` and
`reports/long_event_board_20260930/`. The old and expanded runtime captures
for IPI 15 ms had byte-identical events and summaries.

扩展版 bit 文件保持 200 MHz，将事件存储从 65,536 增至 131,072 条。首次配置后
网口未应答，重新配置同一 bit 文件后成功；随后仅通过网口加载网络，完整采集
15/35/65 ms 三组长试验的 40,868/74,765/99,349 个有序单神经元事件，
均与独立 CPU 参考逐条一致。首次失败仍保留在审计记录中。

An additional speed-controlled physical test on 2026-10-01 used the **same
expanded-event bitstream** at a measured 100-Mbps full-duplex link. One
programming operation passed 20/20 read-only STATUS probes, a 738,044-word
courtship image upload, and an eight-step trial with 2,475/2,475 ordered
events equal to fixed CPU; the post-trial bad-FCS count was zero. Earlier
expanded-image 1-Gbps configurations had zero good RX frames and hundreds of
bad-FCS frames, including after a reported full board power cycle. This
supports a link-speed/RGMII receive-path hypothesis but does not prove a
specific root cause or startup reliability. See
`reports/expanded_bit_100m_board_test_20261001.md` and
`reports/startup_stability_probe_20260930.md`. The PC NIC's original speed
setting and IP address were restored after the test.

2026-10-01 的实板同速率对照进一步表明：扩展事件版本在实际 100 Mbps 链路下，
20/20 次 STATUS、求偶网络网口上传及 8 步 2,475 个事件比对均通过，坏 FCS 为零。
此前千兆配置下的接收异常仍未定位，不能据此宣称已解决启动可靠性问题。

### V0.3 release disposition / V0.3 发布状态

The 100-Mbps capture has been independently rechecked offline, including
every ordered event, all eight step counts, image epoch/checksum, deadlines
and post-trial FCS diagnostics. Run `python scripts/audit_100m_board_test.py`
from this directory, or use its full repository-relative path. Evidence is
in `reports/expanded_bit_100m_audit_v1.json` and
`reports/expanded_bit_100m_20261001/` (raw capture and selected log excerpts).
The original 65,536-event runtime bitstream and the expanded 131,072-event
bitstream remain separate, hash-pinned artifacts; both are included in the
public package. Figure 10 and the manuscript report the additional 100-Mbps
result separately from the 30 September long-event campaign.

Further 1-Gbps tests are deferred. An unqualified cable is one possible
explanation; neither a cable fault nor a specific RGMII timing fault is
confirmed. See `reports/ethernet_100m_vs_1g_diagnosis_20261001.md` for the
read-only PHY/timing checks and the tests needed to distinguish them.

100 Mbps 的原始采集已离线重新核查：八步计数、2,475 个有序事件、镜像身份、
截止时间和坏 FCS 均通过。原版与扩展版 bit 文件分别保留并固定哈希，论文图 10
单独报告新增 100M 会话。按用户要求，1G 实测暂缓；网线不支持千兆只是待验证
解释，不能视作已经查明的原因。

## Verification / 验证

- `tests/run_udp_sim.ps1` runs `tests/tb_udp_command.sv` to check BEGIN,
  DATA ordering, duplicate suppression,
  out-of-order rejection, COMMIT, ACK fields and the 125/200 MHz bridge.
- The signed-off port-filter build is under `reports/runtime_eth_portfilter_200mhz`
  and `build/runtime_eth_portfilter_200mhz`; its routed setup, hold, routing,
  and DRC checks all pass.
- The Ethernet MAC/ARP/IP/UDP implementation is adapted from
  [alexforencich/verilog-ethernet](https://github.com/alexforencich/verilog-ethernet)
  commit `77320a9471d19c7dd383914bc049e02d9f4f1ffb`, MIT license in
  `vendor/COPYING`. Interface timing follows [AMD PG160](https://docs.amd.com/r/en-US/pg160-gmii-to-rgmii/Constraining-the-Core)
  and the [KSZ9031RNX datasheet](https://ww1.microchip.com/downloads/aemDocuments/documents/UNG/ProductDocuments/DataSheets/KSZ9031RNX-Data-Sheet-DS00002117.pdf).

## Public package note / 公开仓库说明

The GitHub-ready copy places the verified Ethernet bitstream at
`hardware/bitstreams/cns2fpga_runtime_eth_200mhz.bit` and omits generated
Vivado checkpoints and packet captures. It includes curated P0 board captures,
campaign/fault logs, and the audit JSON, along with three older publication
log excerpts. Complete original development transcripts remain local.
Historical PowerShell board wrappers default to this
machine's Vivado installation and NIC settings; override their parameters
before use elsewhere. `program_ethernet_bitstream.ps1` falls back to the
published bitstream when the development `build/` path is absent. The protocol
must only be used on an isolated lab link.

公开仓库中的已验证网口 bit 文件放在 `hardware/bitstreams/`；Vivado 临时文件和
抓包不发布。P0 的板上采集、试验及异常日志、审计 JSON 会保留；三份旧 `.log`
是去除本机身份与会话信息的公开摘录。完整开发日志仍保留在本地工作区。
历史上板脚本默认采用本机 Vivado 和网卡设置，
异机使用前须通过参数调整；若开发目录的 `build/` bit 文件不存在，烧录脚本会回退到
公开仓库中的 bit 文件。该无认证协议只能用于隔离的实验网络。
