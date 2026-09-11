# syntax=docker/dockerfile:1.7
# ===========================================================================
# POESIA / wPoA — ONE Ubuntu 22.04 environment for the whole experiment.
#
# Everything a run needs lives in this single image:
#
#   * the MultiChain build toolchain (GCC 11 / Boost 1.74), so `mc-build`
#     compiles the daemons here rather than on the host;
#   * CORE (Common Open Research Emulator) 9.x, installed exactly as the
#     official Ubuntu 22.04 guide does it, because CORE is the fabric the
#     harness drives;
#   * the Python analysis stack, pinned to the archive versions;
#   * the harness itself, bind-mounted at run time.
#
# Shadow is gone. Nothing in this image, in mcsim, in docker-compose.yml or in
# the entrypoint installs, configures or tunes for it; the harness's fabrics
# are CORE and plain network namespaces, both of which are kernel primitives.
#
# Why a container at all: MultiChain compiles against GCC 11 / Boost 1.74 and
# CORE ships a .deb for 22.04, while the host may run something newer. The
# container supplies the *userspace*; the kernel is the host's, so namespaces,
# veth and tc are the host's real ones and an emulated run goes at native
# speed.
#
# WHAT THIS CONTAINERISES, AND WHAT IT DOES NOT
# ---------------------------------------------
# One container runs THE HARNESS AND CORE together. CORE builds the emulated
# network inside that container's own network namespace and the multichaind
# processes are ordinary processes inside the node namespaces CORE created.
#
# It is NOT `mode: docker`, which would put each NODE in its own container.
# That one is declared and deliberately deferred; the obstacle is the shared
# run directory, not the network. See experiments/docs/architecture.md,
# "Why native first".
#
# WHAT THE CONTAINER NEEDS FROM THE HOST
# --------------------------------------
# CAP_NET_ADMIN for veth pairs, addresses, routes and qdiscs; CAP_SYS_ADMIN
# and an unconfined AppArmor profile because both `ip netns add` and CORE's
# own `vnoded` mount /run/netns and unshare a namespace, which no network
# capability covers; a writable /proc/sys, which the entrypoint arranges, so
# the nodes can turn on IPv4 forwarding. mcsim and docker-compose.yml supply
# all of it. It does not need --privileged.
#
# Resources are not capped anywhere in this image or its launchers: a run
# started without resource flags gets the whole machine, because a throttled
# run measures the throttle rather than the protocol.
# ===========================================================================
ARG UBUNTU_VERSION=22.04

FROM ubuntu:${UBUNTU_VERSION} AS runtime

ENV DEBIAN_FRONTEND=noninteractive \
    TZ=Etc/UTC \
    LANG=C.UTF-8

# --- what gets installed, and which versions -------------------------------
# CORE_VERSION is pinned to a release tag rather than fetched from
# `releases/latest`: an image that silently changes emulator version between
# two builds makes two campaigns incomparable for no visible reason.
ARG CORE_VERSION=9.2.1
ARG OSPF_MDR_REPO=https://github.com/USNavalResearchLaboratory/ospf-mdr.git

# OSPF-MDR is the MANET routing daemon CORE's zebra/OSPFv3 services call. The
# topologies in experiments/configs use CORE SWITCH nodes and static
# addressing, so nothing here needs it — but it is part of the official
# install and costs a few minutes, so it stays on by default and can be
# turned off for a fast rebuild.
ARG WITH_OSPF_MDR=1

# EMANE is OFF by default, and that is a considered choice rather than an
# omission. EMANE models *wireless* channels; every topology this harness
# runs is wired (locations are L2 bridges, links are veth with netem), so
# EMANE would add a long from-source build and a large layer that no
# experiment ever loads. Turn it on with --build-arg WITH_EMANE=1 when a
# wireless scenario actually needs it.
ARG WITH_EMANE=0
ARG EMANE_RELEASE=emane-1.5.1-release-1
ARG EMANE_GIT_TAG=v1.5.1
ARG PROTOC_VERSION=3.19.6

