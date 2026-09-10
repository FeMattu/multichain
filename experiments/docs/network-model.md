# Network model

How a delay value gets from a configuration file onto a packet, and what each
number is allowed to claim.

## Two sources, never both silently

A link's impairment comes from exactly one of two places, and which one is
recorded per link in `runtime/topology-realized.json`:

1. **A named profile** — `links[].profile: intercontinental`, resolved against
   `configs/network-profiles/`. Use it when the number is a decision.
2. **The physical model** — when the link names no profile, the delay is
   derived from the endpoints' coordinates. The record then reads
   `derived:latency-model`.

`profile_overrides` merges on top of either, key by key.

## The physical model

```
one_way_ms = propagation_ms_per_km · D_km · routing_factor + overhead
RTT        = 2 · one_way_ms
```

| term | value | why |
|---|---|---|
| `propagation_ms_per_km` | 0.005 | fibre propagation, v ≈ 2·10⁵ km/s |
| `routing_factor` | 1.4 | the physical path is longer than the great circle |
| `overhead` | 0.5 ms backbone, 1.0 ms access | switching and aggregation, not distance-proportional |

`D_km` is the great-circle distance from the two locations' coordinates.

This is **the same model the Shadow campaign used**, unchanged on purpose: it
is what makes a regional run and an intercontinental run comparable, and
changing it would silently invalidate every comparison with the archive.
`tests/unit/test_topology.py` pins it to its published check points.

### Validation against real measurements

| route | D | model RTT | measured RTT |
|---|---:|---:|---:|
| Bologna–Geneva | 840 km | 12.8 ms | ~9.5 ms |
| Milan–Rome | 477 km | 7.7 ms | ~9 ms |
| Milan–Madrid | 1188 km | 17.6 ms | ~20 ms |
| Milan–New York | 6464 km | 91.5 ms | ~90 ms |

Slightly pessimistic on short hops, accurate on the long ones — which are the
ones that matter for the geography axis.

### Packet loss

```
access:   0.04 %                       constant
backbone: 0.02 % + 2·10⁻⁵ % per km     grows with distance
```

Same constants as the archived topologies.

## Profiles

Seven ship with the harness. Each declares a `source`, and that field is not
decoration: a delay value that cannot be traced back to a measurement or to a
stated assumption is not evidence, and the harness reports it in every
manifest.

| profile | one-way delay | jitter | loss | rate | what it is |
|---|---:|---:|---:|---:|---|
| `lan` | 0.1 ms | 0.02 ms | 0.04 % | 1 Gbit | one switch hop |
| `regional` | 2.1 ms | 0.3 ms | 0.025 % | 1 Gbit | worst hop of the regional level |
| `national` | 5.1 ms | 0.8 ms | 0.033 % | 1 Gbit | Milan–Naples |
| `continental` | 10.4 ms | 2.0 ms | 0.048 % | 1 Gbit | Frankfurt–Madrid |
| `intercontinental` | 45.8 ms | 8.0 ms | 0.15 % | 1 Gbit | Milan–New York |
| `degraded` | 120 / 160 ms | 20 / 35 ms | 0.5 / 1.0 % | 100 / 10 Mbit | **asymmetric**: a poor uplink |
| `partitioned` | — | — | 100 % | — | the link exists and drops everything |

`degraded` and `partitioned` are operating points, not measurements, and say
so in their own `source` field. Read `degraded`'s numbers as "deliberately
hostile", never as typical.

### Jitter is new

Every archived topology carries `jitter "0 us"` on every edge. That was not a
modelling choice — Shadow never implemented the field
([shadow#3601](https://github.com/shadow/shadow/issues/3601)). The values in
the profiles above are a **declared assumption**, applied for the first time
by the tc/netem backend, and every report that shows them says so.

### Asymmetry

`direction: asymmetric` gives a profile a `forward` and a `reverse` block.
Because netem shapes egress only, the two become two different qdiscs: the
forward impairment on the interface at the link's source end, the reverse on
the target end. Averaging them would be a different network, so the harness
never does.

## From a profile to the kernel

```
no bandwidth limit          root ── netem delay/jitter/loss
with a bandwidth limit      root ── tbf rate/burst/limit ── netem delay/jitter/loss
```

The order matters. netem above tbf would delay the *pre-shaping* stream, and
the effective latency would then drift with the queue depth. tbf first, netem
below, so the delay is added to packets that have already been paced.

Three details that are easy to get wrong, all covered by
`tests/unit/test_netem.py`:

* **tbf burst.** A burst below `rate/HZ` makes the bucket refill slower than
  the configured rate, and the link silently runs under it. The harness uses a
  tenth of a second of traffic, floored at one MTU.
* **`distribution` needs a jitter term.** netem rejects it otherwise, and
  `uniform` — its default — has no table file, so it is expressed by omitting
  the keyword.
* **No exponent notation.** `tc` rejects `1e-05ms`. Every magnitude is
  rendered fixed-point.

A partition is expressed as 100 % loss, not as a deleted interface. The link
keeps its shape, so a partitioned run stays comparable with a healthy one link
by link, and the partition can be lifted mid-run without rebuilding anything.

## The two planes

```
EMULATED PLANE                        MANAGEMENT PLANE
routers, /30 per link, netem          one bridge, no impairment
P2P and node→node RPC                 the harness's collectors only
11.0.0.0/24, identity /32 on lo       172.30.0.0/24
```

Node-to-node RPC travels the emulated plane because it is part of the
experiment. The harness's own polling does not, because twenty nodes sampled
every ten seconds would add traffic to exactly the paths under measurement.

Routing is static, computed from the topology's **minimum-delay** paths — not
hop count — so the path a packet takes is the path the topology says it takes.

## Changing conditions during a run

```bash
# degrade one link
sudo -E experiments/scripts/apply_network_profile.sh --run-id <id> \
    --profile experiments/configs/network-profiles/degraded.yaml \
    --link milano-c--frankfurt

# partition it
sudo -E experiments/scripts/apply_network_profile.sh --run-id <id> \
    --profile experiments/configs/network-profiles/partitioned.yaml \
    --link milano-c--frankfurt

# put everything back to what the topology declares
sudo -E experiments/scripts/apply_network_profile.sh --run-id <id> --restore
```

Every change is appended to `<run>/runtime/netem-events.jsonl` with both
clocks, so the analysis can align a change in behaviour with the change in
conditions that caused it.

## What the numbers do not claim

The values in `metrics/netem_conditions.csv` are what was **configured**, not
what was measured on the wire. Measuring the real delay of every link would
need a probe per link whose own traffic would perturb the run, so the
catalogue declares `measured_delay_ms` **unavailable** rather than reporting a
configured value as an observation.

What *is* measured, indirectly, is block propagation:
`metrics/block_propagation.csv` records how long a block took to reach every
node that saw it. Its resolution is the sampling interval, so it is an **upper
bound**, and it is labelled as one.
