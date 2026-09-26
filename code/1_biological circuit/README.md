# Courtship-song circuit extractor

This directory contains the first CNS2FPGA data-stage deliverable: a reproducible
definition and extractor for a MaleCNS-v1.0 courtship-song sensorimotor subgraph.

## Circuit V0 definition

| Role | MaleCNS selector | Purpose |
| --- | --- | --- |
| Input | `JO-A*`, `JO-B*` | Johnston's organ auditory sensory populations |
| Relay | `*vPN1*`, `pC1*` | auditory projection / courtship integration anchors |
| Output | `pIP10`, `pMP2` | male-specific descending command neurons |

The extractor does **not** assume that every named anchor is directly connected.
It retains only annotated neurons lying on a directed path from an input selector
to an output selector within the configured hop budget and synapse-weight threshold.

## Layout

- `configs/` – frozen circuit and FPGA-estimation parameters.
- `cns2fpga_circuit/` – data loading, graph traversal, and reporting modules.
- `extract_circuit.py` – command-line entry point.
- `outputs/` – generated CSV and Markdown/JSON reports; ignored by Git.

## Run

From this directory, use a Python environment with `pandas` and `pyarrow`:

```powershell
python extract_circuit.py --config configs/courtship_song_v0.json
```

The source data are intentionally referenced from `../../support`; they are never
copied into the code tree.  The script streams the 1.05 GB connectivity table, so
it can run on a normal workstation without materialising the 151M-row graph.

## Interpretation

`report.md` separates graph facts (neurons, nonzero edges, aggregate synapses,
fan-in/out) from an architecture assumption (the BRAM36 estimate).  The latter is
an early capacity estimate, not a post-synthesis utilization claim.
