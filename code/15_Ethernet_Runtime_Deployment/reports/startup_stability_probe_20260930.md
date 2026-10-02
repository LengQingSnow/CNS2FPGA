# Expanded-event runtime Ethernet startup probe — 2026-09-30

Status: **FAIL / stopped after two consecutive JTAG configurations**. This is
not a 10–20-cycle reliability estimate and did not involve a full board power
cycle. The board was left programmed with the expanded-event bitstream, but
no graph was uploaded in this probe.

## Fixed test conditions

- ALINX AXKU115 V1.0; direct PC Realtek-to-board Ethernet connection.
- Bitstream SHA-256:
  `D4C9378D461147062FA5DC590CB3647D241C789B01CC6255F38DA16CB21990DF`.
- PC source `192.168.1.10/24` temporarily added alongside the pre-existing
  `192.168.0.3/24`; board target `192.168.1.128:4321`.
- The temporary PC address was removed after the stopped probe; `ipconfig`
  then showed `192.168.0.3` and no `192.168.1.10` on the wired adapter.
- Same unmodified bitstream, cable, source IP, STATUS probe and FPGA board in
  both JTAG configuration attempts. No RTL or bitstream rebuild was performed.

## Observations

| Attempt | JTAG configuration | UDP STATUS (five 1-s attempts) | FPGA valid RX frames | Bad FCS frames | Diagnostic status |
| --- | --- | --- | ---: | ---: | --- |
| 1 | PASS; one JTAG AXI core recognized | No reply | 0 | 365 (`0x016D`) | `0x000200E7` |
| 2 | PASS; same bitstream | No reply | 0 | 370 (`0x0172`) | `0x000200E7` |

Both times JTAG read firmware ID `0x434E5352`, PHY and MAC reset-release
status bits were high, and the FPGA-side RX clock counter changed. An MDIO
scan after attempt 1 found one KSZ9031 at PHY address 1 with ID1 `0x0022`;
basic status `0x796D` indicated link up. RX good/UDP and TX good/UDP counters
were all zero. The bad-FCS counter is the low 16 bits of diagnostic register
`0xA4` per `rtl/cns2fpga_eth_stack.v`. The host learned no ARP neighbor for
`192.168.1.128`. ICMP ping is not a valid board protocol check.

For contrast, earlier successful original-runtime P0 logs recorded diagnostic
status `0x0002851F`, nonzero RX counters, and zero bad-FCS frames. A previous
expanded-event attempt also initially had no UDP ACK and bad FCS, then worked
after reprogramming the same bitstream. The present test shows that one
reprogramming is *not* a reliable recovery: its second configuration still
failed. It does not establish a failure rate, and cannot distinguish power-on
sequence, PHY RGMII receive timing/skew, cable/NIC effects, or other receive
path faults. A pure command-parser error is less likely because no good
Ethernet frames reached that layer; this is an inference, not a diagnosis.

## Stop and next discriminating test

No further configurations were attempted after the second failure. The next
test should be one **true board power-off/power-on cycle**, followed by the
same read-only STATUS and JTAG diagnostics before uploading a graph. This
distinguishes physical power sequencing from JTAG-only reconfiguration.
If failures persist, compare PHY RGMII internal delay/strap settings and
received-frame timing against the KSZ9031RNX and AXKU115 constraints, then
test one controlled reset/timing change per bitstream. Do not revise the
paper's existing long-event PASS claim; annotate any future reliability
claim separately with a complete attempt denominator.

Raw local logs: `startup_cycle_01_program_20260930.log`,
`startup_cycle_01_status_20260930.log`, `startup_cycle_01_diag_20260930.log`,
`startup_cycle_01_mdio_20260930.log`, and the corresponding cycle-02
program/status/diagnostic logs.

## User-reported true power cycle and one first configuration

The user subsequently reported a complete board power-off/power-on. The PC
wired link was connected; the temporary source IP was re-added, and a
pre-configuration STATUS probe timed out twice. The same pinned expanded-event
bitstream was then programmed **once** by JTAG successfully, with one JTAG
AXI core detected. Five post-configuration STATUS attempts all timed out.
Read-only JTAG diagnostics again showed ID `0x434E5352`, status
`0x000200E7`, zero valid RX/UDP and TX frames, a changing RX clock, and 354
bad-FCS frames (`0x0162`). This is the same failure signature as the two
earlier JTAG-only configurations. No graph upload or second configuration
was attempted after the power cycle. The physical off-duration and power
rails were not independently instrumented.

