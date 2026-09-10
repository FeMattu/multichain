# syntax=docker/dockerfile:1.7
# ===========================================================================
# POESIA / wPoA — build + emulation environment (Ubuntu 22.04)
#
# Why a container: MultiChain compiles against GCC 11 / Boost 1.74, which is
# Ubuntu 22.04, while the host may run something newer. The container supplies
# the *userspace*; the kernel is the host's, so namespaces, veth and tc are the
# host's real ones and an emulated run goes at native speed.
#
# WHAT THIS CONTAINERISES, AND WHAT IT DOES NOT
# ---------------------------------------------
# This image runs THE HARNESS in one container: that container builds the whole
# emulated network inside its own network namespace, and the twenty
# multichaind processes are ordinary processes inside it. That works today and
# is what ./docker/mcsim does.
#
# It is NOT `mode: docker`, which would put each NODE in its own container.
# That one is declared and deliberately deferred; the obstacle is the shared
# run directory, not the network. See experiments/docs/architecture.md,
# "Why native first".
#
# The container needs CAP_NET_ADMIN and its own network namespace, which mcsim
# supplies. It does not need --privileged.
# ===========================================================================
ARG UBUNTU_VERSION=22.04

FROM ubuntu:${UBUNTU_VERSION} AS runtime

ENV DEBIAN_FRONTEND=noninteractive

# --- MultiChain build toolchain --------------------------------------------
# Versions come from the top-level README; -march=native is deliberately NOT
# used, because changing codegen changes the CPU time the emulated nodes
# consume and therefore the block times they produce.
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
        libssl-dev \
        libtool \
        pkg-config \
    && rm -rf /var/lib/apt/lists/*

# --- the emulated network --------------------------------------------------
# iproute2 gives ip and tc; iputils-ping and the netem module are what make a
# built fabric verifiable from inside the container.
RUN apt-get update && apt-get install -y --no-install-recommends \
        iproute2 \
        iputils-ping \
        iptables \
        kmod \
        procps \
        net-tools \
    && rm -rf /var/lib/apt/lists/*

# --- the analysis stack ----------------------------------------------------
# From apt on purpose: on 22.04 these are the versions that produced the
# archived campaign (networkx 2.4, numpy 1.21.5, pandas 1.3.5, scipy 1.8.0,
# jsonschema 3.2.0). networkx in particular is load-bearing - its GML
# reader/writer changed behaviour after 2.4.
RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 \
        python3-pip \
        python3-yaml \
        python3-jsonschema \
        python3-numpy \
        python3-scipy \
        python3-pandas \
        python3-matplotlib \
        python3-networkx \
        python3-pytest \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /tmp/requirements.txt
RUN python3 -m pip install --no-cache-dir -r /tmp/requirements.txt \
    && rm /tmp/requirements.txt

# --- helpers ---------------------------------------------------------------
COPY build-multichain.sh /usr/local/bin/mc-build
COPY preflight.sh        /usr/local/bin/preflight.sh
COPY entrypoint.sh       /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/mc-build /usr/local/bin/preflight.sh \
             /usr/local/bin/entrypoint.sh \
    && ln -s /usr/local/bin/preflight.sh /usr/local/bin/mc-preflight

# Where the repository is bind-mounted. No personal path is baked in: mcsim
# and docker-compose pass the host's own checkout path, and MULTICHAIN_HOME
# tells everything inside the container where it landed.
ARG PROJECT_DIR=/workspace/multichain
ENV MULTICHAIN_HOME=${PROJECT_DIR}
ENV PYTHONDONTWRITEBYTECODE=1
WORKDIR ${PROJECT_DIR}

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["bash"]
