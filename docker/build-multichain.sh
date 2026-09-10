#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Compile MultiChain inside the container (Ubuntu 22.04 / GCC 11).
#
# Runs against the bind-mounted repository, so the resulting binaries land in
# src/ exactly where shadow/run.sh looks for them (BINDIR=<repo>/src).
#
#   mc-build                    configure if needed, then make -j$(nproc)
#   mc-build --clean            distclean first (do this once after switching
#                               between a host build and a container build)
#   mc-build --jobs 8           limit parallelism
#   mc-build --with-berkeley    also build Berkeley DB 4.8 and link against it
#                               (optional: configure.ac defaults --enable-berkeley to no)
#
# Flags come from README.md: GCC > 11 needs -std=c++11 explicitly, and the
# build is deliberately NOT tuned with -march=native — the recorded campaigns
# were produced with plain -O2 and changing codegen changes the CPU time the
# simulated nodes consume.
# ---------------------------------------------------------------------------
set -euo pipefail

ROOT="${MULTICHAIN_HOME:-}"
if [ -z "$ROOT" ]; then
    ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
fi
JOBS="$(nproc)"
CLEAN=0
BERKELEY=0
V8_URL="https://github.com/MultiChain/multichain-binaries/raw/master/linux-v8.tar.gz"

while [ "$#" -gt 0 ]; do
    case "$1" in
        --clean)         CLEAN=1 ;;
        --with-berkeley) BERKELEY=1 ;;
        --jobs)          JOBS="$2"; shift ;;
        --jobs=*)        JOBS="${1#*=}" ;;
        --root)          ROOT="$2"; shift ;;
        --root=*)        ROOT="${1#*=}" ;;
        --v8-url=*)      V8_URL="${1#*=}" ;;
        -h|--help)       awk 'NR>1 && /^#/ {sub(/^# ?/, ""); print; next} NR>1 {exit}' "$0"; exit 0 ;;
        *)               echo "unknown option: $1" >&2; exit 2 ;;
    esac
    shift
done

say() { printf '\033[1m[mc-build]\033[0m %s\n' "$*"; }
die() { printf '\033[31m[mc-build] %s\033[0m\n' "$*" >&2; exit 1; }

[ -f "$ROOT/configure.ac" ] || die "not a MultiChain tree: $ROOT"
[ -w "$ROOT" ] || die "$ROOT is not writable by $(id -u):$(id -g) — rebuild the image with USER_UID/USER_GID matching the host user"
cd "$ROOT"
say "tree: $ROOT   gcc: $(gcc -dumpversion)   jobs: $JOBS"

# --- V8 ---------------------------------------------------------------------
# v8build/ is not tracked in git (.gitignore) but src/Makefile.am links the V8
# static archives from v8build/v8/out.gn/x64.release/obj, so a fresh clone has
# to fetch the prebuilt tree first (README.md, "Prepare to download or build V8").
if [ -d v8build/v8/include ] && [ -d v8build/v8/out.gn ]; then
    say "V8: v8build/v8 already present"
else
    say "V8: fetching prebuilt tree from multichain-binaries"
    mkdir -p v8build
    TMP="$(mktemp -d)"
    trap 'rm -rf "$TMP"' EXIT
    curl -fsSL "$V8_URL" -o "$TMP/linux-v8.tar.gz" || die "download failed: $V8_URL"
    tar -xzf "$TMP/linux-v8.tar.gz" -C "$TMP"
    SRC="$(find "$TMP" -maxdepth 3 -type d -name v8 -print -quit)"
    [ -n "$SRC" ] || die "no v8/ directory inside the archive"
    rm -rf v8build/v8
    mv "$SRC" v8build/v8
    rm -rf "$TMP"; trap - EXIT
    [ -d v8build/v8/out.gn ] || die "v8build/v8/out.gn missing after extraction"
    say "V8: installed into v8build/v8"
fi

# --- optional Berkeley DB 4.8 ----------------------------------------------
BDB_CONFIGURE=()
if [ "$BERKELEY" = 1 ]; then
    BDB_PREFIX="$ROOT/db4"
    if [ ! -f "$BDB_PREFIX/lib/libdb_cxx-4.8.a" ]; then
        say "Berkeley DB 4.8: building into $BDB_PREFIX"
        mkdir -p "$BDB_PREFIX"
        if [ ! -d db-4.8.30.NC ]; then
            [ -f db-4.8.30.NC.tar.gz ] || \
                curl -fsSL 'http://download.oracle.com/berkeley-db/db-4.8.30.NC.tar.gz' \
                     -o db-4.8.30.NC.tar.gz
            tar -xzf db-4.8.30.NC.tar.gz
        fi
        # BDB 4.8 predates C++11: its atomic_init/__atomic_compare_exchange
        # names collide with the ones GCC 11 provides.
        sed -i 's/\(#define\s*__atomic_compare_exchange\)/\1_db/' \
            db-4.8.30.NC/dbinc/atomic.h || true
        sed -i 's/\batomic_init\b/atomic_init_db/g' \
            db-4.8.30.NC/dbinc/atomic.h \
            db-4.8.30.NC/mp/mp_region.c db-4.8.30.NC/mp/mp_mvcc.c \
            db-4.8.30.NC/mp/mp_fget.c db-4.8.30.NC/mutex/mut_method.c \
            db-4.8.30.NC/mutex/mut_tas.c || true
        ( cd db-4.8.30.NC/build_unix \
          && ../dist/configure --enable-cxx --disable-shared --with-pic \
                               --prefix="$BDB_PREFIX" >/dev/null \
          && make -j"$JOBS" >/dev/null && make install >/dev/null )
    else
        say "Berkeley DB 4.8: reusing $BDB_PREFIX"
    fi
    BDB_CONFIGURE=(--enable-berkeley
                   "LDFLAGS=-L$BDB_PREFIX/lib/"
                   "CPPFLAGS=-I$BDB_PREFIX/include/")
fi

# --- configure / make -------------------------------------------------------
if [ "$CLEAN" = 1 ]; then
    say "make distclean"
    make distclean >/dev/null 2>&1 || true
    rm -f configure
fi

[ -x ./configure ] || { say "./autogen.sh"; ./autogen.sh; }

if [ ! -f config.status ] || [ "$CLEAN" = 1 ]; then
    say "./configure"
    # Only switches this configure.ac actually defines: MultiChain has no GUI
    # target and no bench target, so the `--with-gui=no --disable-bench` pair
    # quoted in the root README (inherited from Bitcoin's instructions) would
    # only produce "unrecognized options" warnings.
    ./configure \
        CXXFLAGS="-O2 -std=c++11 -w" \
        CFLAGS="-O2 -w" \
        --disable-tests \
        "${BDB_CONFIGURE[@]}"
else
    say "reusing existing config.status (pass --clean to reconfigure)"
fi

say "make -j$JOBS"
make -j"$JOBS"

say "built:"
for b in multichaind multichain-cli multichain-util; do
    [ -x "src/$b" ] || die "src/$b missing after build"
    # the first line of MultiChain's --version output is blank
    printf '    %-18s %s\n' "$b" "$("src/$b" --version 2>/dev/null | grep -m1 .)"
done
say "done — BINDIR=$ROOT/src is what shadow/run.sh will use"
