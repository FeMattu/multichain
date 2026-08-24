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
MultiChain's permissioned mining: block proposers are elected in proportion to a
per-validator **weight** rather than by round-robin. It is **off by default** — a chain
created without any wPoA flag behaves as a plain MultiChain instance.

> **Full design, internals, parameters and testing:
> [src/wpoa/README.md](src/wpoa/README.md).** That file is the entry map for the whole
> subsystem; the sections below cover only what an operator needs to start a chain.

### Configuration model

Every wPoA switch is a **chain parameter** (from protocol version `20014`). You set it
once, when the chain is created:

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
overriding the inherited value for that node only. The parameters are **hash-enforced**,
so a divergent override risks a silent fork: `AppInit2` logs a loud warning but does not
prevent startup.

`-enablewpoa` (alias `-wpoaenable`) turns every phase on; a more specific
`-enablewpoa*` flag then overrides its phase. Phases must be enabled bottom-up —
`weights → selection → vrf → randao → sortition → malus` — and a violation is a **hard
failure** at both chain creation and node startup.

```bash
# Full stack except sortition:
./src/multichain-util create mychain -enablewpoa=1 -enablewpoasortition=0
```

> **All 21 parameters** — name, type, default, valid range, defining and validating code
> line, consensus effect, network-fixed vs locally overridable — are catalogued in
> **[src/wpoa/docs/protocol-parameters.md](src/wpoa/docs/protocol-parameters.md)**.

### Where a validator's weight comes from

The authoritative channel is an **RPC write to the on-chain weights stream, by a node
that already holds the required permission**. The `-weight=<n>` command-line flag is
only a local fallback:

- with `-enableweightengine=1` the weight engine derives each cluster's weight from
  on-chain inputs and publishes it, and `-weight` is parsed, validated and logged but
  **never published**;
- the `wpoa-weights` stream is created **closed**, so publishing requires the
  `wpoa-weights.write` permission. A node without it carries **no weight in the
  election** and cannot set its own weight by any means;
- the two **attestation** streams behind the engine — records that make an unverifiable
  claim about a third party — are written only through the admin-gated RPCs
  `weightsetesg` and `weightsetreconciliation`;
- `weight-engine-membership` is instead **self-attested**: any node declares its own
  cluster through the public `weightregistermembership`, and the reader discards any
  record whose transaction signer differs from the `node_address` it declares. Joining a
  cluster is a voluntary choice, so the write is open to every node — nobody can declare
  membership on another node's behalf.

> The authoritative diagram of this flow, with both authorization gates, is in
> **[src/wpoa/docs/implementation-status.md](src/wpoa/docs/implementation-status.md)**.
> Module detail: [src/wpoa/docs/weight-engine.md](src/wpoa/docs/weight-engine.md).

### Build and test

```bash
./src/wpoa/test/run_unit_tests.sh            # wPoA unit suites, node-free
./src/weight_engine/test/run_unit_tests.sh   # weight-engine unit suites, node-free
./src/wpoa/test/run_all_tests.sh             # unit + the functional system run
```

Details and troubleshooting: [src/wpoa/docs/testing.md](src/wpoa/docs/testing.md).

Windows Build Notes
=====================

Please see the instructions in [win.md](/win.md/) to build MultiChain for use with Windows.


Mac Build Notes (on MacOS Sierra)
================

Please see the instructions in [mac.md](/mac.md/) to build MultiChain for use with MacOS.
