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

Windows Build Notes
=====================

Please see the instructions in [win.md](/win.md/) to build MultiChain for use with Windows.


Mac Build Notes (on MacOS Sierra)
================

Please see the instructions in [mac.md](/mac.md/) to build MultiChain for use with MacOS.
