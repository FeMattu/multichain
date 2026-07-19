MultiChain
==========

[MultiChain](http://www.multichain.com/) is an open source platform for private blockchains, which offers a rich set of features including extensive configurability, rapid deployment, permissions management, native assets and data streams. Although it is designed to enable private blockchains, MultiChain provides maximal compatibility with the bitcoin ecosystem, including the peer-to-peer protocol, transaction/block formats and [Bitcoin Core](https://bitcoin.org/en/bitcoin-core/) APIs/runtime parameters.

    Copyright (c) 2014-2019 Coin Sciences Ltd
    License: GNU General Public License version 3, see COPYING

    Portions copyright (c) 2009-2016 The Bitcoin Core developers
    Portions copyright many others - see individual files

System requirements
-------------------

These compilation instructions have been tested on Ubuntu 16.04 x64 (xenial) and Ubuntu 18.04 x64 (bionic) only and on Ubuntu 22.04 with GCC 11.

C++ compilers are memory-hungry, so it is recommended to have at least 1 GB of memory available when compiling MultiChain. With less memory, compilation may take much longer due to swapfile thrashing.


Linux Build Notes (on Ubuntu 22.04 x64) with compiler GCC 11
=================

Install dependencies
--------------------

    sudo apt-get update
    sudo apt-get install -y software-properties-common
    sudo apt-get install -y build-essential libtool autotools-dev automake pkg-config git
    sudo apt-get install libboost-all-dev
    sudo apt-get install libevent-dev

Clone MultiChain
----------------

    git clone https://github.com/MultiChain/multichain.git

Prepare to download or build V8
-------------------

    cd multichain
    MULTICHAIN_HOME=$(pwd)
    mkdir v8build
    cd v8build
    
You can use pre-built headers and binaries of Google's V8 JavaScript engine by downloading and expanding [linux-v8.tar.gz](https://github.com/MultiChain/multichain-binaries/raw/master/linux-v8.tar.gz) in the current directory (copy only `/v8` directory inside `/v8build`). If, on the other hand, you prefer to build the V8 component yourself, please follow the instructions in [V8.md](/V8.md/).


Compile MultiChain for Ubuntu (64-bit)
--------

```bash
cd $MULTICHAIN_HOME
./autogen.sh
./configure
make
```


Notes
-----

- If the build fails, it is likely due to GCC > 11. Use instead:

```bash
./configure CXXFLAGS="-O2 -std=c++11 -w" CFLAGS="-O2 -w"
```

Remove the `-w` flag to see all compiler warnings.
- Compilation can take a long time. Speed it up using all available cores:

```bash
make -j$(nproc)
```

- This builds `multichaind`, `multichain-cli`, and `multichain-util` in the `src` directory.
- Release builds use GCC; running `strip multichaind` removes debug symbols, reducing binary size by ~90%.


## Berkeley DB 4.8

Required only when compiling from source, for wallet compatibility. Not needed when using precompiled binaries.

### 1. Build Berkeley DB

```bash
BITCOIN_ROOT=$(pwd)
BDB_PREFIX="${BITCOIN_ROOT}/db4"
mkdir -p "${BDB_PREFIX}"

wget 'http://download.oracle.com/berkeley-db/db-4.8.30.NC.tar.gz'
tar -xzvf db-4.8.30.NC.tar.gz
cd db-4.8.30.NC/build_unix/
../dist/configure --enable-cxx --disable-shared --with-pic --prefix="${BDB_PREFIX}"
make install
cd "${BITCOIN_ROOT}"
```


### 2. Configure MultiChain with Berkeley DB

```bash
./autogen.sh

./configure \
  CXXFLAGS="-O2 -std=c++11 -w" \
  CFLAGS="-O2 -w" \
  LDFLAGS="-L${BDB_PREFIX}/lib/" \
  CPPFLAGS="-I${BDB_PREFIX}/include/" \
  --with-gui=no \
  --disable-tests \
  --disable-bench
```
run

    make

 or

    make -j$(nproc)

## Test Command

To check if everything after compilation its working run

    ./src/multichaind --version

To create and/or test the blockchain follow instructions in [Create-Blockchain.md](Create-Blockchain.md)

## wPoA — Weighted Proof-of-Authority

This build adds an optional **weighted proof-of-authority** consensus layer on top of
MultiChain's permissioned mining. It is **off by default**: a chain created without any
wPoA flag behaves as a plain MultiChain instance. Full design and internals are in
[src/wpoa/README.md](src/wpoa/README.md).

### Configuration model

Every wPoA switch is a **chain parameter** (introduced at protocol version `20014`).
You set it once, when the chain is created:

```bash
# Whole protocol on — baked into params.dat:
./src/multichain-util create mychain -enablewpoa=1

# Any node that joins INHERITS the configuration from params.dat — no flags needed:
./src/multichaind mychain                       # the creator / a local node
./src/multichaind mychain@<seed-ip>:<port>      # a joining node
```

Because the switches live in `params.dat`, a node that does not know how the network is
configured retrieves every parameter on connect and starts correctly with no
command-line flags. The **same names also work as runtime flags** on `multichaind`,
which override the inherited value for that node only (a divergent override logs a
consensus-fork warning, since these switches must match across the validator set).

### All flags

| Flag (CLI) / parameter (`params.dat`) | Phase | Default | Meaning |
|---|---|---|---|
| `-enablewpoa` / `-wpoaenable` &nbsp; (`enable-wpoa`) | master | `0` | Enable the **whole** protocol. Specific flags below override it per phase. |
| `-enablewpoaweights` &nbsp; (`enable-wpoa-weights`) | 1 | `0` | Run the `wpoa-weights` stream (validators register their weight). Can run standalone; forced on by any higher phase. |
| `-enablewpoaselection` &nbsp; (`enable-wpoa-selection`) | 2 | `0` | Weighted proposer selection (Efraimidis–Spirakis). Requires phase 1. |
| `-dumpfunction=<none\|sqrt\|log>` &nbsp; (`dump-function`) | 2 | `none` | Weight-dumping (damping) function applied before the draw. Consensus-critical. |
| `-enablewpoavrf` &nbsp; (`enable-wpoa-vrf`) | 3a | `0` | VRF randomness beacon (verifiable per-block reveal). Requires phase 2. |
| `-enablewpoarandao` &nbsp; (`enable-wpoa-randao`) | 3b | `0` | RANDAO beacon seed from accumulated reveals. Requires phase 3a. |
| `-wpoarandaolookback=<k>` &nbsp; (`wpoa-randao-lookback`) | 3b | `1` | RANDAO lookback distance `k`. Consensus-critical. |
| `-enablewpoasortition` &nbsp; (`enable-wpoa-sortition`) | 4 | `0` | Private (VRF-scored) sortition. Requires phase 3b and `k≥1`. |
| `-wpoasortitiondelay=<s>` &nbsp; (`wpoa-sortition-delay`) | 4 | `1` | Sortition delay scale in seconds. Consensus-critical. |
| `-weight=<n>` | — | `100` | This node's own validator weight (per-node, **not** a chain parameter). |

**Master + precedence.** `-enablewpoa` (alias `-wpoaenable`) turns every phase on; a more
specific `-enablewpoa*` flag overrides its phase. Example — full stack except sortition:

```bash
./src/multichain-util create mychain -enablewpoa=1 -enablewpoasortition=0
```

**Dependency constraints (hard fail).** Phases must be enabled bottom-up —
`weights → selection → vrf → randao → sortition` — and sortition additionally requires
`wpoa-randao-lookback ≥ 1`. In particular **RANDAO requires the VRF beacon** and
**sortition requires the VRF beacon** (transitively, via RANDAO). Enabling a phase
without its prerequisite is rejected with a clear error at chain creation *and* at node
startup; the node refuses to start rather than run a phase inert.

Windows Build Notes
=====================

Please see the instructions in [win.md](/win.md/) to build MultiChain for use with Windows.


Mac Build Notes (on MacOS Sierra)
================

Please see the instructions in [mac.md](/mac.md/) to build MultiChain for use with MacOS.