# ---------------------------------------------------------------------------
# 1) MultiChain build toolchain
# ---------------------------------------------------------------------------
# Versions come from the top-level README; -march=native is deliberately NOT
# used, because changing codegen changes the CPU time the emulated nodes
# consume and therefore the block times they produce.
#
# libevent is not optional: configure.ac stops with an error without it
# (libevent >= 2.0.21 and libevent_pthreads), and multichaind links against
# both at run time.
RUN apt-get update && apt-get install -y --no-install-recommends \
        autoconf \
        automake \
        bsdmainutils \
        build-essential \
        ca-certificates \
        curl \
        git \
        libboost-chrono-dev \
        libboost-filesystem-dev \
        libboost-program-options-dev \
        libboost-system-dev \
        libboost-test-dev \
        libboost-thread-dev \
        libevent-dev \
        libssl-dev \
        libtool \
        pkg-config \
        wget \
    && rm -rf /var/lib/apt/lists/*

# ---------------------------------------------------------------------------
# 2) The emulated network: what CORE and the netns fallback both drive
# ---------------------------------------------------------------------------
# iproute2 gives ip and tc. ethtool is not decoration: CORE turns checksum
# offload off on every veth end it creates, and without it node creation logs
# an error for each interface. nftables and ebtables are what CORE reaches for
# when it filters between bridge ports.
RUN apt-get update && apt-get install -y --no-install-recommends \
        bridge-utils \
        ebtables \
        ethtool \
        iproute2 \
        iptables \
        iputils-ping \
        kmod \
        net-tools \
        nftables \
        procps \
        psmisc \
        tcpdump \
    && rm -rf /var/lib/apt/lists/*

# ---------------------------------------------------------------------------
# 3) The analysis stack
# ---------------------------------------------------------------------------
# From apt on purpose: on 22.04 these are the versions that produced the
# archived campaign (networkx 2.4, numpy 1.21.5, pandas 1.3.5, scipy 1.8.0,
# jsonschema 3.2.0). networkx in particular is load-bearing - its GML
# reader/writer changed behaviour after 2.4.
#
# python3-tk and xterm are CORE's, not the analysis stack's: core-gui is a Tk
# application and CORE opens node consoles in xterm.
RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 \
        python3-pip \
        python3-venv \
        python3-tk \
        python3-yaml \
        python3-jsonschema \
        python3-numpy \
        python3-scipy \
        python3-pandas \
        python3-matplotlib \
        python3-networkx \
        python3-pytest \
        xterm \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /tmp/requirements.txt
RUN python3 -m pip install --no-cache-dir -r /tmp/requirements.txt \
    && rm /tmp/requirements.txt

WORKDIR /opt/build

# ---------------------------------------------------------------------------
# 4) OSPF-MDR (optional) — CORE's MANET routing services
# ---------------------------------------------------------------------------
RUN if [ "${WITH_OSPF_MDR}" = "1" ]; then \
        apt-get update && apt-get install -y --no-install-recommends \
            gawk libreadline-dev make && \
        git clone --depth 1 "${OSPF_MDR_REPO}" ospf-mdr && \
        cd ospf-mdr && \
        ./bootstrap.sh && \
        ./configure --disable-doc --enable-user=root --enable-group=root \
            --with-cflags=-ggdb --sysconfdir=/usr/local/etc/quagga \
            --enable-vtysh --localstatedir=/var/run/quagga && \
        make -j"$(nproc)" && make install && \
        cd /opt/build && rm -rf ospf-mdr && \
        rm -rf /var/lib/apt/lists/*; \
    else \
        echo "OSPF-MDR skipped (WITH_OSPF_MDR=${WITH_OSPF_MDR})"; \
    fi

# ---------------------------------------------------------------------------
# 5) EMANE (optional) — wireless channel emulation
# ---------------------------------------------------------------------------
RUN if [ "${WITH_EMANE}" = "1" ]; then \
        EMANE_PACKAGE="${EMANE_RELEASE}.ubuntu-22_04.amd64.tar.gz" && \
        wget -q "https://adjacentlink.com/downloads/emane/${EMANE_PACKAGE}" && \
        tar xf "${EMANE_PACKAGE}" && \
        cd "${EMANE_RELEASE}/debs/ubuntu-22_04/amd64" && \
        rm -f emane-spectrum-tools*.deb emane-model-lte*.deb *dev*.deb && \
        apt-get update && \
        apt-get install -y --no-install-recommends ./emane*.deb ./python3-emane_*.deb && \
        cd /opt/build && rm -rf "${EMANE_RELEASE}" "${EMANE_PACKAGE}" && \
        rm -rf /var/lib/apt/lists/*; \
    else \
        echo "EMANE skipped (WITH_EMANE=${WITH_EMANE}) — no wireless scenario needs it"; \
    fi

# ---------------------------------------------------------------------------
# 6) CORE itself, from the official .deb
# ---------------------------------------------------------------------------
# The .deb drops CORE's Python code into its own virtualenv at /opt/core/venv
# and puts core-daemon, core-gui, vnoded and vcmd on PATH.
RUN CORE_PACKAGE="core_${CORE_VERSION}_amd64.deb" && \
    wget -q "https://github.com/coreemu/core/releases/download/release-${CORE_VERSION}/${CORE_PACKAGE}" && \
    apt-get update && \
    apt-get install -y --no-install-recommends "./${CORE_PACKAGE}" && \
    rm -f "${CORE_PACKAGE}" && \
    rm -rf /var/lib/apt/lists/*

# --- EMANE's Python bindings, inside CORE's venv ---------------------------
# Only meaningful when EMANE was installed above: the bindings are built from
# the matching source tag and installed into the interpreter CORE runs.
RUN if [ "${WITH_EMANE}" = "1" ]; then \
        apt-get update && apt-get install -y --no-install-recommends \
            unzip libpcap-dev libpcre3-dev libprotobuf-dev libxml2-dev \
            protobuf-compiler uuid-dev && \
        wget -q "https://github.com/protocolbuffers/protobuf/releases/download/v${PROTOC_VERSION}/protoc-${PROTOC_VERSION}-linux-x86_64.zip" && \
        mkdir protoc && \
        unzip -q "protoc-${PROTOC_VERSION}-linux-x86_64.zip" -d protoc && \
        rm "protoc-${PROTOC_VERSION}-linux-x86_64.zip" && \
        git clone https://github.com/adjacentlink/emane.git && \
        cd emane && git checkout "${EMANE_GIT_TAG}" && \
        ./autogen.sh && ./configure --prefix=/usr && \
        cd src/python && PATH=/opt/build/protoc/bin:$PATH make && \
        /opt/core/venv/bin/python -m pip install . && \
        cd /opt/build && rm -rf emane protoc && \
        rm -rf /var/lib/apt/lists/*; \
    fi

# ---------------------------------------------------------------------------
# 7) Make CORE's Python API importable from the system interpreter
# ---------------------------------------------------------------------------
# This is the one piece of integration the official install does not do, and
# without it the whole image is two halves that cannot talk.
#
# The .deb confines CORE to /opt/core/venv, while the harness runs on the
# system python3 (that is where the apt-pinned numpy/pandas/networkx live).
# `experiments.runtime.fabric.core_emulator` does `from core.api.grpc import
# client`, so the system interpreter has to see the venv.
#
# A .pth file is the right tool rather than PYTHONPATH: it survives `sudo`
# stripping the environment, and because site appends it AFTER
# /usr/lib/python3/dist-packages, the apt versions of the analysis stack keep
# winning over anything CORE happens to vendor. Both interpreters are the same
# python3.10, so the venv's compiled wheels (grpcio) load unchanged.
RUN VENV_SITE="$(/opt/core/venv/bin/python -c 'import site; print(site.getsitepackages()[0])')" && \
    echo "${VENV_SITE}" > /usr/lib/python3/dist-packages/zz-core-venv.pth && \
    echo "bridged ${VENV_SITE} into the system interpreter"

# Prove it now rather than four steps into a run: a broken bridge otherwise
# surfaces as "CORE's Python API is not importable" at fabric selection time.
RUN python3 - <<'PY'
import networkx, numpy
from core.api.grpc import client, wrappers
print("core.api.grpc   OK  (%s)" % client.__file__)
print("networkx        %s" % networkx.__version__)
print("numpy           %s" % numpy.__version__)
assert "dist-packages" in networkx.__file__, \
    "networkx no longer comes from apt: the .pth is shadowing the pinned stack"
PY

# ---------------------------------------------------------------------------
# 8) Runtime state CORE expects to exist
# ---------------------------------------------------------------------------
# core-daemon is normally started by systemd, which creates these. There is no
# systemd here, so the image does it.
RUN mkdir -p /var/log/core /var/run/core /etc/core

# ---------------------------------------------------------------------------
# Cleanup and helpers
# ---------------------------------------------------------------------------
RUN apt-get clean && rm -rf /var/lib/apt/lists/* /opt/build/*

COPY build-multichain.sh /usr/local/bin/mc-build
COPY core-daemon.sh      /usr/local/bin/core-up
COPY preflight.sh        /usr/local/bin/preflight.sh
COPY entrypoint.sh       /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/mc-build /usr/local/bin/core-up \
             /usr/local/bin/preflight.sh /usr/local/bin/entrypoint.sh \
    && ln -s /usr/local/bin/preflight.sh /usr/local/bin/mc-preflight \
    && ln -s /usr/local/bin/core-up /usr/local/bin/core-down \
    && ln -s /usr/local/bin/core-up /usr/local/bin/core-status

# Where the repository is bind-mounted. No personal path is baked in: mcsim
# and docker-compose pass the host's own checkout path, and MULTICHAIN_HOME
# tells everything inside the container where it landed.
ARG PROJECT_DIR=/workspace/multichain
ENV MULTICHAIN_HOME=${PROJECT_DIR}
ENV PYTHONDONTWRITEBYTECODE=1
# The address the harness's `fabric.core_address` defaults to. Exported so
# core-up and the descriptors cannot drift apart.
ENV CORE_GRPC_ADDRESS=127.0.0.1:50051
WORKDIR ${PROJECT_DIR}

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["bash"]
