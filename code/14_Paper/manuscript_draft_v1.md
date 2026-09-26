# CNS2FPGA: Compiling MaleCNS Connectome Subcircuits to a Time-Multiplexed FPGA Engine

Draft, 26 September 2026. Engineering manuscript; not yet submission-ready.

## Abstract

Dense connectomes now provide neuron-resolved wiring for the adult male *Drosophila* central nervous system, but a reproducible path from a biological subgraph to executable FPGA memory images remains useful. We present CNS2FPGA, a configurable circuit extractor, signed-weight fixed-point compiler, and time-multiplexed leaky integrate-and-fire engine. A courtship-song candidate circuit (6,279 neurons, 350,185 directed weighted edges) is evaluated against floating-point and fixed-point CPU references on 13 stimulus conditions. On an AXKU115 board at 200 MHz, all measured per-timestep population counts match fixed CPU and a short raster trial matches individual event order; the slowest timestep takes 199,063 of 200,000 available cycles. A second visual-to-steering candidate circuit (226 neurons, 1,730 edges) is compiled without changing the core algorithm and passes 7,232 full-state RTL comparisons over eight timesteps. Its 200 MHz KU115 implementation exactly matches 560 ordered CPU spike events in a 250-ms left-input trial and takes at most 4,439 cycles per step. In its uncalibrated model, unilateral LC10a input activates ipsilateral DNa02 whereas bilateral broadcast input does not. A hand-written type-level wiring baseline misses that output under unilateral input. Perturbation and width sweeps distinguish implementation fidelity from biological validity: hardware agreement does not establish that the LIF readout reproduces fly activity or behavior. We release versioned data transforms, protocol hashes, memory images, and executable comparisons to make this boundary auditable.

## 1. Introduction

MaleCNS v1.0 offers a brain–ventral-nerve-cord connectome with cell annotations and synaptic weights [1]. A connectome, however, specifies structural constraints rather than membrane dynamics, stimulus encoding, or behavioral readout. Our target is therefore a reproducible *connectome-constrained computation* whose FPGA execution can be compared exactly with a CPU reference. We do not claim to simulate the full fly brain.

The project asks three engineering questions: can a user select an annotated sensorimotor circuit without manual edge transcription; can the resulting memory image execute on a reusable FPGA core; and do fixed-point and physical hardware preserve the defined computation across stimuli and perturbations? A secondary scientific question is whether a simplified type-level schematic is adequate for the chosen readout. We test this with both bilateral and unilateral visual input because a bilateral-only benchmark proved uninformative.

We chose the courtship-song pathway as the larger stress test and the LC10a–AOTU019/AOTU025–DNa02 pathway as a transfer test. The latter chain is motivated by anatomical and physiological work on visual object pursuit [2], but our input current is not a reconstructed visual object. The courtship interpretation is likewise constrained by incomplete mapping between experimental pC1 imaging regions and MaleCNS subtypes, and by predicted rather than receptor-confirmed neurotransmitter signs [1,3].

## 2. Methods

### 2.1 Data and path extraction

The input is the pinned MaleCNS v1.0 annotation, neurotransmitter and aggregate-connectivity Feather files [1,4]. The extractor resolves regex selectors against annotations, streams the connectivity table, computes directed input/output reachability, and retains nodes with input-to-output path length at most the configured hop bound. An edge requires at least five aggregate synapses. Its output contains indexed neurons, directed weighted edges, CSR offsets, anchor maps, source metadata and storage estimates. The courtship and visual circuits use different configuration files but the same extraction implementation.

The visual configuration selects LC10a inputs, AOTU019/AOTU025 relays and DNa02 outputs. From 275 annotated LC10a cells, 220 survive a two-hop input-to-output path constraint. The resulting graph has 226 neurons, 1,730 edges and 33,748 aggregate synapses. A left-input image retains the identical graph but flags only 109 left LC10a cells for external current; this specialization is separately provenance-tracked.

### 2.2 Computation and fixed-point contract

The floating-point reference uses a discrete-time LIF update at 1 ms: one-timestep-delayed presynaptic spikes, exponentially decayed membrane state, additive signed synaptic current and external input, threshold/reset, and a two-step refractory period. The engineering sign policy maps predicted acetylcholine to +1 and predicted GABA/glutamate to −1; unknown/modulatory signs contribute zero. Synaptic magnitude is proportional to aggregate synapse count with recurrent gain 0.015. This gain and sign policy are computational choices, not fitted conductances.

The fixed-point implementation uses `safe_wf24`: 34-bit state with 24 fractional bits, 30-bit weights with 24 fractional bits, 32-bit decay with 30 fractional bits, and 35-bit accumulation. Rounding and saturation are specified in the CPU implementation and mirrored in RTL. A versioned compiler converts each CSR graph into `neuron_param.mem`, `synapse.mem`, `offset.mem`, `type_sign.mem`, `input_mapping.mem` and `global_config.mem`. Round-trip decoding checks the serialized fields. The visual image uses the same format and compiler as the courtship image.

### 2.3 FPGA and comparisons

