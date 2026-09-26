# Step 11 result interpretation

The 65 full-length CPU perturbation trials show that the frozen float and
`safe_wf24` fixed-point implementations agree on the measured group counts;
the three 5/10/20% input-noise trials measured on KU115 also agree with fixed
CPU at every recorded timestep and group (77,544 comparisons, zero mismatches).
This is an **implementation robustness** result. It is not evidence that the
model's circuit behavior matches an animal under injury or noise.

The plotted degradation quantity is absolute deviation from the intact model's
response-window spike count, not a task success rate. The random perturbation
series used only five fixed seeds per level, and weight/input-noise response is
not monotonic with level. Therefore no monotonic dose-response or population
confidence interval is claimed. A single deletion trial has event F1 just below
one despite zero group-count difference, illustrating that aggregate counts can
hide individual event changes.

`boundary_wf21` is rejected by the independent nine-IPI Step-5 envelope (maximum
key-response error 24.53%), despite matching at the single 35-ms reference and
in the Step-12 visual stimuli. Bit width must be selected on a diverse condition
set, not one easy operating point. The board cannot change connectivity or
weights at runtime, so the non-input perturbations here remain CPU comparisons;
recompiled perturbation bitstreams would be a distinct future experiment.

The biological plausibility qualification from Step 4 remains in force. In
particular, the experimental pC1 ROI has not been uniquely mapped to the 112
MaleCNS pC1 neurons; no behavioral performance or experimental response
correlation is assigned to these robustness curves.
