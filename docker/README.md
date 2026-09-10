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
| `--cap-add NET_ADMIN` | creating namespaces, veth pairs and qdiscs. **The one flag without which nothing works.** Note it is not `--privileged`: the container needs network administration, not everything. |
| `--network bridge` | its own network namespace, so twenty emulated nodes cannot reach the host's real network. `--network none` would remove `lo`, which the management bridge needs. |
| `--tmpfs /run` | `ip netns` writes its handles under `/var/run/netns`, which must be writable. |
| `--ulimit nofile=1048576` | twenty daemons plus their peers exhaust the default soft limit; the entrypoint raises the soft limit to whatever hard limit you grant. |
| `-v <repo>:<PROJECT_DIR>` | the harness writes results and the build writes into `src/`. |
| `--cpuset-cpus` | optional. Use `./docker/mcsim cpus` for physical cores only: pinning to hyper-thread siblings costs throughput and makes block times look like protocol behaviour when they are scheduling. |

**No personal path is versioned.** `PROJECT_DIR` defaults to
`/workspace/multichain`, which is the mount point *inside* the container; the
host's own checkout is bind-mounted onto it by a relative path.

## What the image contains

| | |
|---|---|
| toolchain | GCC 11, Boost 1.74, autotools, OpenSSL — for MultiChain |
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

**`ip netns does not work`** — `/run` is not writable. `mcsim` mounts a tmpfs
there; if you are calling `docker run` yourself, add
`--tmpfs /run:rw,exec,nosuid,size=64m`.

**`netem is not usable`** — the *host* kernel needs `sch_netem`; a container
cannot load a module. On the host: `sudo modprobe sch_netem sch_tbf`.

**`CAP_NET_ADMIN is missing`** — add `--cap-add NET_ADMIN`.

**The build fails on a `std=c++11` error** — GCC above 11 needs the standard
named explicitly for this source tree. `mc-build` passes it; a manual
`./configure` needs `CXXFLAGS="-O2 -std=c++11"`.

**Switching between a host build and a container build** — run
`mc-build --clean` once. The object files are not interchangeable.

`./docker/host-tune.sh` reports the host settings a twenty-node run wants, and
`--apply` sets the ones it can. Nothing it does is persistent.

The harness's own environment check is more detailed and runs inside the
container too:

```bash
./docker/mcsim run experiments/scripts/check_environment.sh \
    --experiment experiments/configs/experiments/smoke-3n.yaml
```