The FPGA engine time-multiplexes virtual neurons through synchronous on-chip memory. A JTAG AXI-Lite trial interface supplies one 34-bit current value per model timestep and returns counters, diagnostics and event records. The courtship implementation is a 200 MHz AXKU115 bitstream. We compare CPU float versus CPU fixed to measure quantization error, CPU fixed versus RTL to measure arithmetic/state fidelity, and CPU fixed versus the programmed board to measure physical execution fidelity. These are different comparisons and must not be pooled into a single accuracy number.

The courtship experiment contains nine pulse intervals, two amplitudes, one alternating-interval condition and one short full-event raster. The robustness experiment contains 65 full-length CPU conditions: intact, four random perturbation families at three levels with five fixed seeds each, and four targeted ablations. Three scalar input-noise trials were executed on the board. In the visual circuit, three pulse intervals were tested with bilateral, left and right LC10a injection. A separate eight-step synchronous RTL test checks voltage, synaptic current, refractory state and spike state for all 226 cells at each step.

### 2.4 Baselines

The manual/synthetic baseline deliberately replaces individual connectivity with four complete-bipartite type rules: LC10a→AOTU019, LC10a→AOTU025, AOTU019→DNa02 and AOTU025→DNa02. Each rule uses the median synapse count of the corresponding real type pair. It retains the same 226 neuron identities but does not preserve the exact number of edges, synapses or degree distribution. Thus it tests consequences of a transparent simplified wiring choice, not human labor, mapping speed, or a matched-topology null. Four fixed-point formats are evaluated separately. We report individual-event F1 and the prespecified DNa02 output counts, not only total-network activity.

## 3. Results

### 3.1 Courtship hardware fidelity and capacity

All 13 stimulus conditions have exact float/fixed individual-event agreement and exact measured fixed/FPGA population counts per millisecond. The short trial additionally has exact FPGA event order. The placed-and-routed 200 MHz implementation uses 11,912 LUTs, 4,093 FFs, 589 RAMB36, three RAMB18 and four DSPs. The signed-off timing report records setup WNS +0.073 ns and hold WHS +0.030 ns. Maximum measured timestep latency is 199,063 cycles, or 995.315 µs, leaving 937 cycles before the 1 ms deadline. This is a small real-time margin, not an assertion of substantial timing headroom. No board-level power measurement was performed, so power efficiency is not reported.

### 3.2 Robustness and quantization

In 65 CPU perturbation trials, float and fixed agree on the measured response-window group counts. In three board input-noise trials, 77,544 per-timestep group-count comparisons with fixed CPU have zero mismatches, and no diagnostic fault is observed. Random deletion, neuron failure and weight perturbations were not programmed into the immutable board memory image; their robustness result is CPU-side only. The plotted degradation measure is absolute spike-count deviation from the intact model, not behavior accuracy. Five seeds per level provide descriptive spread, not a population confidence interval.

The independent nine-interval courtship width envelope has maximum key-response error 0% for `safe_wf24`, `compact_wf23` and `boundary_wf22`, but 24.53% for `boundary_wf21`. A single 35 ms condition would have missed the latter failure. Hence the conservative format is used for the reported board implementation.

### 3.3 Transfer to visual-to-steering circuit

The visual subgraph compiles to 154,528 logical memory bits: five BRAM36 by aggregate capacity lower bound, or nine BRAM36 if each file is allocated independently, before state buffers and port constraints. All eight compiler round-trip checks pass. The Step-8 RTL core, instantiated with 226 neuron and 1,730 edge records, passes 7,232 full-state/spike comparisons across eight steps with zero errors for both bilateral and left-only input images. The Step-9 board-core RTL independently passes the same 7,232 left-input checks. Across nine 250-ms CPU trials (three pulse intervals × three input sides), float and fixed individual events match exactly with no saturation.

At 40 ms pulse interval, left LC10a input generates five DNa02_L spikes and zero DNa02_R spikes; right input generates the converse. Bilateral synchronous input generates no DNa02 spikes. This directional asymmetry is a property of the selected structural graph and current-input model. It is not an estimate of steering angle, visual receptive field, or fly behavior. The current board interface provides one scalar amplitude to all flagged inputs, so a separate left-only input image was compiled for the board trial. The resulting bitstream passes 200 MHz setup/hold signoff (WNS +0.191 ns, WHS +0.028 ns), with zero unrouted nets and DRC errors. Its placed-and-routed utilization is 3,008 LUTs, 3,602 FFs, 88 RAMB36, nine RAMB18 and four DSPs. In a 250-step left-input trial, all 560 ordered individual spike events and all 250 per-step total counts match the fixed CPU oracle; DNa02_L/DNa02_R counts are 5/0. Maximum board latency is 4,439 cycles (22.195 µs) and there are no saturation, deadline-miss or event-overflow flags. This is physical execution fidelity, not behavioral validation.

### 3.4 Wiring and width baselines

The four-rule manual graph has 888 directed edges and 59,612 synthetic aggregate synapses; only 321 edges overlap the real graph, giving edge Jaccard 0.1397. At bilateral 40 ms input, both graphs have zero DNa02 spikes, apparently tying. With left-only input, the real graph generates five DNa02_L spikes but the manual graph generates none; the right condition mirrors this. Total-network event F1 remains near 0.987 because the large LC10a input population dominates, illustrating why output-specific readouts matter. On the visual benchmark's tested stimuli, all four width formats match float events with no saturation. That does not override the independent courtship rejection of `boundary_wf21`.

