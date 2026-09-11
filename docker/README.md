# Container environment

**One Ubuntu 22.04 environment for the whole experiment.** A single image
holds the MultiChain build toolchain, the CORE network emulator and the
analysis stack; the harness is bind-mounted into it. Build MultiChain, emulate
the network, run the campaign and analyse it without leaving the container.

The kernel is the host's, so namespaces, veth and `tc` are the host's real
ones and a run goes at native speed. The container supplies the *userspace* —
which is the point: MultiChain compiles against GCC 11 / Boost 1.74 and CORE
ships a `.deb` for 22.04, while the host may run something newer.

**Shadow is not involved anywhere.** Nothing in the image, in `mcsim`, in
`docker-compose.yml`, in the entrypoint or in `host-tune.sh` installs,
configures or tunes for it. The fabrics are CORE and plain Linux network
namespaces, and both are kernel primitives.

## What is containerised, and what is not

One container runs **the harness and CORE together**. CORE builds the emulated
network inside that container's own network namespace, and the `multichaind`
processes are ordinary processes inside the node namespaces CORE created.

It is **not** `mode: docker`, which would put each *node* in its own
container. That is declared in the harness and deliberately deferred; the
obstacle is the shared run directory, not the network. See
[../experiments/docs/architecture.md](../experiments/docs/architecture.md),
"Why native first".

## Use

```bash
./docker/mcsim build                 # build the image (MultiChain + CORE)
./docker/mcsim run mc-build          # compile MultiChain into src/
./docker/mcsim preflight             # can this container do it?

./docker/mcsim exp experiments/configs/experiments/smoke-3n.yaml
./docker/mcsim shell                 # poke around
```

`smoke-3n` is the right first run: three nodes, one of each role, and it
exercises the whole path from CORE session to analysis.

Every descriptor in `experiments/configs/experiments/` except `e2e-5n` asks
for `fabric.backend: auto`, and inside this image `auto` resolves to **CORE**,
because the entrypoint has already started `core-daemon` and waited for its
gRPC API to answer.

`docker compose` works too — copy `.env.example` to `.env` first; see the
header of `docker-compose.yml`.

Keep the output off the repository volume when you run anything large:

```bash
RESULTS_DIR=/data/poesia-runs ./docker/mcsim exp \
    experiments/configs/experiments/intercontinental.yaml
```

`RESULTS_DIR` is bind-mounted at `/results` and exported as
`EXPERIMENT_ROOT`.

## CORE

CORE 9.2.1 is installed from the official `.deb`, following the upstream
Ubuntu 22.04 guide. Two things the plain install does not do, and this image
does:

**It starts the daemon.** On a normal machine systemd does that. There is no
systemd here, and the harness's CORE fabric *connects* to a daemon rather than
starting one — so the entrypoint runs `core-up`, which starts `core-daemon`
and then waits until a real gRPC call succeeds. The wait matters: the port is
listening a second or two before the service behind it can answer, and a run
that connects in that window fails its preflight with "no CORE daemon
answering" and drops to the netns fallback.

```bash
core-status        # does CORE answer? exit 0 when it does
core-up            # start it (idempotent)
core-down          # stop it
```

Control it from the host with `MC_CORE=0` (do not start it), `MC_CORE=1`
(start it and report loudly on failure) or the default `auto`.

**It makes CORE's Python API visible to the harness.** The `.deb` confines
CORE to its own virtualenv at `/opt/core/venv`, while the harness runs on the
system `python3` — that is where the apt-pinned numpy, pandas and networkx
live. `experiments.runtime.fabric.core_emulator` does
`from core.api.grpc import client`, so the system interpreter has to see the
venv. The image writes a `.pth` file into `/usr/lib/python3/dist-packages`
pointing at the venv's `site-packages`.

A `.pth` rather than `PYTHONPATH` because it survives `sudo` stripping the
environment, and because `site` appends it *after* `dist-packages` — so the
apt versions of the analysis stack keep winning over anything CORE vendors.
Both interpreters are the same python3.10, so the venv's compiled wheels load
unchanged. The Dockerfile asserts all of this at build time; `mc-preflight`
re-checks it at run time, because a broken bridge otherwise surfaces only as
"CORE is not available" at fabric-selection time.

### EMANE and OSPF-MDR

| | default | why |
|---|---|---|
| OSPF-MDR | **on** | Part of the official install; CORE's zebra and OSPFv3 services call it. These topologies use static addressing and never start those services, so `./docker/mcsim build --no-ospf` is a safe, faster build. |
| EMANE | **off** | EMANE models *wireless* channels. Every topology in `experiments/configs` is wired — locations are L2 bridges, links are veth with netem — so EMANE is a long from-source build and a large layer that no experiment ever loads. `./docker/mcsim build --with-emane` turns it on. |

## Why each flag

