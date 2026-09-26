# courtship_song_v0: subcircuit extraction

## Selector and path result

| Item | Count |
| --- | ---: |
| input anchors matched | 138 |
| relay anchors matched | 184 |
| output anchors matched | 4 |
| input anchors retained | 93 |
| relay anchors retained | 138 |
| output anchors retained | 4 |
| forward reachable neurons | 165,677 |
| backward reachable neurons | 162,668 |
| path-retained neurons | 6,279 |

## Directed induced subgraph

| Metric | Value |
| --- | ---: |
| neurons | 6,279 |
| nonzero edges | 350,185 |
| aggregate synapses | 7,029,800 |
| max fan out edges | 843 |
| max fan in edges | 545 |

## Storage planning estimate

- Total IR bits: 23,014,656
- BRAM36 equivalent: 625
- Note: Storage estimate only; excludes buffers, port replication and control logic.
