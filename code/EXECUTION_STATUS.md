# CNS2FPGA execution status — 2026-09-28

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
| Paper | Full manuscript, seven figures, five tables, 17 data snapshots and SHA-256 manifest | Updated with paired old/new bitstream latency comparison; biological validation remains open |
| 14 | JTAG runtime image format and reconfiguration tests | Completed within recorded trials |
| 15 | One Ethernet bitstream accepting visual then courtship images; courtship 8-step trial | COMMIT/STATUS and 2,475 ordered events passed at 100-Mbps negotiated link |

The main local results are [courtship experiment](10_Complete%20Courtship-Song%20Circuit%20Experiment/outputs/courtship_song_v1/report.md),
[robustness](11_Courtship-Song%20Robustness/outputs/courtship_song_robustness_v2/report.md),
[visual board verification](12_Visual-to-Steering%20Circuit/outputs/visual_left_board_v0/report.md),
[baselines](13_Baselines%20and%20Ablations/README.md), and
[full paper](Paper/manuscript_full_v2.md), and
[Ethernet deployment evidence](15_Ethernet_Runtime_Deployment/reports/deployment_evidence_v1.json).

Remaining scientific work: independently map experimental ROI/driver lines to
MaleCNS cells; constrain visual and auditory input encoding, neuronal dynamics
and observation readouts with measured data; then use held-out conditions to
test biological predictions. If a publication asserts energy efficiency, add
board power measurements. None of these gaps should be silently recast as a
passing biological validation.
