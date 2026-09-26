# CNS2FPGA Circuit Extractor

This is project step 2: a configurable tool that turns the raw MaleCNS v1.0
annotation, neurotransmitter and connectivity tables into a directed, annotated
subcircuit plus a hardware-friendly intermediate representation (IR).

## What it extracts

The config supplies regex selectors for input and output neuron groups, a maximum
directed hop count and a minimum aggregate synapse count.  The extractor then:

1. resolves selectors against the official neuron annotation table;
2. performs forward and reverse streaming graph searches;
3. retains annotated neurons satisfying `input_distance + output_distance <= max_hops`;
4. exports an indexed neuron table, sorted synapse table, CSR offset table and I/O maps;
5. records graph statistics and a BRAM36 storage estimate.

The current `courtship_song_v0.json` is a **candidate** courtship-song benchmark:
`JO-A/JO-B` auditory input to `pIP10/pMP2` descending outputs. Literature names
are resolved through the official MaleCNS `synonyms` field: aPN1 maps to
`SAD051_a/b` and `CB1078/CB1542`, while vPN1 maps to the male-specific
`AVLP761m/762m/763m` types. Named relays are reported without forcing an edge.

## Directory layout

- `configs/` — named, versioned extraction definitions.
- `src/cns2fpga_extractor/` — reusable extraction and IR-export code.
- `run_extractor.py` — command-line entry point.
- `outputs/<config-name>/` — generated subgraphs; not source code.

## Run

Install the two Python dependencies listed in `requirements.txt`, then run from
this directory:

```powershell
python run_extractor.py --config configs/courtship_song_v0.json
```

The raw source data remain in `../../../support`. The 1.05 GB connectivity table
is processed batch-by-batch and is never loaded into a pandas DataFrame.

## Output IR

| File | Purpose |
| --- | --- |
| `neuron_table.csv` | Stable `neuron_index`, source body ID, type, transmitter and anchor flags. |
| `synapse_table.csv` | Sorted `(pre_index, post_index, synapse_count, nt_model_sign)` records. |
| `offset_table.csv` | CSR start/count for each presynaptic virtual neuron. |
| `input_mapping.csv`, `relay_mapping.csv`, `output_mapping.csv` | Testbench/Golden-Model biological anchor maps. |
| `report.md`, `metadata.json` | Reproducibility record, graph size, fan-in/out and BRAM estimate. |

`nt_model_sign` follows the whole-brain LIF convention of Shiu et al. (Nature,
2024): acetylcholine maps to `+1`, GABA and glutamate to `-1`; modulatory and
unclear transmitters remain `0` pending a receptor-level policy.
