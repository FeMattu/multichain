# Topology model

A topology is a **map**: locations and the links between them. It says nothing
about which MultiChain node runs where — that is the experiment descriptor's
`nodes[].location`, and several nodes may share a location.

That separation is what lets one map serve several experiments, and one
experiment move between maps by changing one line.

## Locations

```yaml
nodes:
  - id: milano-c              # referenced by an experiment's nodes[].location
    label: HUB_IT_Milano      # preserved from the historical .gml
    kind: hub                 # hub = backbone PoP (1 Gbit); leaf = access site
    scope: continental        # regional | national | continental | intercontinental
    region: lombardy
    country: italy
    continent: europe
    lat: 45.4642
    lon: 9.1900
    legacy_gml_id: 0          # the id this site had in the archived .gml
```

`legacy_gml_id` is load-bearing, not decoration: the archived `topology_edges`
and `topology_latency` tables key on those ids, and preserving them is what
lets an old and a new edge table be compared without translation.

`lat`/`lon` are required for any link that does not name a profile — that is
what the physical delay model consumes.

## Links

```yaml
links:
  - source: milano-c
    target: frankfurt
    kind: backbone            # backbone | access — selects the overhead term
    profile: continental      # optional; omit to derive from the coordinates
    profile_overrides:        # optional; merges on top, key by key
      loss: {percent: 0.5}
    enabled: true             # false keeps it declared but never builds it
```

`enabled: false` is a **permanent partition that stays visible**. The link is
still in the map, still in the exported edge table, still comparable with the
same link in a healthy run — it is simply never created. Use
`profile: partitioned` instead when you want the partition liftable at run
time.

## What the model supports

| requirement | how |
|---|---|
| regional / national / continental / intercontinental | `scope` on every location, plus one topology per level |
| per-link parameters | `profile` or `profile_overrides` on each link |
| asymmetric links | a profile with `direction: asymmetric` |
| partially connected graphs | any link set; `topology validate --allow-partitions` |
| partitions | `profile: partitioned`, or `enabled: false` |
| offline peers | a node with `expected_state: absent` — declared, never started |
| degraded connectivity | `profile: degraded` on that node's access link |

## The shipped topologies

```
configs/topologies/
├── regional.yaml            20 locations,  7 hubs, 34 links
├── national.yaml            20 locations,  7 hubs, 34 links
├── continental.yaml         20 locations,  7 hubs, 34 links
├── intercontinental.yaml    20 locations,  7 hubs, 34 links
├── smoke-3n.yaml             3 locations,  1 hub,   2 links
└── legacy-*.yaml            the five historical 10-node maps
```

The four levels share a shape: seven hubs in a full mesh, thirteen access
sites each attached to its nearest hub. Only the geography differs, which is
what makes them an axis.

| topology | worst RTT | worst pair |
|---|---:|---|
| `regional` | 10.3 ms | la-spezia — rimini |
| `national` | 23.7 ms | venezia — reggio-calabria |
| `continental` | 55.7 ms | kobenhavn — barcelona |
| `intercontinental` | 363.0 ms | sydney — los-angeles |

Each 20-node level **contains its 10-node ancestor**: the historical sites keep
their exact coordinates and GML ids, and a golden test asserts it.

The intercontinental level is deliberately wider than the historical one
(112 ms). That level stopped at the North Atlantic, and the interesting regime
— where the sortition band `Δmax = δ·T` stops dominating the network variance
— only opens past the Pacific. The historical suite reached the same
conclusion and added `intercontinental-global` (407 ms) for it.

## Placing nodes on a map

```yaml
nodes:
  - id: m1
    role: miner
    organization: cluster-1
    location: milano-c        # must exist in the topology
    geography: {region: lombardy, country: italy, continent: europe, scope: continental}
    reconcile_rate: 0.95
```

`geography` is copied into every metric row. When omitted it is inherited from
the location, so it is normally there for documentation rather than for
override.

A node placed at an unknown location is a configuration error at load time,
and the message lists the locations the topology does offer.

## Validating and exporting

```bash
python3 -m experiments.cli topology validate \
    --topology experiments/configs/topologies/intercontinental.yaml --matrix

python3 -m experiments.cli topology generate \
    --topology experiments/configs/topologies/continental.yaml \
    --format gml --output experiments/topology/generated/continental.gml
```

`validate` checks for duplicate links, isolated locations, negative delays,
out-of-range loss and connectivity, then prints the RTT matrix over the
minimum-delay paths. Three export formats: `gml` (for CORE and for the
analysis pipeline's edge tables), `json` (the realised description) and `csv`
(one row per direction).

`topology/generated/` is not versioned — everything in it is reproducible from
the YAML.

## Adding a topology

1. Copy the nearest existing file and edit the locations and links.
2. `topology validate --matrix`, and read the worst RTT: it is the number the
   whole geography axis is indexed on.
3. Reference it from a descriptor, or make one with
   `scripts/create_experiment.sh --name x --from regional --topology <path>`.

Keep the same node ids across topologies. The comparison between levels is
per-node, and renaming `m1` breaks it.
