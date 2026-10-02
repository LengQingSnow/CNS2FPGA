# Expanded-event runtime bitstream at a measured 100 Mbps — 2026-10-01

Result: **PASS for one programmed session at a measured 100-Mbps link**.
This is a speed-controlled connectivity, image-upload, and eight-step
execution test. It is not a cold-boot reliability estimate or a fix for the
previous 1-Gbps bad-FCS failures.

## Controlled conditions

- Board: ALINX AXKU115 V1.0; direct Realtek PC link.
- Expanded-event bitstream SHA-256:
  `D4C9378D461147062FA5DC590CB3647D241C789B01CC6255F38DA16CB21990DF`.
- PC Realtek interface index 23 was temporarily changed from its pre-existing
  `1.0 Gbps full duplex` driver setting (registry value 6) to `100 Mbps full
  duplex` (value 4). Windows reported an **actual** 100-Mbps link before and
  after programming and after the board trial. Source `192.168.1.10/24` was
  temporarily added beside the original `192.168.0.3/24`.
- Before switching bitstreams, the original Ethernet runtime image answered
  STATUS on the first attempt under the same forced-100-Mbps host setting.
- The expanded-event bitstream was programmed **once**. No resynthesis or
  bitstream edit was performed, and no reprogramming occurred between upload
  and execution.

## Observations

| Check | Result |
| --- | --- |
| First post-program STATUS | PASS, first request, 2.10 ms RTT |
| Repeated read-only STATUS | 20/20 PASS, all first requests |
| Courtship graph UDP upload | PASS, 738,044 words, 11,538 protocol packets, checksum `45AEAAAE` |
| Post-upload STATUS | PASS, image ready (`0x00000001`), correct next sequence 11,539 |
| Eight-step courtship board trial | PASS, 2,475 exact ordered events versus fixed-point CPU reference |
| Image identity and deadline | Epoch 1; checksum `45AEAAAE`; maximum core step 199,699/200,000 cycles |
| FPGA receive/FCS diagnostic after trial | Nonzero good Ethernet and UDP frame counts; bad-FCS count 0 |

The first *manual* post-upload STATUS probe used the fresh-board default
sequence 1 and received protocol status 2 (sequence mismatch), which is
expected after 11,538 upload/status commands. The immediately repeated probe
with next sequence 11,539 passed. This was not a transport timeout or image
fault. The upload tool itself had already verified the committed ready state.

The final JTAG diagnostic status `0x0001FD1F` encoded 100-Mbps MAC mode, in
contrast with the earlier failed expanded-event 1-Gbps status `0x000200E7`.
Its RX and TX frame counters were nonzero, and the error register was
`0x00000000`. Thus the expanded-event image can receive valid frames and
execute the uploaded courtship circuit at 100 Mbps. Prior 1-Gbps failures
remain unresolved; speed/RGMII receive timing is a supported hypothesis,
not a proven root cause. One passing 100-Mbps configuration cannot establish
startup reliability across repeated programming or power cycles.

## Host restoration and board state

After the trial, the temporary `192.168.1.10/24` address was removed and the
Realtek speed/duplex driver setting restored to its original registry value
6 (`1.0 Gbps full duplex`). The original `192.168.0.3/24` remained. The
physical link happened to report 100 Mbps immediately after restoration;
the driver setting and the actual negotiated speed are separate observations.
The board was left with the expanded-event bitstream and committed courtship
image; no further programming was done during cleanup.

Evidence logs in this directory are prefixed `new_bit_100m_`. The raw
eight-step capture is under
`../build/new_bit_100m_smoke8_20261001/` (registers, summary and event words).
The comparison with previous failures and the original bitstream is in
`startup_stability_probe_20260930.md`.
