# CNS2FPGA execution status — 2026-09-26

The 14 items in `../大概流程.txt` have engineering artifacts. This status is not
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
| 14 | Result-grounded manuscript draft with references and limitations | Draft complete; not submission-ready |

The main local results are [courtship experiment](10_Complete%20Courtship-Song%20Circuit%20Experiment/outputs/courtship_song_v1/report.md),
[robustness](11_Courtship-Song%20Robustness/outputs/courtship_song_robustness_v2/report.md),
[visual board verification](12_Visual-to-Steering%20Circuit/outputs/visual_left_board_v0/report.md),
[baselines](13_Baselines%20and%20Ablations/README.md), and
[paper draft](14_Paper/manuscript_draft_v1.md).

Remaining scientific work: independently map experimental ROI/driver lines to
MaleCNS cells; constrain visual and auditory input encoding, neuronal dynamics
and observation readouts with measured data; then use held-out conditions to
test biological predictions. If a publication asserts energy efficiency, add
board power measurements. None of these gaps should be silently recast as a
passing biological validation.
