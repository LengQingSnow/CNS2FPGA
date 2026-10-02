# Why 100 Mbps passes while 1 Gbps sometimes fails (2026-10-01)

## Finding

The failure is in the receive path **before** the UDP graph-loader/parser: in
the failed 1-Gbps sessions the MAC reported hundreds of bad-FCS frames and
zero valid Ethernet/UDP frames. The same expanded-event bitstream, programmed
once at a measured 100-Mbps link, completed 20/20 STATUS requests, a full
738,044-word courtship graph upload, and a 2,475-event exact trial with zero
bad FCS. This establishes a speed-dependent receive-integrity problem, not
that 1 Gbps is inherently unsupported or that the graph image is too large.

The **physical root cause is not yet proven**. Two leading possibilities are:

1. PHY-to-FPGA RGMII sampling margin at the 125-MHz DDR receive interface,
   including PCB skew, FPGA input delay and clock insertion, PVT variation,
   or reset/negotiation state. At 100 Mbps the PHY RX clock is 25 MHz, versus
   125 MHz at 1 Gbps, making its half-cycle 20 ns rather than 4 ns.
2. Marginal 1000BASE-T copper link (cable, connector, magnetics, NIC or PHY).
   Unlike the previous observed 1-Gbps P0 session, the host currently reports
   an actual **100-Mbps** link even though its Realtek advanced setting says
   "1.0 Gbps full duplex". The driver setting is not the negotiated speed.

These mechanisms can coexist. A MAC bad-FCS count alone cannot identify
which side of the PHY produced the corruption.

## Evidence ledger

| Condition | Actual link / image | Good RX | Bad FCS | Other result |
| --- | --- | ---: | ---: | --- |
| Prior P0 preprobe, 2026-09-30 | Host reported 1 Gbps; original bit | nonzero (`RX_COUNTS=0x01CD011A`) | 0 | Demonstrates a historical working 1-Gbps session; not a simultaneous A/B. |
| Three expanded-bit startup failures | FPGA MAC speed field 2 (1 Gbps); expanded bit | 0 | 365, 370, 354 | JTAG ID/PHY link/RX clock alive; no UDP ACK. |
| Original bit A/B, 2026-10-01 | Actual 100 Mbps | 275 Ethernet, 168 UDP | 0 | STATUS replied. |
| Expanded bit, 2026-10-01 | Actual 100 Mbps | nonzero | 0 | 20/20 STATUS; full upload; 2,475/2,475 ordered events. |
| Current PC link | Actual 100 Mbps despite Realtek setting 1 Gbps full duplex | — | — | No board reprogramming done for this audit. |

Sources: `p0_ethernet_preprobe_diag_20260930.log`,
`p0_host_link_observation_20260930.md`,
`startup_stability_probe_20260930.md`,
`expanded_bit_100m_board_test_20261001.md`,
`new_bit_100m_post_trial_diag_20261001.log`.

## Static and PHY checks (read-only)

- The board uses a KSZ9031RNX PHY. MDIO reads on the currently running
  expanded image returned MMD2 pad-skew registers `0x04=0x0077`,
  `0x05=0x7777`, `0x06=0x7777`, and `0x08=0x3DEF`: the RX clock's low-five-bit
  setting is 15 and the RX data/control settings are 7, the documented
  defaults. The PHY therefore has not obviously been given a wrong custom
  RGMII skew setting. See `phy_rgmii_skew_read_20261001.log`.
- The XDC models a 1-ns setup/hold window around both RX clock edges. The
  five FPGA RX IDELAYE3 cells use fixed `COUNT=400`. AMD UG571 says COUNT
  mode is uncalibrated and lacks voltage/temperature compensation; 400 taps
  must **not** be interpreted as a guaranteed fixed delay in nanoseconds.
- An offline Vivado 2021.2 audit reopened the two *existing* routed DCPs;
  it did not resynthesize, write a bitstream, or touch the board. All modeled
  RX-input paths met their constraints. Worst setup/hold slack, respectively:
  original bit `+2.632/+0.358 ns`; expanded bit `+2.101/+0.668 ns`.
  Considering the actual DDR input registers rather than the auxiliary
  `raw_rx_ctl_seen` monitor, worst setup was `+4.060 ns` original and
  `+3.469 ns` expanded. The DDR data-path delays were nearly identical.
  Thus there is **no demonstrated static timing violation or simple
  new-bit-only hold regression**. The STA figures depend on assumed external
  PHY/PCB timing and do not measure the hardware data eye.

Timing artifacts: `rx_input_timing_old_20261001_{max,min}.rpt`,
`rx_input_timing_new_20261001_{max,min}.rpt`. Audit script:
`../scripts/audit_rx_input_timing.tcl`.

## Discriminating test, before any redesign

1. Use a known-good short Cat5e/Cat6 cable and preferably a known-good
   gigabit switch/another NIC. Record **actual negotiated speed** on both
   ends, not merely the Windows speed setting. If the link still cannot
   negotiate 1 Gbps, inspect copper pairs/connector/PHY first.
2. With a measured 1-Gbps link and the *same already-built bitstream*, send
   a small repeatable STATUS probe while recording FPGA good-RX/bad-FCS
   deltas and the PHY's Clause-22 register `0x15` RXER counter (receive
   symbol-error frames). A rising PHY RXER supports a copper/PHY-side
   problem. A zero PHY RXER with rising FPGA bad FCS instead strengthens
   the RGMII-sampling hypothesis, though it does not prove it by itself.
   Note that reading RXER is read-to-clear, so capture a baseline and delta
   deliberately.
3. Only if the copper side tests clean, characterize the RGMII eye by
   controlled RX delay/skew settings or calibrated delay, one variable per
   image, then repeat 1-Gbps cold-start and packet/FCS tests. This step
   requires a new bitstream and board programming; no such change was made
   in this diagnosis.

Official references:

- Microchip KSZ9031RNX datasheet, RGMII clocks, default RX clock skew,
  pad-skew registers and RXER register:
  https://ww1.microchip.com/downloads/aemDocuments/documents/UNG/ProductDocuments/DataSheets/KSZ9031RNX-Data-Sheet-DS00002117.pdf
- AMD UG571, IDELAYE3 COUNT versus TIME mode:
  https://docs.amd.com/api/khub/documents/kFbaUC5HGcXyGNauhgU6Gw/content

No RTL, bitstream, FPGA image, host network setting, or GitHub repository
was changed by the timing/diagnostic audit; only this report, its four timing
reports, and the read-only audit script were added locally.

## V0.3 release note (2026-10-02)

The user has deferred further 1-Gbps testing pending a later cable/link
check. The possibility that the cable cannot sustain gigabit operation is
not a confirmed diagnosis. The measured 100-Mbps PASS and the earlier
1-Gbps receive failures are preserved as separate observations. No new
physical test or board programming was performed for this release update.
Complete original diagnostic logs remain in the development workspace;
the public package contains this report, the startup report, four timing
reports, and the archived 100-Mbps capture with selected log excerpts.
