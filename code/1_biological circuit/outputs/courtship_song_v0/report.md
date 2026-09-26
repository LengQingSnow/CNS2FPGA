# courtship_song_v0 extraction report

## Frozen V0 anchors

| Role | Matched neurons |
| --- | ---: |
| input anchors | 138 |
| relay anchors | 158 |
| output anchors | 4 |
| retained input anchors | 93 |
| retained relay anchors | 112 |
| retained output anchors | 4 |
| forward-reachable nodes | 165,677 |
| backward-reachable nodes | 162,668 |
| path-retained nodes | 6,279 |

## Extracted directed subgraph

| Metric | Value |
| --- | ---: |
| neurons | 6,279 |
| nonzero edges | 350,185 |
| aggregate synapses | 7,029,800 |
| max fan out edges | 843 |
| max fan in edges | 545 |
| max fan out synapses | 19,787 |
| max fan in synapses | 24,350 |

## BRAM36 storage estimate

Assumes 64-bit virtual-neuron records, 64-bit adjacency records, and a 32-bit CSR offset table.
This is an architecture-planning estimate, not post-synthesis utilization.

| Storage item | Bits |
| --- | ---: |
| neuron state + parameters | 401,856 |
| CSR offsets | 200,960 |
| adjacency records | 22,411,840 |
| total aligned | 23,014,656 |
| BRAM36 equivalent | 625 |