Thus a user-reported full power cycle did not restore this bitstream's
Ethernet receive path in the recorded first configuration. The next
discriminating A/B test would be to program the previously successful
original Ethernet runtime bitstream once under the same host/cable/link
conditions, run read-only STATUS and diagnostics, and stop. If it passes,
the expanded build's RGMII placement/timing or startup implementation merits
focused comparison; if both fail, investigate the shared PHY, cable and host
link. Do not infer a proven RTL root cause from the bad-FCS count alone.

Power-cycle logs: `cold_boot_ip_setup_20260930.log`,
`cold_boot_preprogram_status_20260930.log`, `cold_boot_program_01_20260930.log`,
`cold_boot_status_01_20260930.log`, and `cold_boot_diag_01_20260930.log`.

At the time this addendum was saved, the power-cycle test's temporary PC
address `192.168.1.10/24` was **still present**: the Windows UAC prompt for
removal had not completed. Do not mark host networking restored until
`ipconfig` shows only the original `192.168.0.3/24` address on that adapter.

## Original-versus-expanded bitstream A/B, 2026-10-01

Before this A/B, the PC wired adapter showed disconnected/0 bps. Read-only
JTAG inspection found a different design with two ILA cores and no project
JTAG AXI core, so the disconnected state was not evidence about either
Ethernet runtime bitstream. The board was powered and JTAG reachable.

The original signed-off Ethernet runtime bitstream
(`581354A62C8C7AEB134F300E7EA1928D8B681B996807710C61E307B33530D8F8`)
was programmed **once**. The first read-only STATUS request timed out while
the physical link was settling; the second returned a valid board ACK in
2.74 ms. A subsequent request returned a valid ACK on its first try in
1.19 ms. Windows learned dynamic ARP neighbor `192.168.1.128` at
`02-00-00-00-00-15`. No network graph was uploaded.

JTAG diagnostics on the original runtime showed ID `0x434E5352`, status
`0x0001FD1F`, 275 good received Ethernet frames, 168 received UDP headers,
2 good transmitted frames, 1 transmitted UDP header, and **zero bad FCS**.
However, the host reported an actual **100 Mbps** link and the bitstream
status encoded MAC speed 1 (100 Mbps). In contrast, the expanded-event
failure status `0x000200E7` encoded MAC speed 2 (1 Gbps), with zero good
frames and hundreds of bad FCS frames. The Realtek advanced property was
displayed as `1.0 Gbps full duplex` during the A/B, but the actual link
reported 100 Mbps; the setting alone is not evidence of negotiated rate.

This A/B proves the cable, host IP, PHY, ARP, UDP path and original image can
work on the current board at 100 Mbps. It is **not a speed-matched
old-versus-expanded comparison**. The observations are consistent with a
1-Gbps RGMII receive timing/skew issue, but do not identify a root cause or
exclude an expanded-bitstream-specific startup/placement issue. The next
controlled comparison should establish the *same measured negotiated speed*
for both images before drawing a bitstream-specific conclusion, recording
link speed and FPGA good/bad-FCS counters at each attempt.

A/B local logs: `ab_precheck_jtag_20261001.log`,
`ab_old_bit_program_20261001.log`, `ab_old_bit_status_20261001.log`, and
`ab_old_bit_diag_20261001.log`.

The PHY's standard auto-negotiation restart was then issued once without
changing the bitstream. The actual host link stayed at 100 Mbps and STATUS
still replied (2.01 ms). A single restart of the PC's dedicated Realtek
adapter, retaining its pre-existing `1.0 Gbps full duplex` property, also
failed to negotiate 1 Gbps: the link returned `Up, 100 Mbps`. That adapter
restart removed the temporary ActiveStore `192.168.1.10` address, leaving
only the original `192.168.0.3/24`; the next UDP probe failed locally with
WinError 10049 (source address absent), **not** as a board timeout. No further
speed attempts or FPGA configurations were made. Logs:
`ab_old_bit_autoneg_20261001.log`,
`ab_old_bit_after_autoneg_status_20261001.log`,
`ab_old_bit_nic_renegotiate_20261001.log`, and
`ab_old_bit_post_nic_status_20261001.log`.

## Subsequent speed-controlled test

On 2026-10-01 the expanded-event bitstream passed a separate, measured
100-Mbps physical session: 20/20 STATUS replies, a complete courtship UDP
upload, 2,475/2,475 ordered smoke8 events, and zero bad FCS after the trial.
See `expanded_bit_100m_board_test_20261001.md`. This narrows the failure
conditions but does not prove the specific 1-Gbps fault mechanism or a
repeated-start reliability rate.
