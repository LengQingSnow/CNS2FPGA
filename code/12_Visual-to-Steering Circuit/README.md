# Step 12 — visual-to-steering transfer circuit

This is a second MaleCNS v1.0 subcircuit, chosen from the literature-motivated
LC10a → AOTU019/AOTU025 → DNa02 candidate path. It is an engineering transfer
test of the same extractor, compiler, fixed-point semantics and RTL core; it is
not a validated model of visual pursuit or a calibrated retinal stimulus.

## Frozen graph and input contract

The Step-2 extractor, run with `configs/visual_to_steering_v0.json`, retains
226 neurons, 1,730 directed nonzero edges and 33,748 aggregate synapses at a
five-synapse edge threshold. The retained groups are 220 LC10a input anchors,
two AOTU019, two AOTU025 and two DNa02. The generic Step-6 compiler produced
`outputs/visual_hw_ir_v0` in `safe_wf24`; all eight round-trip checks pass.

| Retained directed type pair | Edges | Aggregate synapses |
| --- | ---: | ---: |
| LC10a → LC10a | 1,404 | 11,472 |
| LC10a → AOTU019 | 179 | 14,152 |
| LC10a → AOTU025 | 138 | 6,988 |
| AOTU025 → AOTU019 | 3 | 95 |
| AOTU019 → AOTU019 | 2 | 54 |
| AOTU019 → DNa02 | 2 | 586 |
| AOTU025 → DNa02 | 2 | 401 |

`derive_left_input_ir.py` does **not** alter the graph. It changes only the
external-input flags to the 109 left LC10a cells and produces a separate,
provenance-tracked image `outputs/visual_left_hw_ir_v0`. This is necessary
because the current board interface broadcasts one scalar stimulus to every
flagged input. The two DNa02 cells remain in the graph.

## Verified software and RTL results

- `run_visual_experiment.py`: three IPI conditions × bilateral/left/right
  injection; float and fixed have identical individual spike events in all nine
  cases, with no fixed-point saturation.
- For 40 ms IPI, left input gives DNa02_L=5, DNa02_R=0; right input gives
  DNa02_L=0, DNa02_R=5. Bilateral input gives zero DNa02 spikes under this
  uncalibrated sign/weight model. This is a model response, not an observed
  steering behavior.
- The original Step-8 synchronous RTL core, parameterized for the new memory
  image, matches the CPU reference on all 226 neurons over eight timesteps:
  7,232 voltage/current/refractory/spike comparisons with zero errors for both
  the bilateral and left-input images.
- The separate Step-9 200 MHz board-core RTL also passes the same 7,232
  left-input state checks with zero errors before physical implementation.

## Reproduction

Use the Python runtime already installed for this workspace. The commands
below are run from the repository root unless noted.

```powershell
$py = 'C:\Users\20474\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
& $py 'code\2_Subcircuit Automatic Extraction Tool\run_extractor.py' --config 'code\12_Visual-to-Steering Circuit\configs\visual_to_steering_v0.json' --output-dir 'code\12_Visual-to-Steering Circuit\outputs\visual_to_steering_v0'
& $py 'code\12_Visual-to-Steering Circuit\run_visual_experiment.py'
& $py 'code\12_Visual-to-Steering Circuit\derive_left_input_ir.py'
& $py 'code\6_Connectome Compiler\compile_hardware_ir.py' --config 'code\12_Visual-to-Steering Circuit\configs\visual_left_hw_ir_v0.json' --output-dir 'code\12_Visual-to-Steering Circuit\outputs\visual_left_hw_ir_v0'
& $py 'code\8_RTL Bit-Exact Co-Simulation\generate_reference.py' --config 'code\12_Visual-to-Steering Circuit\configs\visual_left_rtl_8step_v0.json' --output-dir 'code\12_Visual-to-Steering Circuit\outputs\visual_left_rtl_reference_v0'
```

The extract/compile/reference commands refuse or overwrite outputs according
to their own contracts; use a new versioned output directory for a rerun, and
do not overwrite these recorded results. To reproduce just the simulation,
run the following in this Step-12 directory:

```powershell
vlib work_visual
vlog -sv -work work_visual '..\8_RTL Bit-Exact Co-Simulation\rtl\cns2fpga_core_sync.sv' 'sim\tb_visual_left_bit_exact.sv'
vsim -c -lib work_visual tb_visual_left_bit_exact -do 'run -all; quit -f'
```

The physical-design files under `rtl/` specialize the unchanged Step-9 board
architecture for 226/1,730 records, using the left-input image. The routed
200 MHz bitstream passed setup/hold/DRC signoff. A 250-step trial on the
programmed KU115 matched all 560 ordered CPU spike events, including five
ipsilateral DNa02 spikes; maximum latency was 4,439 cycles and all diagnostics
were zero. See [physical verification](outputs/visual_left_board_v0/report.md).

The board is left programmed with the visual bitstream. To rebuild in a normal
Windows shell, run `run_visual_left_bitstream.ps1`; the split recovery path is
`run_visual_left_bitstream.ps1 -SynthesisOnly` followed by
`resume_visual_left_impl.ps1`. Then `prepare_board_trial.py` and
`run_visual_left_board.ps1` perform a new versioned board trial. They refuse to
overwrite the existing capture.

## Scientific boundary

This selected subgraph deliberately excludes other LC10a outputs and
behavioral-state inputs. The input is a current pulse, not a visual object or
measured firing response. AOTU019's predicted inhibitory sign is carried from
the annotation/sign policy; receptor-specific physiology is not inferred.

Literature: [Collie et al., *Neuron* 2026](https://doi.org/10.1016/j.neuron.2026.01.001)
for LC10a/AOTU019/AOTU025/DNa02 visual pursuit circuits;
[MaleCNS resource](https://male-cns.janelia.org/download/) for the versioned
connectome.
