# syntax=docker/dockerfile:1.7
# ===========================================================================
# POESIA / wPoA — build + simulation environment (Ubuntu 22.04)
#
# Why a container: MultiChain compiles against GCC 11 / Boost 1.74 (Ubuntu
# 22.04) and Shadow only officially supports 22.04 / 24.04, while the host runs
# a newer Ubuntu. The container supplies the *userspace*; the kernel is the
# host's, so simulations run at native speed (see docker/README.md,
# "Performance contract").
#
#   stage 1  shadow-builder : Rust toolchain + Shadow, pinned to one commit
#   stage 2  runtime        : MultiChain toolchain + Shadow + analysis stack
# ===========================================================================
ARG UBUNTU_VERSION=22.04

# ---------------------------------------------------------------------------
# Stage 1 — Shadow discrete-event simulator
# Dependency list from shadow/docs/install_dependencies.md (APT section).
# ---------------------------------------------------------------------------
FROM ubuntu:${UBUNTU_VERSION} AS shadow-builder

# Pinned to the exact commit that produced the recorded runs under
# shadow/runs/ and shadow/esperimenti/ (`shadow --version` reports
# v3.3.0-205-g93d3c32cc). Use a tag (e.g. v3.3.0) or `main` to move forward —
# and re-run the whole campaign if you do, because Shadow's scheduler is part
# of the experiment.
ARG SHADOW_REPO=https://github.com/shadow/shadow.git
ARG SHADOW_REF=93d3c32cc
# Same rustc that built the reference Shadow binary. Shadow's own CI pins 1.95
# (ci/rust-toolchain-stable.toml); anything >= that works.
ARG RUST_VERSION=1.98.0

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates \
        cmake \
        findutils \
        g++ \
        gcc \
        git \
        curl \
        libc-dbg \
        libclang-dev \
        libglib2.0-0 \
        libglib2.0-dev \
        make \
        netbase \
        pkg-config \
        python3 \
        python3-networkx \
        python3-yaml \
        util-linux \
        xz-utils \
    && rm -rf /var/lib/apt/lists/*

# rustup, system-wide so the build stage is reproducible regardless of $HOME
ENV RUSTUP_HOME=/opt/rustup \
    CARGO_HOME=/opt/cargo \
    PATH=/opt/cargo/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs \
      | sh -s -- -y --no-modify-path --profile minimal \
                 --default-toolchain "${RUST_VERSION}" \
    && rustc --version && cargo --version

# A full clone is deliberate: `git fetch <sha>` rejects abbreviated hashes, so
# a shallow fetch cannot resolve a short commit id.
RUN git clone "${SHADOW_REPO}" /usr/src/shadow \
    && git -C /usr/src/shadow checkout --detach "${SHADOW_REF}" \
    && git -C /usr/src/shadow --no-pager log --oneline -1

WORKDIR /usr/src/shadow
# /opt/shadow has no space characters: LD_PRELOAD (used for the shim) does not
# support them — shadow/docs/install_shadow.md.
RUN ./setup build --clean --jobs "$(nproc)" --prefix /opt/shadow \
    && ./setup install \
    && /opt/shadow/bin/shadow --version

# ---------------------------------------------------------------------------
# Stage 2 — runtime: compile MultiChain, run Shadow, analyse the output
# ---------------------------------------------------------------------------
FROM ubuntu:${UBUNTU_VERSION} AS runtime

ARG USER_NAME=mattu
ARG USER_UID=1000
ARG USER_GID=1000
# Keep the project at the same absolute path used by the recorded runs: every
# generated shadow.yaml embeds absolute paths, so an identical path keeps old
# artefacts, logs and processed-config.yaml directly comparable.
ARG PROJECT_DIR=/home/mattu/multichain

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    `# --- MultiChain build toolchain (README.md, Ubuntu 22.04 / GCC 11) ---` \
        build-essential \
        libtool \
        autotools-dev \
        automake \
        autoconf \
        pkg-config \
        git \
        libboost-all-dev \
        libevent-dev \
    `# --- Shadow runtime (the shim needs glib; lscpu drives CPU pinning) ---` \
        libglib2.0-0 \
        libc-dbg \
        netbase \
        util-linux \
        xz-utils \
        findutils \
        iproute2 \
        procps \
    `# --- analysis stack: apt versions on 22.04 are exactly the ones the` \
    `#     recorded campaigns were produced with (networkx 2.4, numpy 1.21.5,` \
    `#     pandas 1.3.5, scipy 1.8.0, jsonschema 3.2.0) ---` \
        python3 \
        python3-pip \
        python3-networkx \
        python3-numpy \
        python3-pandas \
        python3-scipy \
        python3-jsonschema \
        python3-yaml \
    `# --- helpers used by shadow/tools/*.sh and run.sh ---` \
        gawk \
        bc \
        curl \
        ca-certificates \
        wget \
        tar \
        gzip \
        file \
        less \
        nano \
    && rm -rf /var/lib/apt/lists/*

# shadow/README.md, "Reproducibility": the ESG draw uses awk srand()/rand(),
# whose sequence depends on the awk implementation. The reference runs used GNU
# awk 5.1.0; Ubuntu would otherwise default `awk` to mawk.
RUN update-alternatives --set awk /usr/bin/gawk && awk -W version 2>&1 | head -1

# openpyxl 3.1.5 (xlsx workbooks in tools/pipeline/phase3_analyze.py). apt ships
# 3.0.9, which is not what the stored workbooks were written with.
COPY requirements.txt /usr/local/share/poesia/requirements.txt
RUN python3 -m pip install --no-cache-dir --upgrade-strategy only-if-needed \
        -r /usr/local/share/poesia/requirements.txt \
    && python3 -m pip cache purge || true

COPY --from=shadow-builder /opt/shadow /opt/shadow

COPY entrypoint.sh preflight.sh build-multichain.sh /usr/local/bin/
RUN chmod 0755 /usr/local/bin/entrypoint.sh \
                /usr/local/bin/preflight.sh \
                /usr/local/bin/build-multichain.sh \
    && ln -sf /usr/local/bin/preflight.sh       /usr/local/bin/mc-preflight \
    && ln -sf /usr/local/bin/build-multichain.sh /usr/local/bin/mc-build

# Same uid/gid as the host user, so everything written into the bind-mounted
# repository stays owned by that user. The account is created only if that
# uid/gid is still free in the base image; the container then runs by numeric
# id, which is valid either way.
RUN set -eu; \
    if ! getent group "${USER_GID}" >/dev/null 2>&1; then \
        groupadd -g "${USER_GID}" "${USER_NAME}"; \
    fi; \
    if ! getent passwd "${USER_UID}" >/dev/null 2>&1; then \
        useradd -m -u "${USER_UID}" -g "${USER_GID}" -s /bin/bash "${USER_NAME}"; \
    fi; \
    install -d -o "${USER_UID}" -g "${USER_GID}" \
        "/home/${USER_NAME}" "$(dirname "${PROJECT_DIR}")" "${PROJECT_DIR}"

ENV HOME=/home/${USER_NAME} \
    MULTICHAIN_HOME=${PROJECT_DIR} \
    SIM_HOME=${PROJECT_DIR}/shadow \
    BINDIR=${PROJECT_DIR}/src \
    PATH=/opt/shadow/bin:${PROJECT_DIR}/src:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin \
    PYTHONUNBUFFERED=1 \
    LC_ALL=C.UTF-8 \
    LANG=C.UTF-8

# Re-declared: an ARG from stage 1 is not in scope here.
ARG SHADOW_REF=93d3c32cc
LABEL org.opencontainers.image.title="POESIA / wPoA simulation environment" \
      org.opencontainers.image.description="Ubuntu 22.04 userspace: MultiChain (GCC 11) + Shadow + analysis stack" \
      org.poesia.shadow.ref="${SHADOW_REF}"

USER ${USER_UID}:${USER_GID}
WORKDIR ${PROJECT_DIR}/shadow

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["bash"]
