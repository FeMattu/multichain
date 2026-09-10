# The Shadow suite's declarative descriptors

The seven simulation descriptors of the archived campaign, plus the JSON
Schema they validated against. Kept as a record of exactly how those runs were
configured — the node placements, the seeds, the scaling factors — because the
archived results cannot be interpreted without them.

They are **not runnable**: they reference Shadow's own settings
(`shadow.stop_time`, `time_granularity`, `parallelism`) and address the
network by `network_node_id` in a `.gml`. Their successor is
`experiments/configs/experiments/*.yaml`, which addresses the network by
location id and declares a schedule in wall-clock seconds.

The mapping between the two:

| Shadow descriptor | new descriptor |
|---|---|
| `name` | `name` |
| `seed` | `seed` |
| `blockchain_params_file` | `chain_params` |
| `topology_file` | `topology` (YAML, not GML) |
| `shadow.stop_time` | `schedule.duration_s` |
| `shadow.time_granularity`, `shadow.parallelism` | — (simulator settings; no equivalent) |
| `scaling.factor`, `scaling.ca_count` | the explicit `nodes` list |
| `nodes.miners[].network_node_id` | `nodes[].location` |
| `nodes.miners[].location` (documentary) | `nodes[].geography` |

All seven used 5 miners, 10 generated companies, 2 CAs, 1 admin and seed 42.
The new default is 7 / 10 / 3 on twenty locations; see
`experiments/configs/node-roles.yaml`.
