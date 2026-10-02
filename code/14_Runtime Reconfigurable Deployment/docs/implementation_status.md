# 200 MHz runtime bitstream status / 200 MHz 运行时 bit 文件状态

Build date: 2026-09-27; physical validation: 2026-09-30.
Part: `xcku115-flva1517-2-i`. Vivado: 2021.2.

One FPGA image contains the fixed `safe_wf24` compute architecture and graph
storage. The graph is written after configuration through JTAG AXI-Lite; the
same bitstream can receive another compatible graph without recompilation or
another FPGA programming operation.

## Offline evidence

| Check | Result |
| --- | --- |
| Setup WNS at 200 MHz | +0.043 ns |
| Hold WHS | +0.030 ns |
| Unrouted / partially routed nets | 0 / 0 |
| DRC errors | 0 |
| Bus skew minimum slack | +3.533 ns |
| Synthesis utilization | 585 RAMB36, 3 RAMB18, 4 DSP48E2 |
| Synthetic two-image reload | PASS, two epochs and distinct spike counts |
| Real visual-left image | PASS, 226 neurons, 1,730 synapses, 250 exact step counts |
| Real courtship image | PASS, 6,279 neurons, 350,185 synapses, 8 exact step counts |
| Courtship max timestep latency | 199,699 cycles, below the 200,000-cycle 1 ms target |

Bitstream: `build/runtime_jtag_200mhz/cns2fpga_runtime_jtag_200mhz.bit`
(14,806,256 bytes). SHA-256:
`95F9B50EE03804DDC211828A9FBD3B3171B45BC3FFB79F9F3B2407F0D3190E52`.
The public-repository package places the identical bitstream at
`hardware/bitstreams/cns2fpga_runtime_jtag_200mhz.bit`.

Vivado reported 85 non-error DRC warnings: input/output pipelining advice,
LUT equation term checks, BRAM write-width and write-first collision advisories,
and one no-routable-load warning. These are not a replacement for board testing.

## Physical validation gate — PASS

The earlier 27 September attempt was blocked because no Digilent JTAG device
was visible. The connected AXKU115 was subsequently detected and tested on
30 September. The signed-off bitstream was programmed once; visual image
epoch 1 produced 560 exact ordered events in 250 steps, then courtship image
epoch 2 produced 2,475 exact ordered events in eight steps without another
FPGA programming operation. A transport interruption, incomplete COMMIT and
invalid postsynaptic index were rejected. A valid visual reload at epoch 4
again passed 250 steps with 560 exact events. Both captures and fault logs
are preserved under `build/p0_jtag_20260930/` and
`build/p0_jtag_recovery_logged_20260930/`; the cross-transport audit is under
`../15_Ethernet_Runtime_Deployment/reports/p0_board_audit_v1.json`.

This closes the physical two-image and tested-recovery gate for this bitstream.
It does not establish arbitrary graph compatibility, independent-board
reproduction, or biological model validity.
