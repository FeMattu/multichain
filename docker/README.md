# Containerised build & simulation environment

MultiChain compiles against **GCC 11 / Boost 1.74**, i.e. Ubuntu 22.04, and Shadow
officially supports only Ubuntu 22.04 / 24.04. When the machine that runs the campaign
is on a newer Ubuntu, the mismatch is in **userspace only** — which is exactly what a
container replaces.

The kernel stays the host's. There is no hypervisor, no virtual CPU, no second
scheduler, no emulated devices: the simulated nodes issue their syscalls to the same
kernel they would on bare metal, on the same cores, through the same page cache. That is
the whole reason this is a container and not a VM, and it is also why the flag set in
[`mcsim`](mcsim) is not negotiable — the default `docker run` sandbox *does* cost real
performance for this workload (see [Performance contract](#performance-contract)).

Shadow's oldest supported kernel is 5.10 and it is regularly tested on the newest Ubuntu
kernel, so a modern host kernel is an advantage, not a risk.

---

## Quick start

```bash
# 1. host kernel / CPU settings (report first, then apply)
sudo ./docker/host-tune.sh
sudo ./docker/host-tune.sh --apply --persist

# 2. build the image (compiles Shadow from source: ~10-30 min, ~3 GB)
./docker/mcsim build

# 3. compile MultiChain into src/ (fetches the prebuilt V8 tree if missing)
./docker/mcsim run mc-build

# 4. verify the container behaves like bare metal
./docker/mcsim preflight

# 5. run a simulation
./docker/mcsim sim config/simulations/tbt10s-cont-sqrt-5n.json

# ... or work interactively
./docker/mcsim shell
#   ./run.sh --config=config/simulations/tbt10s-cont-sqrt-5n.json
#   python3 tools/pipeline/run_pipeline.py --help
```

`docker compose` is supported as an alternative — see [`docker-compose.yml`](docker-compose.yml).

---

## What is in the image, and why

Derived from the actual dependencies of this repository: the root [`README.md`](../README.md)
build instructions, `shadow/docs/install_dependencies.md`, the imports of
`shadow/tools/**/*.py`, and the external commands invoked by `shadow/run.sh` and
`shadow/tools/*.sh`.

| Group | Contents | Why |
|---|---|---|
| MultiChain toolchain | `build-essential libtool autotools-dev automake autoconf pkg-config git libboost-all-dev libevent-dev` | root `README.md`, Ubuntu 22.04 / GCC 11 |
| V8 | prebuilt static archives, fetched by `mc-build` | `src/Makefile.am:502` links `v8build/v8/out.gn/x64.release/obj`; `v8build/` is not tracked in git |
| Berkeley DB 4.8 | **not installed** | `configure.ac:90` defaults `--enable-berkeley` to *no*, and the reference binaries link no `libdb`. Need it? `mc-build --with-berkeley` builds it into `db4/` with the GCC-11 `atomic_init` patch |
| Shadow (build stage) | `cmake findutils libclang-dev libc-dbg libglib2.0-{0,dev} make netbase pkg-config python3 python3-networkx python3-yaml xz-utils util-linux gcc g++` + rustup | `shadow/docs/install_dependencies.md` |
| Shadow (runtime) | `libglib2.0-0 util-linux netbase iproute2 procps` | the shim needs glib; Shadow uses `lscpu` for CPU pinning |
| Analysis stack | `python3-networkx python3-numpy python3-pandas python3-scipy python3-jsonschema python3-yaml` from apt, `openpyxl==3.1.5` from pip | `tools/gen_*.py`, `tools/check_topology.py`, `tools/collect_metrics.py`, `tools/valida_sortition_montecarlo.py`, `tools/pipeline/**` |
| Harness helpers | `gawk bc curl coreutils sed` | `tools/*.sh` — `bc` for the fixed-point arithmetic, `curl` for RPC, `timeout` for the bootstrap waits |

**`gawk`, not `mawk`.** `shadow/README.md` ("Reproducibility") states that the ESG draw
uses `awk`'s `srand()`/`rand()`, whose sequence depends on the implementation. The stored
campaigns were produced with GNU awk 5.1.0; Ubuntu points `awk` at `mawk` by default, so
the image runs `update-alternatives --set awk /usr/bin/gawk`.

---

## Performance contract

### The flags, and what each one costs if you drop it

| Flag | Why |
|---|---|
| `--security-opt seccomp=unconfined` | **The important one.** Docker's default profile is a BPF filter evaluated on *every syscall of every simulated node* — and this workload is nothing but syscalls. It also blocks `personality()`, which Shadow uses to disable ASLR: determinism is lost and each blocked call stalls for seconds (`shadow/ci/run.sh`, moby/moby#43011) |
| `--security-opt apparmor=unconfined` | removes LSM mediation from every file operation of every node datadir |
| `--cap-add SYS_PTRACE` | with seccomp back on, `ptrace` / `process_vm_readv` / `process_vm_writev` are how the shim and the simulator exchange state |
| `--cap-add SYS_NICE`, `SYS_RESOURCE` | thread priorities and limits for Shadow's workers |
| `--shm-size=1024g` | Shadow keeps one shared-memory block per managed thread in `/dev/shm`; Docker's 64 MiB default kills any real simulation (`shadow/docs/supported_platforms.md`) |
| `--ulimit nofile=1048576` | Shadow opens descriptors from its own process space for every managed process; too low means `EMFILE` mid-run |
| `--pids-limit=-1` | one simulation is thousands of threads |
| `--network host` | no veth pair, no NAT, no userland proxy — the simulated network is internal to Shadow anyway |
| bind mount of the repo | native filesystem: no overlayfs copy-up on every `debug.log` write. Results also survive the container |
| **no** `--cpus`, **no** `--memory`, **no** narrow `--cpuset-cpus` | Shadow reads its cgroup cpuset and pins one worker per CPU inside it (`shadow/docs/parallel_sims.md`). A CFS quota does not give it fewer cores, it gives it *throttled* cores — the worst case for a discrete-event scheduler that barriers on every time step |

With those flags the remaining container overhead is cgroup accounting and one extra
mount namespace: not measurable against a multi-hour simulation.

### Why seccomp is the flag that matters, in numbers

From the recorded 23-host continental run (`shadow/runs/tbt10s-cont-log-5n/shadow.log`,
`getrusage()` as reported by Shadow itself):

| Measure | Value | Consequence |
|---|---|---|
| `ru_stime` vs `ru_utime` | 560 min kernel vs 160 min user | **78 % of the CPU time is spent inside syscalls.** A BPF filter evaluated per syscall is a tax on the dominant cost of this workload, not a rounding error |
| voluntary + involuntary context switches | ~9.9 x 10^8 | the simulation is scheduler-bound: throttled cores (`--cpus`) hurt far more than they would in a compute-bound job |
| `shmem` (peak `/dev/shm`) | ~35 MiB | already more than half of Docker's 64 MiB default: the next larger topology simply fails |
| Shadow `ru_maxrss` / system total | 0.5 GiB / ~11 GiB of 16 GiB | with 23 nodes the box is close to full — swap is the real risk, so `vm.swappiness=1` |
| output size | ~820 MiB per run (node datadirs + `debug.log`) | keep `runs/` on local NVMe; that is the only I/O-heavy part |

`general.parallelism: 0` in every descriptor under `config/simulations/` means *Shadow*
picks the thread count from the CPU topology it can see — normally one worker per physical
core. That is another reason the container must see all CPUs: a `--cpus` quota or a
half-core cpuset changes the simulation's parallelism, not just its speed.

### What actually does cost you performance

* **Docker Desktop.** It runs containers inside a Linux VM. Use the native engine
  (`apt install docker.io`, or Docker CE) — `mcsim` and `host-tune.sh` both warn if they
  detect Desktop.
* **WSL2** (the current development machine) is likewise a VM. Fine for development,
  not for the final campaign.
* **A frequency-scaling governor.** Two identical runs can differ by double digits in
  wall clock. `host-tune.sh --apply` sets `performance`.
* **Swapping.** A simulation that swaps is a ruined measurement, not a slow one. Keep
  `vm.swappiness=1`, or `swapoff -a` for the campaign.
* **Two simulations sharing cores.** Shadow's pinning is not aware of other Shadow
  instances. Split the physical cores explicitly:

  ```bash
  ./docker/mcsim cpus                     # one CPU per physical core, e.g. 0,2,4,6,8
  ./docker/mcsim shell --cpuset=0,2,4     # run A
  ./docker/mcsim shell --cpuset=6,8       # run B
  ```

  Avoid pairing SMT siblings (they compete for one core) and keep a run inside a single
  NUMA node — both from `shadow/docs/parallel_sims.md`.
* **Disk-bound output.** `shadow.data/` plus one `debug.log` per node is the only heavy
  I/O in the pipeline. On a spinning disk or a network filesystem, put the repository on
  local NVMe, or trade durability for speed with `--runs-tmpfs=64g` (simulation output in
  RAM, **volatile**: copy `shadow/runs/<name>/` out before the container exits).

---

## Host tuning

`host-tune.sh` is report-only by default and prints current vs. target for every value.
The targets are Shadow's own recommendations (`shadow/docs/system_configuration.md`):

| Setting | Target | Effect |
|---|---|---|
| `fs.nr_open`, `fs.file-max` | 10485760 | ceiling for `--ulimit nofile`; a low `nr_open` silently caps the container |
| `vm.max_map_count` | 1073741824 | `mmap` regions per process; the default 65530 is the first wall a large simulation hits |
| `kernel.pid_max`, `kernel.threads-max` | 4194304 | the kernel clamps `threads-max` to roughly 1/8 of RAM, so the effective value will be lower — that is expected |
| `vm.swappiness` | 1 | see above |
| `scaling_governor` | `performance` | run-to-run wall-clock comparability. Resets at reboot; use `tuned`/`cpupower.service` to persist |

These are **not namespaced**, which is why they belong to the host: Docker refuses to set
non-namespaced sysctls, and `--privileged` would only let a container change them for the
whole machine. The container therefore stays unprivileged — `preflight.sh` reads the host
values and warns instead.

`--persist` writes `/etc/sysctl.d/99-shadow-sim.conf`; the cpufreq governor is not
persisted.

---

## Reproducibility

| Pinned | Value | Why |
|---|---|---|
| Shadow | `SHADOW_REF=93d3c32cc` (`v3.3.0-205-g93d3c32cc`) | the exact build behind the runs stored in `shadow/runs/` and `shadow/esperimenti/`. The simulator's scheduler is part of the experiment |
| Rust | `RUST_VERSION=1.98.0` | the toolchain that built that Shadow binary (Shadow's own CI pins 1.95) |
| Python stack | apt versions of Ubuntu 22.04 = `networkx 2.4`, `numpy 1.21.5`, `pandas 1.3.5`, `scipy 1.8.0`, `jsonschema 3.2.0`; `openpyxl 3.1.5` from pip | identical to the machine that produced the recorded campaigns. `networkx` matters most: its GML reader/writer changed after 2.4 and Shadow's GML parser is stricter than documented (`shadow/README.md`, point 4) |
| `awk` | GNU awk 5.1.0 | the ESG draw depends on the awk implementation |
| Compiler flags | `-O2 -std=c++11`, **no** `-march=native` | codegen changes how much CPU time a simulated node consumes. Do not "optimise" this mid-campaign |
| Project path | `/home/mattu/multichain` inside the container | every generated `shadow.yaml` embeds absolute paths; the same path keeps stored artefacts, logs and `processed-config.yaml` directly comparable |

Two caveats when moving off the current development machine:

* **`cpuid` emulation will probably switch on.** Shadow masks `rdrand`/`rdseed` by
  trapping `cpuid`, but only if the CPU and kernel support CPUID faulting
  (`src/main/core/manager.rs:196`). On WSL2 they do not, and `shadow/README.md` records
  that as a known source of non-determinism. On a native kernel Shadow will likely
  succeed — determinism *improves*, but the draws will not match the WSL runs even with
  the same seed. Re-baseline the campaign on the target machine rather than mixing the
  two.
* **apt versions float** inside 22.04 as updates land. To freeze them completely, pin the
  base image by digest (`FROM ubuntu:22.04@sha256:...`) in [`Dockerfile`](Dockerfile).

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Shadow dies early with a shared-memory / `shmalloc` error | `/dev/shm` too small | use `mcsim` (it sets `--shm-size`), or raise `SHM_SIZE` |
| Simulation is inexplicably slow, seconds-long pauses at startup | default seccomp profile blocking `personality()` | `--security-opt seccomp=unconfined` |
| `EMFILE` / "too many open files" mid-run | `nofile` too low, or host `fs.nr_open` caps it | `sudo ./docker/host-tune.sh --apply`, then rerun |
| Files in `shadow/runs/` owned by `root` or unwritable | image built with the wrong uid | rebuild: `./docker/mcsim build` (it passes your `id -u`/`id -g`) |
| `mc-build` fails linking V8 | `v8build/v8` missing or partial | `rm -rf v8build/v8 && mc-build` |
| Link errors mixing host and container objects | `src/*.o` left from a build on another distro | `mc-build --clean` |
| `shadow: command not found` | image built, but you are in a shell that is not the container's | `./docker/mcsim shell` |
| flags refused, or limits silently lower than requested | rootless Docker / Podman: `--ulimit` is capped by the invoking user's own limits and `apparmor=unconfined` can be denied | use rootful Docker for the campaign, or raise `nofile`/`nproc` for your user in `/etc/security/limits.conf` |
| Results differ from the stored campaigns | different Shadow commit, different `awk`, or `cpuid` emulation now active | see [Reproducibility](#reproducibility) |

---

## Files

| File | Role |
|---|---|
| [`Dockerfile`](Dockerfile) | two stages: Shadow from source (pinned commit) + the runtime environment |
| [`requirements.txt`](requirements.txt) | the only pip-installed package, and why it is not from apt |
| [`entrypoint.sh`](entrypoint.sh) | raises the soft `nofile` limit, runs the preflight on a TTY |
| [`preflight.sh`](preflight.sh) (`mc-preflight`) | in-container report: Shadow's hard requirements, hidden throttling, host sysctls |
| [`build-multichain.sh`](build-multichain.sh) (`mc-build`) | V8 fetch, optional BDB 4.8, `autogen`/`configure`/`make -j` |
| [`mcsim`](mcsim) | host-side wrapper: the flag set, `cpus`, `sim`, `tune` |
| [`host-tune.sh`](host-tune.sh) | host kernel/CPU settings, report-only unless `--apply` |
| [`docker-compose.yml`](docker-compose.yml), [`.env.example`](.env.example) | same container, compose syntax |
