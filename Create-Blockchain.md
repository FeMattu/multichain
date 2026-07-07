# Create a Blockchain (MultiChain)

Complete guide to create, launch, and test a private MultiChain-based blockchain, both in single-node and distributed multi-node configuration.

Reference documentation: [MultiChain - Creating and connecting](https://www.multichain.com/developers/creating-connecting/).

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

A more robust alternative is to replace `$(pwd)/src` with the absolute path to the extracted or compiled MultiChain directory, so the PATH does not depend on the current working directory.

## 3. Functional Test: Single-Node Test Blockchain

This test verifies that the installation works correctly before moving on to a distributed network.

**Create the test chain** (generates default parameters in `~/.multichain/[chain-name]/params.dat`):

```bash
multichain-util create [chain-name]
```

**Inspect and edit consensus parameters** — in particular `mining-diversity` and `mining-turnover` — before the first launch:

```bash
nano ~/.multichain/[chain-name]/params.dat
```

> **Note:** `params.dat` can only be modified **before** the first daemon launch. Once the daemon starts, parameters are locked into the genesis block.

**Start the node in the background** (daemon mode with debug logging):

```bash
multichaind [chain-name] -daemon -debug
```

**Check the node status:**

```bash
multichain-cli [chain-name] getinfo
multichain-cli [chain-name] getblockchainparams
```

## 4. Multi-Node Network Test (WSL, localhost, different ports)

Simulate a distributed network of 3 nodes on WSL using separate terminals and different ports.

### Setup

When multiple nodes run on the same machine, each node should have:

- a dedicated data directory;
- a unique P2P port;
- a unique RPC port.

Using different `-datadir`, `-port`, and `-rpcport` values avoids collisions between local nodes and is the recommended approach for simulations on WSL or Linux.

### Suggested directory layout

A clean approach is to define a base directory and create one subdirectory per node:

```bash
export CHAINHOME="$HOME/chains/data"
mkdir -p "$CHAINHOME/node1" "$CHAINHOME/node2" "$CHAINHOME/node3"
```

The `-datadir` option tells MultiChain where to store the node's local blockchain state, wallet, configuration, logs, and peer metadata. This remains useful even after the network has already been created, because it keeps each node isolated and makes administration, backup, and debugging easier.

---

### Terminal 1 — Master Node

The first node creates the chain and becomes the initial admin node.

**Create the chain**


```bash
multichain-util -datadir="$CHAINHOME/node1" create [chain-name]
```

Before starting, verify that `params.dat` does not restrict the number of connectable nodes (`max-connections`) and that `anyone-can-connect` is set according to your needs. These settings can cause nodes to be rejected or disconnected.

**Run the master node and start the chain** - The `-port` and `-rpcport` flags are optional: if omitted, the daemon uses the default values from `params.dat`. Specify them explicitly when running multiple nodes on the same machine.

```bash
multichaind [chain-name] -daemon \
  -port=<P2P-port> \
  -rpcport=<RPC-port> \
  -datadir=$CHAINHOME/node1
```
On startup, the daemon prints the connection address for other nodes:

```bash
  multichaind [chain-name]@<seed-node-ip>:<seed-node-port>
```
To retrieve it at any time:

```bash
multichain-cli -datadir=$CHAINHOME/node1 [chain-name] getinfo
# Look for the "nodeaddress" field, e.g. [chain-name]@127.0.0.1:7447
```

Copy the value of the `nodeaddress` field; it will look like `[chain-name]@127.0.0.1:7447`.

## 5. Connecting additional nodes

A new node joining an existing chain for the first time must connect using the seed node syntax:

```bash
multichaind -datadir="$CHAINHOME/node2" [chain-name]@<master-node-ip>:<master-p2p-port>
```

or, if the master uses the default P2P port from `params.dat`:

```bash
multichaind -datadir="$CHAINHOME/node2" [chain-name]@<master-node-ip>
```

On the first run, this command is used to initialize the local copy of the chain and generate the joining node's address and credentials. If `anyone-can-connect=false`, the node is not yet fully allowed to connect until an admin grants the `connect` permission.


### Terminal 2 — Node 2 (connects to the master)

### Get node 2 address

After the first attempt, retrieve the node's wallet address:

```bash
multichain-cli -datadir="$CHAINHOME/node2" [chain-name] getaddresses
```

One of the returned addresses will be the address to authorize from the admin node.

### Grant permissions from the master

From node 1, grant at least the `connect` permission, and optionally `send`, `receive`, `mine`, or others depending on the experiment:

```bash
multichain-cli -datadir="$CHAINHOME/node1" -port=<master-p2p-port> -rpcport=<master-rpc-port> [chain-name] \
  grant <NODE2_ADDRESS> connect,send,receive,mine
```

If `anyone-can-connect=true`, this step is not necessary for basic connectivity, but it is still required for privileged actions such as mining when those permissions are restricted.

### Start node 2 as daemon

```bash
multichaind -datadir="$CHAINHOME/node2" [chain-name] -daemon \
  -port=<P2P-node2-port> \
  -rpcport=<RPC-node2-port> \
  -debug # optional, but useful during testing
```

Once the local configuration files exist, future launches can use the local chain name directly rather than the seed syntax.

### Terminal 3 — Node 3 (connects to the master)

**Step 1** - Repeat the same sequence for node 3:

```bash
multichaind -datadir="$CHAINHOME/node3" [chain-name]@<master-node-ip>:<master-p2p-port>
```

if `anyone-can-connect=true`, you can skip this step and connect directly with command at **step 3**.

**Step 2** - Then grant permissions from the master:

```bash
multichain-cli -datadir="$CHAINHOME/node1" -port=<master-p2p-port> -rpcport=<master-rpc-port> [chain-name] \
  grant <NODE3_ADDRESS> connect,send,receive,mine
```

**Step 3** - And finally start node 3 as daemon:

```bash
multichaind -datadir="$CHAINHOME/node3" [chain-name] -daemon \
  -port=<P2P-node3-port> \
  -rpcport=<RPC-node3-port> \
  -debug
```
## 6. Permission model

In MultiChain, permissions are explicit and central to network administration. If `anyone-can-connect=false`, a node can discover the network and generate its identity, but an admin must grant `connect` before that node can join properly. The same logic applies to `send`, `receive`, `mine`, `create`, `issue`, and other permission classes.

To inspect granted mining permissions:

```bash
multichain-cli -datadir="$CHAINHOME/node1" [chain-name] listpermissions mine
```

To inspect current peers:

```bash
multichain-cli -datadir="$CHAINHOME/node1" [chain-name] getpeerinfo
```

If multiple local nodes do not automatically discover each other, manual peer management may be needed because auto-discovery is known to be unreliable when several nodes share the same IP address but use different ports.

## 7. Transaction and block test

### Send a test transaction

From the master node, send funds to node 2:

```bash
multichain-cli -datadir="$CHAINHOME/node1" [chain-name] \
  sendtoaddress <NODE2_ADDRESS> 10
```

### Inspect the latest block

```bash
multichain-cli -datadir="$CHAINHOME/node1" [chain-name] getbestblockhash
```

```bash
multichain-cli -datadir="$CHAINHOME/node1" [chain-name] getblock \
  "$(multichain-cli -datadir="$CHAINHOME/node1" [chain-name] getbestblockhash)" true
```

This verifies whether the transaction has been included in a block and allows inspection of block metadata generated by the consensus process.

## 8. Useful Management Commands

| Command | Description |
|---|---|
| `multichain-cli -datadir="$CHAINHOME/node1" [chain-name] stop` | Stops the node daemon. |
| `multichain-cli -datadir="$CHAINHOME/node1" [chain-name] getpeerinfo` | Lists connected peers. |
| `multichain-cli -datadir="$CHAINHOME/node1" [chain-name] listblocks 0-10` | Shows details of the first blocks. |
| `multichain-cli -datadir="$CHAINHOME/node1" [chain-name] getmininginfo` | Shows current mining and consensus information. |
| `multichain-cli -datadir="$CHAINHOME/node1" [chain-name] validateaddress <address>` | Validates an address. |

Remember that when different nodes use different data directories, the same `-datadir` must also be passed to `multichain-cli`, otherwise the CLI may read the wrong RPC credentials or connect to the wrong RPC port.

## 9. Baseline Achieved

- Do not reuse the same `-port` or `-rpcport` across different nodes on the same machine.
- Do not forget `-datadir` on CLI commands when managing a non-default node directory, otherwise RPC authentication errors can occur.
- Do not expect a first join command alone to be sufficient when `anyone-can-connect=false`; an admin grant is required.
- Do not modify `params.dat` after the first chain launch expecting the running chain to inherit those changes.
- If remote RPC access is needed, review `rpcallowip`, because by default MultiChain accepts RPC requests only from localhost.

## Notes

- Using separate `-datadir` paths allows running multiple nodes on the same machine without configuration conflicts .
- The `-debug` flag in `multichaind` produces detailed logs useful for consensus debugging, but should be removed in production environments.