# Create a Blockchain (MultiChain)

Complete guide to create, launch, and test a private MultiChain-based blockchain, both in single-node and distributed multi-node configuration.

## 1. Prerequisites

- Linux system or WSL (Windows Subsystem for Linux)
- Build dependencies: `build-essential`, `libssl-dev`, `libevent-dev`, `libboost-all-dev`
- MultiChain package downloaded and compiled (or precompiled binaries)

## 2. Add Binaries to the PATH

After extracting or compiling MultiChain, make the executables (`multichaind`, `multichain-cli`, `multichain-util`) available in every terminal session:

```bash
export PATH="$PATH:$(pwd)/src"
```

To make this change permanent, add the line to your `~/.bashrc` file:

```bash
echo 'export PATH="$PATH:$(pwd)/src"' >> ~/.bashrc
source ~/.bashrc
```

## 3. Functional Test: Single-Node Test Blockchain

This test verifies that the installation works correctly before moving on to a distributed network.

**Create the test chain** (generates default parameters in `~/.multichain/testchain/params.dat`):

```bash
multichain-util create testchain
```

**Start the node in the background** (daemon mode with debug logging):

```bash
multichaind testchain -daemon -debug
```

**Check the node status:**

```bash
multichain-cli testchain getinfo
multichain-cli testchain getblockchainparams
```

**Inspect/edit the consensus parameters**, in particular `mining-diversity` and `mining-turnover` (the key parameters for your consensus algorithm):

```bash
nano ~/.multichain/testchain/params.dat
```

> Note: parameters in `params.dat` can only be modified **before** the first daemon launch. Once the daemon starts, the configuration is locked into the genesis block .

## 4. Multi-Node Network Test (WSL, localhost, different ports)

Simulate a distributed network of 3 nodes on WSL using separate terminals and different ports.

### Terminal 1 — Master Node (creates and starts the chain)

```bash
multichaind testchain -daemon \
  -port=7447 \
  -rpcport=7448 \
  -datadir=$HOME/node1
```

Get the master node's connection address:

```bash
multichain-cli -datadir=$HOME/node1 testchain getinfo
```

Copy the value of the `nodeaddress` field; it will look like `testchain@127.0.0.1:7447`.

### Terminal 2 — Node 2 (connects to the master)

```bash
multichaind testchain@127.0.0.1:7447 -daemon \
  -port=7449 \
  -rpcport=7450 \
  -datadir=$HOME/node2
```

### Terminal 3 — Node 3 (connects to the master)

```bash
multichaind testchain@127.0.0.1:7447 -daemon \
  -port=7451 \
  -rpcport=7452 \
  -datadir=$HOME/node3
```

## 5. Granting Node Permissions

In MultiChain, new nodes can connect but **cannot mine or send transactions** until they receive explicit permissions from the admin node .

**Get node 2's address** (needed for authorization):

```bash
multichain-cli -datadir=$HOME/node2 testchain getaddresses
# Output: ["1XxxYyyZzz..."]
```

**Grant node2 and node3** mining and connection permissions (run from the master node):

```bash
multichain-cli -datadir=$HOME/node1 testchain \
  grant 1NODE2_ADDRESS mine,connect,send,receive

multichain-cli -datadir=$HOME/node1 testchain \
  grant 1NODE3_ADDRESS mine,connect,send,receive
```

**Verify granted permissions:**

```bash
multichain-cli -datadir=$HOME/node1 testchain listpermissions mine
```

## 6. Transaction Test and Block Verification

**Send a test transaction** from the master to node2:

```bash
multichain-cli -datadir=$HOME/node1 testchain \
  sendtoaddress 1NODE2_ADDRESS 10
```

**Verify the produced blocks**, including details of the miner who generated them:

```bash
multichain-cli -datadir=$HOME/node1 testchain getbestblockhash

multichain-cli -datadir=$HOME/node1 testchain getblock \
  $(multichain-cli -datadir=$HOME/node1 testchain getbestblockhash) true
```

## 7. Useful Management Commands

| Command | Description |
|---|---|
| `multichain-cli testchain stop` | Stops the node daemon |
| `multichain-cli testchain getpeerinfo` | Lists connected peers |
| `multichain-cli testchain listblocks 0-10` | Shows details of the first 10 blocks |
| `multichain-cli testchain getmininginfo` | Current mining/consensus info |
| `multichain-cli testchain validateaddress <address>` | Checks whether an address is valid |

## 8. Baseline Achieved

At this point the 3-node network is functional: the master node creates and distributes blocks, nodes 2 and 3 are authorized to mine, and transactions propagate and confirm across the whole network. This baseline is the starting point for modifying the `mining-diversity` and `mining-turnover` parameters and experimenting with variants of the hybrid consensus algorithm covered in the thesis.

## Notes

- Using separate `-datadir` paths allows running multiple nodes on the same machine without configuration conflicts .
- The `-debug` flag in `multichaind` produces detailed logs useful for consensus debugging, but should be removed in production environments.