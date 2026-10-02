# CNS2FPGA execution status — V0.3, 2026-10-02

The original workflow has engineering artifacts. Paper is a cross-cutting
publication directory; Steps 14–15 cover runtime graph deployment. This is not
a claim that the biological hypotheses or a publishable paper are complete.

| Step | Delivered evidence | Status |
| --- | --- | --- |
| 1–2 | Pinned MaleCNS v1.0 data; configurable courtship and visual path extraction | Completed |
| 3 | Float CPU LIF reference | Completed as engineering model |
| 4 | Biological interpretation, ROI/alias checks, intervention analyses | Conditional; biological validation remains open |
| 5 | Fixed-point envelope and selected `safe_wf24` format | Completed |
| 6 | Generic CSR-to-hex-memory compiler and round-trip checks | Completed |
| 7–8 | Time-multiplexed RTL and CPU/RTL full-state comparisons | Completed |
| 9 | 200 MHz courtship AXKU115 bitstream and physical measurements | Completed |
| 10 | 13-condition courtship float/fixed/FPGA comparison | Completed |
| 11 | 65 CPU perturbation trials, three board noise trials and width envelope | Completed within stated measurement limits |
| 12 | 226-neuron visual circuit, two compiler images, RTL and 250-ms KU115 trial | Completed engineering transfer |
| 13 | Manual type-level wiring baseline, four width comparisons, lateralized discriminating stimulus | Completed; manual graph is intentionally unmatched |
| Paper | Full manuscript, ten figures, seven main tables, 36 data snapshots and SHA-256 manifest | Updated with expanded-event long-trial and measured-100-Mbps evidence; biological validation remains open |
| 14 | JTAG runtime two-image physical test and interrupted/invalid-image recovery | PASS: one bitstream, visual 560 and courtship 2,475 ordered events, recovery at epoch 4 |
| 15 | Ethernet runtime visual/courtship switch, three long conditions and fault recovery in two P0 sessions; later expanded-event bitstream | PASS: P0 visual and courtship summaries; expanded bit captured 40,868/74,765/99,349 exact ordered courtship events in one successful 4,308-step-per-condition campaign after same-bit reprogramming |

The main local results are [courtship experiment](10_Complete%20Courtship-Song%20Circuit%20Experiment/outputs/courtship_song_v1/report.md),
[robustness](11_Courtship-Song%20Robustness/outputs/courtship_song_robustness_v2/report.md),
[visual board verification](12_Visual-to-Steering%20Circuit/outputs/visual_left_board_v0/report.md),
[baselines](13_Baselines%20and%20Ablations/README.md), and
[full paper](Paper/manuscript_full_v2.md), and
[Ethernet deployment evidence](15_Ethernet_Runtime_Deployment/reports/deployment_evidence_v1.json), and
[P0 independent board audit](15_Ethernet_Runtime_Deployment/reports/p0_board_audit_v1.json).
The [long-event board audit](15_Ethernet_Runtime_Deployment/reports/long_event_board_audit_v1.json)
records the initial failed Ethernet attempt as well as the successful retry.

The same expanded-event bitstream additionally passed one measured-100-Mbps
session: 20/20 STATUS replies, full courtship graph upload, 2,475 exact ordered
events over eight steps and zero bad FCS. See the
[100-Mbps audit](15_Ethernet_Runtime_Deployment/reports/expanded_bit_100m_audit_v1.json).
Earlier 1-Gbps receive failures remain unresolved. Cable capability is a
hypothesis, not a confirmed cause; further gigabit tests are deferred at the
user's request. No FPGA programming or new physical trial was performed
during the 2 October release preparation.

Remaining scientific work: independently map experimental ROI/driver lines to
MaleCNS cells; constrain visual and auditory input encoding, neuronal dynamics
and observation readouts with measured data; then use held-out conditions to
test biological predictions. If a publication asserts energy efficiency, add
board power measurements. None of these gaps should be silently recast as a
passing biological validation.
