# courtship_song_lif_v0 report

This is a computational LIF reference model, not a biological-behavior validation.

## Frozen execution semantics

- dt: 1.0 ms
- duration: 250.0 ms
- membrane time constant: 20.0 ms
- threshold/reset: 1.0 / 0.0
- refractory period: 2.0 ms
- weight mode: `raw_linear`
- propagation backend: `scipy_csr`
- recurrent gain: 0.015
- noise standard deviation: 0.0
- random seed: 20260918

## Observed populations

| Group | Neurons |
| --- | ---: |
| auditory_input | 93 |
| aPN1 | 15 |
| vPN1 | 11 |
| pC1 | 112 |
| pIP10 | 2 |
| pMP2 | 2 |

## Condition summary

| condition | total_network_spikes | auditory_input_mean_rate_hz | aPN1_mean_rate_hz | vPN1_mean_rate_hz | pC1_mean_rate_hz | pIP10_mean_rate_hz | pMP2_mean_rate_hz |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| pulse_ipi_16ms | 13,346 | 52.000 | 4.000 | 4.364 | 7.357 | 32.000 | 8.000 |
| pulse_ipi_36ms | 12,621 | 24.000 | 6.933 | 15.636 | 10.214 | 26.000 | 8.000 |
| pulse_ipi_56ms | 9,491 | 16.000 | 6.400 | 9.818 | 8.071 | 16.000 | 14.000 |

Runtime: 0.960 seconds.
