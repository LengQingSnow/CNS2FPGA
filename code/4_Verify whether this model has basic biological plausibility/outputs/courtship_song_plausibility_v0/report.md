# Courtship-song basic biological-plausibility audit

## Verdict

**BASIC PLAUSIBILITY CHECKS PASSED** — 16 passed, 0 failed, 1 warnings.

The network is executable and its populations respond differently to IPI, but this audit does not support a claim that it currently reproduces the known courtship-song transformation. The result is intentionally conservative: firing rates from a simple connectome-constrained LIF model are treated as qualitative, not as direct calcium or behavioural units.

## Checks

| Category | Check | Status | Observed | Expected |
| --- | --- | --- | --- | --- |
| structure | `auditory_input_present` | **PASS** | 93 JO-A/JO-B anchors | >0 auditory inputs |
| structure | `aPN1_present` | **PASS** | 15 labeled aPN1 neurons | >0 explicit aPN1 neurons |
| structure | `vPN1_present` | **PASS** | 11 labeled vPN1 neurons | >0 explicit vPN1 neurons |
| structure | `pC1_present` | **PASS** | 112 pC1 neurons | >0 pC1 neurons |
| structure | `selected_outputs_present` | **PASS** | 4 pIP10/pMP2 neurons | >0 selected outputs |
| sign | `signed_neuron_coverage` | **PASS** | 97.977% | >=85.0% |
| sign | `acetylcholine_sign` | **PASS** | 100.0% mapped to +1 (n=3812) | >=99% mapped to +1 |
| sign | `gaba_sign` | **PASS** | 100.0% mapped to -1 (n=1727) | >=99% mapped to -1 |
| sign | `glutamate_sign` | **PASS** | 100.0% mapped to -1 (n=613) | >=99% mapped to -1 |
| dynamics | `pC1_ipi_discrimination` | **PASS** | normalized range=28.0% (2.857 Hz) | >=20% normalized modulation |
| dynamics | `pC1_short_ipi_attenuation` | **PASS** | 36 ms=10.214 Hz; 16 ms=7.357 Hz | 36-ms response > 16-ms response |
| dynamics | `pC1_three_point_bandpass` | **PASS** | 16/36/56 ms=7.357/10.214/8.071 Hz | 36 ms exceeds both 16 and 56 ms |
| dynamics | `output_proxy_conspecific_peak` | **WARN** | 16/36/56 ms=20.000/17.000/15.000 Hz | pIP10+pMP2 proxy at 36 ms exceeds both 16 and 56 ms |
| dynamics | `vPN1_short_ipi_attenuation` | **PASS** | 36 ms=15.636 Hz; 16 ms=4.364 Hz | 36-ms response > 16-ms response |
| ablation | `pC1_output_influence` | **PASS** | 88.24% pIP10+pMP2 rate drop | >=20% |
| ablation | `pC1_specificity_vs_random` | **PASS** | pC1=88.24%; random 95th percentile=37.94% | pC1 drop > matched-random 95th percentile |
| ablation | `auditory_input_necessity` | **PASS** | 100.00% pIP10+pMP2 rate drop | >=80% |

## IPI response

| IPI (ms) | aPN1 (Hz) | vPN1 (Hz) | pC1 (Hz) | pIP10 (Hz) | pMP2 (Hz) |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 16 | 4.000 | 4.364 | 7.357 | 32.000 | 8.000 |
| 36 | 6.933 | 15.636 | 10.214 | 26.000 | 8.000 |
| 56 | 6.400 | 9.818 | 8.071 | 16.000 | 14.000 |

The experimental constraints used here are: behaviour peaks near 35 ms; vPN1 attenuates IPIs below 25 ms; pC1 has a 35–65 ms high-response band and is attenuated at short and very long IPIs. With only 16/36/56-ms model conditions, the comparison is an inequality/trend test, not a numeric correlation. Raw per-fly experimental values were not distributed with the local article, so no values were guessed or digitized.

## In-silico ablation at 36 ms

| Ablation | Neurons | Output proxy (Hz) | Drop from intact |
| --- | ---: | ---: | ---: |
| pC1 | 112 | 2.000 | 88.24% |
| auditory_input | 93 | 0.000 | 100.00% |

The output proxy is the combined per-neuron mean firing rate of pIP10 and pMP2. It is not the chaining behavioural index. The pC1 test therefore asks whether this implementation gives pC1 a specific causal influence on the selected downstream readout; it does not directly reproduce the behavioural ablation experiment.

## Neurotransmitter/sign audit

| Consensus transmitter | Neurons | Sign +1 | Sign -1 | Sign 0 |
| --- | ---: | ---: | ---: | ---: |
| acetylcholine | 3,812 | 3,812 | 0 | 0 |
| gaba | 1,727 | 0 | 1,727 | 0 |
| glutamate | 613 | 0 | 613 | 0 |
| unclear | 86 | 0 | 0 | 86 |
| dopamine | 19 | 0 | 0 | 19 |
| octopamine | 14 | 0 | 0 | 14 |
| serotonin | 6 | 0 | 0 | 6 |
| histamine | 2 | 0 | 0 | 2 |

The 2024 whole-brain LIF model treats GABA and glutamate as inhibitory and acetylcholine as excitatory. This audit reports any disagreement instead of silently changing the frozen step-2 IR.

## Main limitations and next correction

1. Expand the IPI sweep to at least 15, 25, 35, 45, 55, 65, 75, 85 and 95 ms with an equal number of pulses per condition. The current fixed-duration stimulus confounds IPI with pulse count.
2. Do not treat pIP10+pMP2 firing as the published chaining index. Their combined response does not peak at 36 ms, so either identify a connectome-supported chaining readout or state that these are downstream courtship-output proxies only.
3. Obtain raw experimental values or perform a documented figure-digitization step before reporting Pearson correlation. The present audit intentionally tests only published qualitative inequalities.
4. The aPN1/vPN1 alias mapping and the acetylcholine/GABA/glutamate sign policy are now resolved and provenance-tracked; keep both frozen in later fixed-point and RTL stages.

Runtime: 1.838 seconds.
