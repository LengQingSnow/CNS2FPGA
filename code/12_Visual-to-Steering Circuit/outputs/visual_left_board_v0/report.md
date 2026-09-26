# Visual-left KU115 physical verification

**PASS** — MaleCNS visual-to-steering candidate graph compiled and executed on
the AXKU115 at 200 MHz with left LC10a external input. This is an execution
fidelity check against a defined LIF model, not a measurement of fly steering.

## Frozen graph and image

- Graph: 226 neurons, 1,730 directed edges, 33,748 aggregate synapses.
- External input: 109 left LC10a cells; the graph retains both DNa02 cells.
- Format: `safe_wf24`; generic compiler round-trip 8/8 checks PASS.
- Bitstream SHA-256: `aa11a5965beaef316c6a388bba3075294a5c4efe02616cdf2ed073d9af0cc572`.
- Trial stimulus SHA-256: `d4902419f18b2c02f825e3de12a6181ebed2c15381b25a6708e2c9278aa7acf5`.

## Placement and execution

| Metric | Result |
| --- | ---: |
| Clock | 200 MHz |
| Setup WNS | +0.191 ns |
| Hold WHS | +0.028 ns |
| Unrouted / partial nets | 0 / 0 |
| DRC errors | 0 |
| LUT / FF | 3,008 / 3,602 |
| BRAM36 / BRAM18 / DSP | 88 / 9 / 4 |
| 250-ms trial max timestep | 4,439 cycles = 22.195 µs |
| Deadline | 200,000 cycles = 1 ms; 0 misses |
| Individual ordered spike events | 560 CPU = 560 FPGA; exact order |
| Per-timestep total spike counts | 250/250 exact |
| DNa02_L / DNa02_R | 5 / 0, CPU = FPGA |
| State/accumulator saturation and event overflow | 0 |

The 88 physical BRAM36 and 9 BRAM18 include trial stimulus, summaries, event
capture, neuron state and implementation packing; they must not be compared
directly to the compiled image's nine-BRAM36 independent-file lower bound.
The board remains programmed with this visual-left bitstream after the test;
the original courtship bitstream remains on disk for restoration.

Evidence: `trial/metadata.json`, `trial/expected_events.csv`,
`capture/registers.csv`, raw summary/event words, parsed CSVs,
`verification.json`, and the route/timing/resource reports in
`../../reports/visual_left_jtag_200mhz/`.
