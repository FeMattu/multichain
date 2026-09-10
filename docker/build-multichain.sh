#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Compile MultiChain inside the container (Ubuntu 22.04 / GCC 11).
#
# Runs against the bind-mounted repository, so the binaries land in src/
# exactly where the harness looks for them by default.
#
#   mc-build                    configure if needed, then make -j$(nproc)
#   mc-build --clean            distclean first — do this once after switching
#                               between a host build and a container build
#   mc-build --jobs 8           limit parallelism
#   mc-build --with-berkeley    also build Berkeley DB 4.8 and link against it
#                               (configure.ac defaults --enable-berkeley to no)
#
# The build is deliberately NOT tuned with -march=native: changing codegen
# changes the CPU time the emulated nodes consume, and therefore the block
# times a run measures.
# ---------------------------------------------------------------------------
set -Eeuo pipefail
trap 'echo "[mc-build] failed at line $LINENO" >&2' ERR

ROOT="${MULTICHAIN_HOME:-}"
if [ -z "$ROOT" ]; then
    ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
fi
cd "$ROOT"

CLEAN=0; JOBS="$(nproc)"; BERKELEY=0
while [ $# -gt 0 ]; do
    case "$1" in
        --clean) CLEAN=1; shift ;;
        --jobs) JOBS="$2"; shift 2 ;;
        --with-berkeley) BERKELEY=1; shift ;;
        -h|--help) sed -n '2,18p' "$0"; exit 0 ;;
        *) echo "[mc-build] unknown argument: $1" >&2; exit 2 ;;
    esac
done

echo "[mc-build] repository: $ROOT"
echo "[mc-build] jobs: $JOBS"

if [ "$CLEAN" -eq 1 ] && [ -f Makefile ]; then
    echo "[mc-build] make distclean"
    make distclean >/dev/null 2>&1 || true
fi

if [ "$BERKELEY" -eq 1 ] && [ ! -d db4 ]; then
    echo "[mc-build] building Berkeley DB 4.8"
    mkdir -p db4
    tar -xzf db-4.8.30.NC.tar.gz
    (cd db-4.8.30.NC/build_unix && \
     ../dist/configure --enable-cxx --disable-shared --with-pic \
         --prefix="$ROOT/db4" >/dev/null && \
     make -j"$JOBS" >/dev/null && make install >/dev/null)
fi

if [ ! -f configure ]; then
    echo "[mc-build] autogen"
    ./autogen.sh
fi

if [ ! -f config.status ] || [ "$CLEAN" -eq 1 ]; then
    echo "[mc-build] configure"
    CONFIGURE_FLAGS=()
    if [ "$BERKELEY" -eq 1 ]; then
        CONFIGURE_FLAGS+=(--enable-berkeley
                          "LDFLAGS=-L$ROOT/db4/lib" "CPPFLAGS=-I$ROOT/db4/include")
    fi
    # GCC above 11 needs the standard named explicitly for this source tree.
    ./configure "${CONFIGURE_FLAGS[@]+"${CONFIGURE_FLAGS[@]}"}" CXXFLAGS="-O2 -std=c++11"
fi

echo "[mc-build] make -j$JOBS"
make -j"$JOBS"

echo
for binary in multichaind multichain-cli multichain-util; do
    if [ -x "src/$binary" ]; then
        echo "[mc-build] $binary: $(src/$binary --version 2>&1 | head -1)"
    else
        echo "[mc-build] WARNING: src/$binary was not produced" >&2
    fi
done
echo "[mc-build] done. The harness finds these automatically; MULTICHAIN_BIN overrides."