| Measurement | Courtship-song | Visual-to-steering |
| --- | ---: | ---: |
| MaleCNS neurons | 6,279 | 226 |
| Directed weighted edges | 350,185 | 1,730 |
| Aggregate synapses | 7,029,800 | 33,748 |
| Compiled logical memory bits | 23,518,944 | 154,528 |
| KU115 clock | 200 MHz | 200 MHz |
| LUT / FF | 11,912 / 4,093 | 3,008 / 3,602 |
| RAMB36 / RAMB18 / DSP | 589 / 3 / 4 | 88 / 9 / 4 |
| Signed-off setup / hold slack | +0.073 / +0.030 ns | +0.191 / +0.028 ns |
| Maximum measured timestep | 199,063 cycles | 4,439 cycles |

Physical BRAM use includes state and trial buffers and is affected by packing,
replication and distributed RAM mapping; it is not a direct measure of graph
bits divided by 36,864. The two maximum-latency observations come from
different recorded stimulus suites and are not a controlled scaling benchmark.

## 4. Discussion

The evidence supports a reusable extraction/serialization/execution stack and exact implementation of a *defined model*, not biological reproduction. The visual transfer test exercises a different graph size and sensory-to-descending pathway without changing the RTL neuron/synapse algorithm. Nevertheless, a model can be exactly executed and still be biologically wrong. In particular, a common current pulse to LC10a cells omits retinotopy, object motion, behavioral state, receptor effects and measured cellular dynamics [2]. The simple sign policy treats predicted glutamate as inhibitory, an assumption that can fail for particular receptors. The 226-neuron path-restricted graph also removes alternate routes that may matter in vivo.

The manual baseline is informative because it fails on an output-specific unilateral condition despite a high whole-network event F1. It is not a controlled ablation of one feature: topology, edge multiplicity and aggregate synapse count all change. A future matched-control suite should preserve degree and weight distributions, vary annotation use separately, and test held-out visual stimuli. Experimental validation additionally requires auditable driver/ROI-to-MaleCNS cell mapping and an observation model for fluorescence or behavior. Until then, the visual and courtship models remain engineering references.

## 5. Limitations and next evidence

1. The pC1 experimental ROI has no unique verified mapping to the full MaleCNS pC1 group; selected subsets can change intervention trends. No experimental correlation coefficient is claimed.
2. The visual injection is a synchronous current pulse, not photoreceptor or LC10a activity inferred from moving-object data.
3. Board perturbations are limited to scalar input noise unless connectivity is recompiled into new bitstreams.
4. The board power and thermal data are unavailable. The latency measurement excludes JTAG host-transfer time.
5. The manual graph is a deliberately unmatched schematic; it cannot quantify automatic mapping productivity.
6. The reported FPGA matches fixed CPU at the observed counters/events, while full per-neuron state equality was checked in RTL simulation, not read out from the programmed chip.

## Figure plan and available artifacts

- Fig. 1: [extraction–compiler–CPU/RTL/FPGA pipeline](figures/pipeline.png). This is a computation/provenance schematic, not a purported biological circuit reconstruction.
- Fig. 2: courtship response curves and short raster from `../10_Complete Courtship-Song Circuit Experiment/outputs/courtship_song_v1/`.
- Fig. 3: robustness curves and board-noise comparisons from `../11_Courtship-Song Robustness/outputs/courtship_song_robustness_v2/`.
- Fig. 4: lateralized real-versus-manual DNa02 comparison from `../13_Baselines and Ablations/outputs/baseline_v0/lateralized_baseline.png`.
- Table 1: graph/compiled-memory size; Table 2: float/fixed/RTL/FPGA comparison levels; Table 3: both circuits' board resources and timing. Visual board source data and checksums are in `../12_Visual-to-Steering Circuit/outputs/visual_left_board_v0/`.

## Data and code availability

All project-local source, versioned configurations, generated IR, checksums and result tables are under `E:\Workspace\CNS2FPGA\code`. MaleCNS source files are pinned under `support/`; redistribution terms should be reviewed before public release. The compiled courtship and visual `.mem` files carry protocol locks. The manuscript does not yet have a public repository DOI, external independent rerun, or power dataset.

## References

1. Berg et al. [Sexual dimorphism in the complete *Drosophila* male central nervous system connectome](https://doi.org/10.1016/j.cell.2026.08.015). *Cell* 189:5504–5526.e15, 2026.
2. Collie MF et al. [Specialized parallel pathways for adaptive control of visual object pursuit](https://doi.org/10.1016/j.neuron.2026.01.001). *Neuron*, 2026.
3. Zhou C et al. [Central neural circuitry mediating courtship song perception in male *Drosophila*](https://doi.org/10.7554/eLife.08477). *eLife* 4:e08477, 2015.
4. [MaleCNS v1.0 download and data description](https://male-cns.janelia.org/download/).
