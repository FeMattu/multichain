# Running on an emulated network

How to run a profile under CORE, what it builds, and how to look inside it when something
is wrong. The *format* of a CORE profile is [`../config/schema.md`](../config/schema.md)
§6; this is the operator's side.

## Before anything

CORE, the namespaces and netem live in the project's container. Nothing here works on the
host, and a CORE profile run there fails saying so rather than quietly running native.

```bash
./docker/mcsim preflight
```

Every line must pass. The two that fail for their own reasons:

- **`ip netns add works`** needs `--cap-add NET_ADMIN --cap-add SYS_ADMIN` *and*
  `--security-opt apparmor=unconfined`, because creating a namespace mounts something and
  Docker's default AppArmor profile denies `mount()` whatever the capabilities say.
  `mcsim` passes all three; a hand-rolled `docker run` usually does not.
- **`CORE's Python API is importable by python3`** is the quiet one. The harness imports
  `core.api.grpc` with the *system* interpreter, not with `/opt/core/venv`'s, so CORE can
  be perfectly installed and still be invisible. The image bridges the two with a `.pth`
  file; if that is missing, rebuild.

If the daemon is not answering, `core-up` starts it and waits until its gRPC API really
answers, which is later than the port opening.

## A run

```bash
# the smallest one: 4 nodes, 3 sites, ~12 minutes of chain
./docker/mcsim run python3 test/bootstrap/bootstrap_network.py \
    --config test/config/profiles/core/smoke.yaml

# a level: 20 nodes on 20 sites
./docker/mcsim run python3 test/bootstrap/bootstrap_network.py \
    --config test/config/profiles/core/continental.yaml
```

`--dry-run` validates the profile and prints the plan — ports, budgets, target height, and
the whole address map — and needs no emulator at all, so it is also how a profile is
checked in CI.

The output is the same run directory a native run produces, plus one file:

```
run-<chain>-<UTC>/
  fabric.json      the session, the addresses, every link's realised impairment
  ...              everything else exactly as in a native run
```

## What gets built

One namespace per **site** of the map, not per node. Nodes are placed at a site with
`location:` and run inside its namespace, so two nodes at one site share its addresses and
are told apart by port. A site with no node placed on it is a pure transit router.

```
            10.61.0.0/30                    10.61.1.0/30
  pisa  ------------------  firenze  ------------------  bologna
 10.60.0.2                 10.60.0.1                    10.60.0.3
 ctrl 172.30.0.2           ctrl 172.30.0.1              ctrl 172.30.0.3
 [company-0]               [miner-0]                    [admin, ca-0]
```

Each site holds one `/32` identity on `lo` — that is what `multichaind` binds to and
advertises — and one static route per other site, computed by shortest path. The harness
itself never touches the data plane: it reaches every node's RPC port over the control
network, which carries no impairment.

## Looking inside

```bash
./docker/mcsim shell

# which session is this run?
jq .session_id test/results/run-.../fabric.json

# a shell inside a site
vcmd -c /tmp/pycore.<session>/firenze -- bash

# what netem is actually on a cable
vcmd -c /tmp/pycore.<session>/pisa -- tc qdisc show dev eth0

# does the map route the way it says it does?
vcmd -c /tmp/pycore.<session>/pisa -- ping -c5 10.60.0.3
vcmd -c /tmp/pycore.<session>/pisa -- ip route

# what the harness asked for, per link
jq '.links[] | {source, target, kind, distance_km, delay: .forward.delay_ms, origin: .forward.origin}' \
   test/results/run-.../fabric.json
```

A node's own log is where it always was: `test/results/run-.../chains/<node>/daemon.out`,
and its `events.jsonl` under `logs/<node>/`.

## Things that will bite you

- **A pid inside a node is not a pid outside it.** A CORE node is a PID namespace as well
  as a network one, so the pid `multichaind` writes into `multichain.pid` means nothing in
  the root namespace. The harness signals through the fabric for exactly this reason; a
  stray `kill` typed at a shell prompt will hit something else, or nothing.
- **A crashed run leaves its session behind**, and with it the namespaces, the bridges and
  the addresses. `stop_network.py --run-dir <run>` deletes it. To see what is still there:
  `python3 -c "from core.api.grpc import client; c=client.CoreGrpcClient(); c.connect();
  print(c.get_sessions())"`.
- **`getpeerinfo` must only ever show `10.60.0.x` addresses.** If a `172.30.0.x` appears,
  the chain has formed on the control plane, there is no delay in the run at all, and the
  numbers describe a network nobody configured. The bootstrap asserts this and fails; if
  you ever see it pass by hand, do not use the results.
- **The block time has to clear the worst round trip.** The four shipped levels run at 10 s
  against a worst one-way path of 5 to 182 ms, which is ample. A profile that lowers
  `target-block-time` towards the RTT measures the emulator's queueing rather than the
  protocol.
- **Twenty namespaces and twenty daemons are not free.** The container is unconstrained by
  default, and it should stay that way for a measured run: a CPU quota nobody meant to set
  looks exactly like a slow protocol, and now competes with the emulated delay for the
  explanation of a slow block. `mcsim` records what it was given in every run.