| flag | why |
|---|---|
| `--cap-add NET_ADMIN` | veth pairs, addresses, routes, qdiscs. |
| `--cap-add SYS_ADMIN` | `ip netns add` — and CORE's own `vnoded` — is not only a network operation: it creates `/run/netns`, makes it a shared bind mount and calls `unshare(CLONE_NEWNET)`. `NET_ADMIN` covers none of the three, and without this the run dies at `mount --make-shared /run/netns failed: Operation not permitted`. |
| `--security-opt apparmor=unconfined` | Docker's default AppArmor profile denies `mount()` whatever the capabilities say, so `SYS_ADMIN` alone still fails — with *Permission denied* rather than *Operation not permitted*, which is the only way to tell the two causes apart. |
| `--network bridge` | its own network namespace, so twenty emulated nodes cannot reach the host's real network. `--network none` would remove `lo`, which the management bridge and CORE's gRPC socket both need. |
| `--tmpfs /run` | `ip netns` writes its handles under `/var/run/netns`, and CORE keeps its daemon pid and node handles there too. It must be writable and must accept mounts. |
| `--device /dev/net/tun` | CORE creates TAP interfaces for some node types. `mcsim` passes it only when the host has the device, because `--device` on a missing path fails the whole `docker run`. |
| `--ulimit nofile=1048576` | twenty daemons plus their peers exhaust the default soft limit; the entrypoint raises the soft limit to whatever hard limit you grant. |
| `-v <repo>:<PROJECT_DIR>` | the harness writes results and the build writes into `src/`. |

The capability and security flags together are still short of `--privileged`:
the rest of the capability set and the seccomp profile stay in force. What
they buy is exactly the ability to make a network namespace.

**No personal path is versioned.** `PROJECT_DIR` defaults to
`/workspace/multichain`, which is the mount point *inside* the container; the
host's own checkout is bind-mounted onto it by a relative path.

The entrypoint adds one thing the flags cannot express: it remounts
`/proc/sys` read-write. Both fabrics turn on IPv4 forwarding in node
namespaces with `sysctl -q -w`, which **exits 0 whether or not the write
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
| emulator | CORE 9.2.1 from the official `.deb`, `core-daemon` on its gRPC API, OSPF-MDR; EMANE on request |
| network | `iproute2` (`ip`, `tc`), `ethtool`, `nftables`, `ebtables`, `bridge-utils`, `iptables`, `iputils-ping`, `tcpdump` |
| analysis | Python 3.10 with numpy 1.21.5, scipy 1.8.0, pandas 1.3.5, networkx 2.4, matplotlib, jsonschema 3.2.0 from apt; openpyxl 3.1.5 from pip |
| helpers | `mc-build`, `mc-preflight`, `core-up`, `core-down`, `core-status` |

Everything except `openpyxl` comes from the Ubuntu archive on purpose: those
are the versions the archived campaign was analysed with. `ethtool` is not
decoration — CORE turns checksum offload off on every veth end it creates, and
logs an error per interface without it.

## Troubleshooting

**`no CORE daemon answering at 127.0.0.1:50051`** — run `core-up` in the
container: it prints the last lines of `/var/log/core/core-daemon.log` when
the daemon dies during startup. The usual cause is missing capabilities, which
`mc-preflight` reports separately.

**The run asks "Proceed anyway with the fallback mode?"** — CORE is not
usable, and the harness refuses to switch fabrics behind your back. Fix CORE
rather than answering `y`: `core-status`, then `mc-preflight`. Answering `y`
(or passing `--allow-fallback-without-core`) gives you the netns fabric, which
is honest but is not what the descriptor asked for.

**`CORE's Python API is not importable`** while `core-daemon` exists — the
`.pth` bridge out of `/opt/core/venv` is missing or broken. Rebuild:
`./docker/mcsim build`.

**`mount --make-shared /run/netns failed: Operation not permitted`** — the
container has `NET_ADMIN` but not `SYS_ADMIN`. Add `--cap-add SYS_ADMIN`.

**`mount --make-shared /run/netns failed: Permission denied`** — the
capability is there and AppArmor is refusing the mount. Add
`--security-opt apparmor=unconfined`.

**`ip netns` says the handle directory is missing** — `/run` is not writable.
`mcsim` mounts a tmpfs there; if you are calling `docker run` yourself, add
`--tmpfs /run:rw,exec,nosuid,size=128m`.

**Nodes in different locations cannot reach each other, but each location
works** — the nodes did not get IPv4 forwarding, because `/proc/sys` was
read-only and `sysctl -w` reported success anyway. Run `mc-preflight`: the
`/proc/sys is writable` line is the one to look at.

**`netem is not usable`** — the *host* kernel needs `sch_netem`; a container
cannot load a module. On the host: `sudo modprobe sch_netem sch_tbf`.

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
