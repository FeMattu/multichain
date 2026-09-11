# Installing CORE on a host

`install_core.sh` is the upstream Ubuntu 22.04 recipe
(<https://coreemu.github.io/core/install_ubuntu.html>) transcribed as a
script: system packages, OSPF-MDR, EMANE 1.5.1 and its Python bindings, then
the official CORE `.deb`. Run it on a machine where you want CORE **outside**
a container — edit the `cd ~/Desktop/thesis` lines first, they are the
author's own scratch directory.

## You probably do not want this

The container in [`..`](..) already installs CORE, exactly this way, next to
the MultiChain toolchain, the analysis stack and the harness. That is the one
environment the experiments run in:

```bash
./docker/mcsim build
./docker/mcsim run mc-build
./docker/mcsim exp experiments/configs/experiments/smoke-3n.yaml
```

This directory used to hold a second, CORE-only `Dockerfile` and
`docker-compose.yml`. They are gone: their contents were folded into
`../Dockerfile`, which is now the single image, so there is no longer a
version of CORE that can drift away from the one the harness talks to.

Two things `install_core.sh` does not do, and which a host install therefore
needs by hand — `../Dockerfile` does both:

* **start `core-daemon`.** On a systemd host `systemctl start core-daemon`
  covers it. The harness *connects* to a daemon; it never starts one.
* **make CORE's Python API visible to the harness.** The `.deb` confines CORE
  to `/opt/core/venv`, while the harness runs on the system `python3`. Either
  run the harness with `PYTHON=/opt/core/venv/bin/python`, or drop a `.pth`
  file naming the venv's `site-packages` into
  `/usr/lib/python3/dist-packages/`. Without one of the two,
  `fabric.backend: auto` reports CORE as unavailable and asks whether to fall
  back to plain network namespaces.
