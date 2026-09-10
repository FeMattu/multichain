# Topologies

A topology is a **map**: locations and the links between them. It says nothing
about which MultiChain node runs where — that is the experiment descriptor's
`nodes[].location`. Several nodes may share a location, which is how a
twenty-node network can be laid over a ten-location map.

## Files

```
configs/topologies/
├── regional.yaml              20 locations,  7 hubs — Tuscany / Liguria / Emilia-Romagna
├── national.yaml              20 locations,  7 hubs — Italy, islands included
├── continental.yaml           20 locations,  7 hubs — Europe, Lisbon to Bucharest
├── intercontinental.yaml      20 locations,  7 hubs — five continents
├── smoke-3n.yaml               3 locations,  1 hub  — the integration fixture
└── legacy-*.yaml              the five historical 10-node maps, migrated verbatim
```

The four `legacy-*-10n.yaml` files and `legacy-global-10n.yaml` are the Shadow
suite's topologies. They are not deprecated: they are the only way to re-run a
configuration comparable with the archived campaign, and
`tests/golden/test_legacy_topologies.py` asserts that each of them still
**regenerates its historical `.gml` byte for byte**.

## Where a link's impairment comes from

Two sources, never both silently:

1. **A named profile** — `links[].profile: intercontinental` resolves against
   `configs/network-profiles/`. Use it when the number is a decision.
2. **The physical model** — when the link names no profile, its delay is
   derived from the two endpoints' coordinates:

   ```
   one_way_ms = propagation_ms_per_km · D_km · routing_factor + overhead
   ```

   with `D_km` the great-circle distance. This is the model the Shadow suite
   used, kept identical on purpose: it is what makes a regional run and an
   intercontinental run comparable, and changing it would silently invalidate
   every historical comparison. See [../docs/network-model.md](../docs/network-model.md).

Whichever fired is recorded per link in `runtime/topology-realized.json`, as
either the profile name or `derived:latency-model`.

`profile_overrides` merges on top of either source, key by key, and turning a
symmetric profile asymmetric is done by giving it a `forward`/`reverse` pair.

## Regenerating and checking

```bash
# validate, print the RTT matrix
python3 -m experiments.cli topology validate \
    --topology experiments/configs/topologies/intercontinental.yaml --matrix

# export the GML (for CORE, and for the analysis pipeline's edge tables)
python3 -m experiments.cli topology generate \
    --topology experiments/configs/topologies/continental.yaml \
    --format gml --output experiments/topology/generated/continental.gml
```

`generated/` is not versioned: everything in it is reproducible from the YAML.

## Worst end-to-end RTT

Measured by `topology validate --matrix`, minimum-delay path, both directions.

| topology | locations | links | worst RTT | worst pair |
|---|---:|---:|---:|---|
| `regional` | 20 | 34 | 10.3 ms | la-spezia — rimini |
| `national` | 20 | 34 | 23.7 ms | venezia — reggio-calabria |
| `continental` | 20 | 34 | 55.7 ms | kobenhavn — barcelona |
| `intercontinental` | 20 | 34 | 363.0 ms | sydney — los-angeles |
| `legacy-regional-10n` | 10 | 10 | 10.0 ms | la-spezia — parma |
| `legacy-national-10n` | 10 | 10 | 22.0 ms | venezia — palermo |
| `legacy-continental-10n` | 10 | 10 | 44.7 ms | warszawa — lisboa |
| `legacy-intercontinental-10n` | 10 | 10 | 112.0 ms | warszawa — toronto |
| `legacy-global-10n` | 10 | 15 | 407.2 ms | tokyo — johannesburg |

The 20-node levels track the historical ones closely at the first three
scopes; the intercontinental one is deliberately wider, because the historical
level stopped at the North Atlantic and the interesting regime — where the
sortition band `Δmax = δ·T` stops dominating the network variance — only opens
past the Pacific. That is the same reason the historical suite added
`intercontinental-global`.
