# Step 15 — AXKU115 Ethernet runtime deployment / 网口运行时部署

This step adds an RGMII/UDP graph loader to the existing 200 MHz runtime
engine. A single FPGA bitstream can accept different preflighted network images
without being recompiled or reprogrammed. The JTAG AXI path remains available
for register access and experiments; host software must not use JTAG and UDP
concurrently. Earlier diagnostics observed a 1 Gbps link and board-to-PC
broadcast traffic. The final visual-to-courtship upload run negotiated
100 Mbps. Both image commits and independent status checks passed on the same
programmed bitstream; the courtship image also passed an eight-step trial.

本步骤给原有 200 MHz 运行时核心增加 RGMII/UDP 网络图加载器。烧录一次后，
不同网络镜像可通过网口更换，无需重新综合或烧录 FPGA。JTAG AXI 通道仍保留，
但上位机不能同时使用 JTAG 与 UDP 访问。早期诊断观察到 1 Gbps 链路；最终
视觉到求偶的上传试验协商为 100 Mbps。两张镜像在同一 bit 文件下完成 COMMIT
和独立 STATUS 校验，求偶镜像另通过 8 步逐事件上板试验。

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
网络镜像上传和求偶短试验已通过；时序余量仍小，需重复上板试验。

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
- Rebuild the audit snapshot with `scripts/build_deployment_evidence.py`;
  `reports/deployment_evidence_v1.json` links the raw logs, captures, CPU
  reference, bitstream hash, and routed reports. The older 250-step visual
  and 13-condition courtship results are from other implementations, not this
  Ethernet bitstream.
- `scripts/build_old_new_board_comparison.py` independently compares the
  dedicated and Ethernet-loaded courtship `smoke8` raw captures. It records
  byte-identical 2,475-event files and eight unchanged seven-word summary
  fields, while each step's cycle count increases by its spike count. See
  `reports/old_new_board_comparison_v1.json`. This is an observed short-trial
  relation, not proof of a specific RTL cause or equality on longer trials.

视觉镜像和求偶镜像已在同一 bit 文件上依次加载、校验；未重新综合或烧录 FPGA。
新 bit 文件上的求偶 8 步试验与 CPU 的 2,475 个有序事件完全一致。视觉 250 步
及求偶 13 条长试验属于此前实现，不能算作新 bit 文件的重复实验。

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
Vivado checkpoints, packet captures, and most diagnostic logs. Its three
included `.log` files are labeled publication excerpts with host/session
metadata removed; the complete original transcripts stay in the local
development workspace. Historical PowerShell board wrappers default to this
machine's Vivado installation and NIC settings; override their parameters
before use elsewhere. `program_ethernet_bitstream.ps1` falls back to the
published bitstream when the development `build/` path is absent. The protocol
must only be used on an isolated lab link.

公开仓库中的已验证网口 bit 文件放在 `hardware/bitstreams/`；Vivado 临时文件、
抓包和多数诊断日志不发布。所附三份 `.log` 是删去本机身份和会话信息的公开摘录，
完整原始日志仍保留在本地开发工作区。历史上板脚本默认采用本机 Vivado 和网卡设置，
异机使用前须通过参数调整；若开发目录的 `build/` bit 文件不存在，烧录脚本会回退到
公开仓库中的 bit 文件。该无认证协议只能用于隔离的实验网络。
