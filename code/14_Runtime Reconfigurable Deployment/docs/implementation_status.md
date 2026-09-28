# 200 MHz runtime bitstream status / 200 MHz 运行时 bit 文件状态

Date: 2026-09-27. Part: `xcku115-flva1517-2-i`. Vivado: 2021.2.

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

## Physical validation gate

The board test has **not** run. At 2026-09-27 01:44 and again at 01:59 local
time, Vivado `hw_server` reported no JTAG targets after refresh; Windows did not show a
present Digilent/FTDI/JTAG USB device. No FPGA was programmed. After power and
USB-JTAG are restored, the next sequence is:

1. Probe and uniquely identify the AXKU115 JTAG target.
2. Program this signed-off bitstream once.
3. Upload the courtship image, run/capture its smoke trial.
4. Upload the visual-left image without calling `program_hw_devices` again,
   run/capture its trial, and compare both captures with references.

Successful simulation and timing closure establish an offline engineering
candidate. The no-recompile/no-reprogram deployment claim remains physically
unverified until the two-image board sequence passes.
