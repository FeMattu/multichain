# Container environment

An Ubuntu 22.04 **userspace** for building MultiChain and running the
emulation harness. The kernel is the host's, so namespaces, veth and `tc` are
the host's real ones and a run goes at native speed.

Two reasons to use it:

* the host runs something newer than 22.04 and MultiChain wants GCC 11 /
  Boost 1.74;
* you want the analysis stack pinned to the versions that produced the
  archived campaign — `networkx` in particular, whose GML reader changed
  behaviour after 2.4.

You do not need it otherwise. The harness runs fine on a host that has
`iproute2`, Python 3.8+ and the binaries.

## What is containerised, and what is not

This image runs **the harness** in one container. That container builds the
whole emulated network inside its own network namespace, and the twenty
`multichaind` processes are ordinary processes inside it.

It is **not** `mode: docker`, which would put each *node* in its own
container. That is declared in the harness and deliberately deferred; the
obstacle is the shared run directory, not the network. See
[../experiments/docs/architecture.md](../experiments/docs/architecture.md),
"Why native first".

## Use

```bash
./docker/mcsim build                 # build the image
./docker/mcsim run mc-build          # compile MultiChain into src/
./docker/mcsim preflight             # can this container do it?

./docker/mcsim exp experiments/configs/experiments/smoke-3n.yaml
./docker/mcsim shell                 # poke around
```

`docker compose` works too — copy `.env.example` to `.env` first; see the
header of `docker-compose.yml`.

Keep the output off the repository volume when you run anything large:

```bash
RESULTS_DIR=/data/poesia-runs ./docker/mcsim exp \
    experiments/configs/experiments/intercontinental.yaml
```

`RESULTS_DIR` is bind-mounted at `/results` and exported as
`EXPERIMENT_ROOT`.

## Why each flag

| flag | why |
|---|---|
| `--cap-add NET_ADMIN` | veth pairs, addresses, routes, qdiscs. |
| `--cap-add SYS_ADMIN` | `ip netns add` is not only a network operation: it creates `/run/netns`, makes it a shared bind mount and calls `unshare(CLONE_NEWNET)`. `NET_ADMIN` covers none of the three, and without this the run dies at `mount --make-shared /run/netns failed: Operation not permitted`. |
| `--security-opt apparmor=unconfined` | Docker's default AppArmor profile denies `mount()` whatever the capabilities say, so `SYS_ADMIN` alone still fails — with *Permission denied* rather than *Operation not permitted*, which is the only way to tell the two causes apart. |
| `--network bridge` | its own network namespace, so twenty emulated nodes cannot reach the host's real network. `--network none` would remove `lo`, which the management bridge needs. |
| `--tmpfs /run` | `ip netns` writes its handles under `/var/run/netns`, which must be writable and must accept mounts. |
| `--ulimit nofile=1048576` | twenty daemons plus their peers exhaust the default soft limit; the entrypoint raises the soft limit to whatever hard limit you grant. |
| `-v <repo>:<PROJECT_DIR>` | the harness writes results and the build writes into `src/`. |

The three capability/security flags together are still short of `--privileged`:
the device cgroup, the rest of the capability set and the seccomp profile stay
in force. What they buy is exactly the ability to make a network namespace.

**No personal path is versioned.** `PROJECT_DIR` defaults to
`/workspace/multichain`, which is the mount point *inside* the container; the
host's own checkout is bind-mounted onto it by a relative path.

The entrypoint adds one thing the flags cannot express: it remounts
`/proc/sys` read-write. The netns fabric turns on IPv4 forwarding in every
router namespace with `sysctl -q -w`, which **exits 0 whether or not the write
landed** — so on Docker's read-only `/proc/sys` the run does not fail, it
quietly produces a backbone that does not route. `mc-preflight` checks for it.

## Resources

