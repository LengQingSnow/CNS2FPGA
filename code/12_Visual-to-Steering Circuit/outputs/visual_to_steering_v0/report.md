# visual_to_steering_v0: subcircuit extraction

## Selector and path result

| Item | Count |
| --- | ---: |
| input anchors matched | 275 |
| relay anchors matched | 4 |
| output anchors matched | 2 |
| input anchors retained | 220 |
| relay anchors retained | 4 |
| output anchors retained | 2 |
| forward reachable neurons | 281 |
| backward reachable neurons | 226 |
| path-retained neurons | 226 |

## Directed induced subgraph

| Metric | Value |
| --- | ---: |
| neurons | 226 |
| nonzero edges | 1,730 |
| aggregate synapses | 33,748 |
| max fan out edges | 15 |
| max fan in edges | 96 |

## Storage planning estimate

- Total IR bits: 132,448
- BRAM36 equivalent: 4
- Note: Storage estimate only; excludes buffers, port replication and control logic.
