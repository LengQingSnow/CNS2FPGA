# Step 13 — baselines and ablations

`run_baselines.py` compares the automatically extracted 226-neuron MaleCNS
visual graph with a deliberately hand-written, four-rule type-level schematic:
LC10a→AOTU019, LC10a→AOTU025, AOTU019→DNa02 and AOTU025→DNa02. Every selected
type pair is complete bipartite and gets the median aggregate synapse count of
the corresponding real pair. This is a transparent **simplification baseline**,
not a fair estimate of human mapping time or a second biological ground truth.

The manual graph keeps 226 neuron identities but has 888 edges and 59,612
synthetic synapses, versus 1,730 edges and 33,748 synapses in the actual graph.
Only 321 directed pairs overlap; edge Jaccard is 0.1397. For bilateral 40-ms
pulses both graphs yield zero DNa02 spikes, an uninformative apparent tie.
For left-only input, the real graph yields five DNa02_L spikes and the manual
graph zero; right-only input mirrors this. The key output, rather than total
network F1 (about 0.987), exposes the failure of the simplified wiring.

Four fixed-point widths were evaluated on both the original pulse cases and
additional sustained-drive cases. On this visual benchmark all four had exact
event agreement with float and zero saturation; that is a property of these
specific stimuli, not an endorsement of the narrowest format. The independent
courtship-song quantization envelope rejects `boundary_wf21` because its
maximum key-response error across nine IPI conditions is 24.53%; `safe_wf24`,
`compact_wf23` and `boundary_wf22` had zero error in that envelope.

Outputs in `outputs/baseline_v0/`: `manual_vs_automatic.csv`,
`width_ablation.csv`, structural comparison, the generated manual graph, source
hashes and `lateralized_baseline.png`.

```powershell
$py = 'C:\Users\20474\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
& $py 'code\13_Baselines and Ablations\run_baselines.py'
& $py 'code\13_Baselines and Ablations\make_figures.py'
```