**Started without resource flags, the container gets the whole machine** —
every CPU, all the memory. Nothing in the image, in `mcsim` or in
`docker-compose.yml` caps anything by default, and that is deliberate: a run
whose daemons are throttled measures the throttle rather than the protocol.
`mcsim` prints what the container was given before every run, and
`mc-preflight` reads the container's own cgroup back (`cpu.max`,
`memory.max`, `cpuset.cpus.effective`) so a quota nobody meant to set is
visible rather than mistaken for a slow chain.

Ask for less only when you mean to:

```bash
./docker/mcsim exp <descriptor> --cpus=8            # fractional quota
./docker/mcsim exp <descriptor> --cpuset=0,2,4,6    # pin to these CPUs
./docker/mcsim exp <descriptor> --memory=16g        # memory ceiling
```

`./docker/mcsim cpus` prints a physical-core-only list for `--cpuset`: pinning
to hyper-thread siblings costs a large fraction of the throughput and makes
block times look like protocol behaviour when they are scheduling. Under
compose the same three are `CPUS`, `CPUSET` and `MEMORY` in `.env`, empty or
`0` meaning no limit.

## What the image contains

| | |
|---|---|
| toolchain | GCC 11, Boost 1.74, autotools, OpenSSL, libevent — for MultiChain |
| network | `iproute2` (`ip`, `tc`), `iputils-ping`, `iptables`, `procps` |
| analysis | Python 3.10 with numpy 1.21.5, scipy 1.8.0, pandas 1.3.5, networkx 2.4, matplotlib, jsonschema 3.2.0 from apt; openpyxl 3.1.5 from pip |
| helpers | `mc-build`, `mc-preflight` |

Everything except `openpyxl` comes from the Ubuntu archive on purpose: those
are the versions the archived campaign was analysed with.

CORE is **not** in the image. Installing it inside a container is possible but
buys nothing here — the `netns` backend uses the same kernel primitives, and
the harness selects it automatically. Run CORE on the host if you want its
session management and GUI.

## Troubleshooting

**`mount --make-shared /run/netns failed: Operation not permitted`** — the
container has `NET_ADMIN` but not `SYS_ADMIN`. Add `--cap-add SYS_ADMIN`.

**`mount --make-shared /run/netns failed: Permission denied`** — the
capability is there and AppArmor is refusing the mount. Add
`--security-opt apparmor=unconfined`.

**`ip netns` says the handle directory is missing** — `/run` is not writable.
`mcsim` mounts a tmpfs there; if you are calling `docker run` yourself, add
`--tmpfs /run:rw,exec,nosuid,size=64m`.

**Nodes in different locations cannot reach each other, but each location
works** — the routers did not get IPv4 forwarding, because `/proc/sys` was
read-only and `sysctl -w` reported success anyway. Run `mc-preflight`: the
`/proc/sys is writable` line is the one to look at.

**`netem is not usable`** — the *host* kernel needs `sch_netem`; a container
cannot load a module. On the host: `sudo modprobe sch_netem sch_tbf`.

**`CAP_NET_ADMIN is missing`** — add `--cap-add NET_ADMIN`.

**The build fails on a `std=c++11` error** — GCC above 11 needs the standard
named explicitly for this source tree. `mc-build` passes it; a manual
`./configure` needs `CXXFLAGS="-O2 -std=c++11"`.

**Switching between a host build and a container build** — run
`mc-build --clean` once. The object files are not interchangeable, and a
binary built against a newer archive's Boost or libevent will not start in
here (`error while loading shared libraries`). `mc-preflight` runs
`multichaind --version` rather than just looking for the file, so it catches
this before a run does.

`./docker/host-tune.sh` reports the host settings a twenty-node run wants, and
`--apply` sets the ones it can. Nothing it does is persistent.

The harness's own environment check is more detailed and runs inside the
container too:

```bash
./docker/mcsim run experiments/scripts/check_environment.sh \
    --experiment experiments/configs/experiments/smoke-3n.yaml
```
