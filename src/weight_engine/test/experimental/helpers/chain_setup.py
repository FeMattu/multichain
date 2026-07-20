# Copyright (c) 2014-2019 Coin Sciences Ltd
# MultiChain code distributed under the GPLv3 license, see COPYING file.
#
# chain_setup.py -- MultiChain network lifecycle for the WeightEngine experiment.
#
# This is a Python port of the permissioned-bootstrap protocol proven in
# src/wpoa/test/functional_lib.sh (create -> start seed -> grant -> rejoin), kept
# deliberately faithful to it: node 0 is the seed/genesis node, every other node
# launches once (prints the grant hint and exits), is granted connect/send/receive
# /mine + wpoa-weights.write from node 0, then relaunched to join. The one addition
# for this experiment is the ADMIN role: node 0 keeps global admin (it is the
# genesis node) but has its MINE permission revoked once the miner set is live, so
# it writes the governance streams without ever proposing a block.
#
# Node exposes a thin multichain-cli wrapper (cli / cli_ok) that strips the
# one-line request echo some builds print before the JSON result.

import json
import os
import shutil
import subprocess
import tempfile
import time

import config


class MCError(Exception):
    """An RPC call returned a MultiChain error (non-zero exit / error payload)."""


def looks_txid(s):
    """True if s contains a 64-hex-char transaction id (the shape MultiChain
    prints for a successful publish / send / grant)."""
    import re
    return isinstance(s, str) and re.search(r"[0-9a-fA-F]{64}", s) is not None


def _repo_bindir():
    """.../src, where multichaind / multichain-util / multichain-cli live."""
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.abspath(os.path.join(here, "..", "..", "..", ".."))


def _parse_cli_output(text):
    """Parse multichain-cli output into (result, is_error).

    Some builds prefix the result with a one-line request echo ({"method":...});
    that line is dropped. The remaining body is the RESULT: it may be a multi-line
    JSON object/array, OR a bare UNQUOTED token (an address or a txid), which is not
    valid JSON. So we try a STRICT full-body json.loads and, only if that fails,
    fall back to the raw text. (A naive raw_decode would swallow the leading digits
    of a bare address/txid as a JSON number -- the bug this replaces.)"""
    is_error = ("error code:" in text) or ("error message:" in text)
    body = "\n".join(ln for ln in text.splitlines()
                     if not ln.lstrip().startswith('{"method"')).strip()
    if not body:
        return "", is_error
    try:
        return json.loads(body), is_error
    except ValueError:
        return body, is_error


class Node(object):
    """One MultiChain node: its datadir, ports, and a multichain-cli wrapper."""

    def __init__(self, index, label, datadir, rpcport, p2pport, bindir, chain):
        self.index = index
        self.label = label          # "admin" / "M1" ...
        self.datadir = datadir
        self.rpcport = rpcport
        self.p2pport = p2pport
        self.bindir = bindir
        self.chain = chain
        self.address = None         # main wallet address, resolved after start

    # -- multichain-cli -----------------------------------------------------
    def _run_cli(self, args):
        cmd = [os.path.join(self.bindir, "multichain-cli"),
               "-datadir=%s" % self.datadir, "-rpcport=%d" % self.rpcport,
               self.chain] + [str(a) for a in args]
        p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                           universal_newlines=True)
        return p.returncode, p.stdout

    def cli_ok(self, *args):
        """Run a CLI command WITHOUT raising. Returns (ok, result). result is the
        decoded JSON when the body is JSON, else the raw text (a bare txid/address,
        or an error blob when ok is False)."""
        rc, out = self._run_cli(args)
        result, is_error = _parse_cli_output(out)
        ok = (rc == 0) and not is_error
        return ok, result

    def cli(self, *args):
        """Run a CLI command, raising MCError on failure. Returns parsed JSON when
        available, otherwise the trimmed text result (bare txid, etc.)."""
        ok, res = self.cli_ok(*args)
        if not ok:
            raise MCError("%s: `%s` failed:\n%s" %
                          (self.label, " ".join(str(a) for a in args), res))
        return res

    # -- convenience --------------------------------------------------------
    def up(self):
        ok, _ = self.cli_ok("getinfo")
        return ok

    def block_count(self):
        ok, res = self.cli_ok("getblockcount")
        if not ok:
            return -1
        try:
            return int(res)
        except (TypeError, ValueError):
            return -1

    def resolve_address(self):
        addrs = self.cli("getaddresses")
        if isinstance(addrs, list) and addrs:
            self.address = addrs[0]
        return self.address


class Network(object):
    """Owns the whole multi-node network: creation, bootstrap, teardown."""

    def __init__(self, mode, log):
        self.mode = mode
        self.log = log                       # log_reporter.LogReporter
        self.bindir = _repo_bindir()
        self.chain = "weexp%d" % os.getpid()
        self.node_args = config.node_args(mode)
        self.nodes = []                      # index 0 = admin, 1..N = miners
        self._up = False
        base = 21000 + (os.getpid() % 15000)
        self._alloc_base = base

    @property
    def admin(self):
        return self.nodes[0]

    @property
    def miners(self):
        return self.nodes[1:]

    # -- binaries -----------------------------------------------------------
    def require_binaries(self):
        for b in ("multichain-util", "multichaind", "multichain-cli"):
            path = os.path.join(self.bindir, b)
            if not (os.path.isfile(path) and os.access(path, os.X_OK)):
                raise MCError("binary not found or not executable: %s "
                              "(build the node first: ./autogen.sh && ./configure && make)" % path)

    # -- lifecycle ----------------------------------------------------------
    def _make_node(self, index, label):
        datadir = tempfile.mkdtemp(prefix="weexp_%s_" % label)
        rpcport = self._alloc_base + index * 10
        p2pport = rpcport + 1
        return Node(index, label, datadir, rpcport, p2pport, self.bindir, self.chain)

    def _daemon(self, node, connect_seed=None, extra=None):
        """Launch multichaind for a node (daemonised). connect_seed None -> genesis
        launch; otherwise join via chain@host:port."""
        target = connect_seed if connect_seed else self.chain
        cmd = [os.path.join(self.bindir, "multichaind"), target,
               "-datadir=%s" % node.datadir, "-port=%d" % node.p2pport,
               "-rpcport=%d" % node.rpcport, "-daemon"] + list(self.node_args)
        if extra:
            cmd += list(extra)
        logf = open(os.path.join(node.datadir, "node.log"), "w")
        subprocess.run(cmd, stdout=logf, stderr=subprocess.STDOUT,
                       universal_newlines=True)
        logf.close()

    def _wait_rpc(self, node, timeout):
        deadline = time.time() + timeout
        while time.time() < deadline:
            if node.up():
                return True
            time.sleep(1)
        return False

    def _grant_hint_address(self, node):
        """Scrape the 'grant <addr> connect' hint a joining node prints on first
        launch (matches functional_lib._fl_addr_from_log)."""
        try:
            with open(os.path.join(node.datadir, "node.log")) as f:
                text = f.read()
        except IOError:
            return None
        import re
        m = re.search(r"grant\s+([A-Za-z0-9]{30,40})\s+connect", text)
        return m.group(1) if m else None

    def start(self):
        """Create the chain, bring up the admin (seed) node and all miner nodes."""
        self.require_binaries()
        self.nodes = [self._make_node(0, "admin")]
        for i in range(config.NUM_MINERS):
            self.nodes.append(self._make_node(i + 1, config.miner_id(i)))
        self._up = True  # datadirs exist -> teardown must clean them

        self.log.info("chain=%s mode=%s nodes=%d (1 admin + %d miners)" %
                      (self.chain, self.mode, len(self.nodes), config.NUM_MINERS))

        # 1. create the chain in the admin's datadir.
        admin = self.admin
        rc = subprocess.run([os.path.join(self.bindir, "multichain-util"), "create",
                             self.chain, "-datadir=%s" % admin.datadir],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode
        if rc != 0:
            raise MCError("multichain-util create failed")
        self._tune_params(admin)

        # 2. start the seed (admin / genesis) node.
        self.log.info("starting admin/seed node 0 ...")
        self._daemon(admin, connect_seed=None)
        if not self._wait_rpc(admin, config.RPC_TIMEOUT):
            raise MCError("RPC did not come up on the admin node")
        admin.resolve_address()
        self.log.info("admin address: %s" % admin.address)

        # same-host peers dial loopback (getinfo nodeaddress can be a NAT addr on WSL).
        seed = "%s@127.0.0.1:%d" % (self.chain, admin.p2pport)

        # 3. bootstrap each miner: launch -> grant -> relaunch to join.
        for node in self.miners:
            self._bootstrap_miner(node, seed)

        # Bootstrap grants may still be unconfirmed; make mine permission solid on
        # every miner before any wPoA governance can begin (see method docstring).
        self.ensure_miners_can_mine()

    def _bootstrap_miner(self, node, seed):
        self.log.info("bootstrapping %s ..." % node.label)
        # first launch: initialises, prints the grant hint, exits without serving RPC.
        self._daemon(node, connect_seed=seed)
        for _ in range(5):
            if node.up():
                node.resolve_address()
                self.log.info("%s joined directly: %s" % (node.label, node.address))
                return
            time.sleep(1)

        addr = self._grant_hint_address(node)
        if not addr:
            raise MCError("%s: could not read grant-hint address from node.log" % node.label)
        self.log.info("%s address %s -> granting from admin" % (node.label, addr))
        self.admin.cli("grant", addr, "connect,send,receive,mine")
        self.admin.cli_ok("grant", addr, "wpoa-weights.write")  # best-effort

        deadline = time.time() + config.CONNECT_TIMEOUT
        while time.time() < deadline:
            self._daemon(node, connect_seed=seed)
            if self._wait_rpc(node, 4):
                node.resolve_address()
                self.log.info("%s joined: %s" % (node.label, node.address))
                return
            time.sleep(2)
        raise MCError("%s refused to join (see %s/node.log)" % (node.label, node.datadir))

    def _tune_params(self, admin):
        """Match params.dat to the experiment (fast blocks, short setup phase)."""
        params = os.path.join(admin.datadir, self.chain, "params.dat")
        if not os.path.isfile(params):
            raise MCError("params.dat not found at %s" % params)
        with open(params) as f:
            lines = f.readlines()
        repl = {
            "target-block-time": config.TARGET_BLOCK_TIME,
            "setup-first-blocks": config.SETUP_FIRST_BLOCKS,
            "mine-empty-rounds": 1000,      # keep mining even without pending tx
        }
        out = []
        import re
        for ln in lines:
            m = re.match(r"^(\s*)([a-z0-9-]+)(\s*=\s*)([-0-9.]+)(.*)$", ln)
            if m and m.group(2) in repl:
                out.append("%s%s%s%s%s\n" % (m.group(1), m.group(2), m.group(3),
                                             repl[m.group(2)], m.group(5)))
            else:
                out.append(ln)
        with open(params, "w") as f:
            f.writelines(out)

    # -- confirmation / height helpers -------------------------------------
    def wait_confirmed(self, node, txid, timeout=None):
        """Block until `txid` has >= 1 confirmation on `node`. Returns True on
        success, False on timeout / bad txid."""
        if not isinstance(txid, str) or len(txid) < 64:
            return False
        deadline = time.time() + (timeout if timeout else config.CONFIRM_TIMEOUT)
        while time.time() < deadline:
            ok, res = node.cli_ok("getrawtransaction", txid, 1)
            if ok and isinstance(res, dict) and res.get("confirmations", 0) >= 1:
                return True
            time.sleep(2)
        return False

    def wait_height(self, target, timeout=None, stallmsg="chain stalled"):
        """Drive/wait until the admin node's tip reaches `target`. (Mining is
        automatic; this only waits and reports.) Returns True on success."""
        deadline = time.time() + (timeout if timeout else config.DRIVE_TIMEOUT)
        last_h, stall_since = -1, time.time()
        while time.time() < deadline:
            h = self.admin.block_count()
            if h >= target:
                return True
            if h != last_h:
                last_h, stall_since = h, time.time()
            elif time.time() - stall_since >= 90:
                self.log.warn("%s -- stuck at height %d for 90s" % (stallmsg, h))
                stall_since = time.time()
            time.sleep(2)
        self.log.warn("only reached height %d of %d within timeout" %
                      (self.admin.block_count(), target))
        return False

    def ensure_miners_can_mine(self):
        """Re-grant connect/send/receive/mine to every miner's address and WAIT for
        the grants to confirm.

        Bootstrap grants can still be UNCONFIRMED when wPoA governance takes over at
        the end of the setup phase. An elected miner whose mine permission has not yet
        confirmed reports 'no local mining key' and cannot propose -- and since wPoA
        elects exactly one proposer per height, the chain stalls until (or unless)
        that grant confirms. Confirming mine for the exact address the engine keys the
        weight by (node.address) before sampling removes the race. Idempotent; harmless
        in native mode."""
        txids = []
        for node in self.miners:
            ok, res = self.admin.cli_ok("grant", node.address,
                                        "connect,send,receive,mine")
            if ok and looks_txid(res):
                txids.append(res)
        for txid in txids:
            self.wait_confirmed(self.admin, txid)
        ok, res = self.admin.cli_ok("listpermissions", "mine")
        mine_addrs = set(p.get("address") for p in res) if isinstance(res, list) else set()
        missing = [n.label for n in self.miners if n.address not in mine_addrs]
        if missing:
            self.log.warn("miners still without confirmed mine permission: %s" % missing)
        else:
            self.log.info("all %d miners hold confirmed mine permission" % len(self.miners))

    def ensure_wpoa_weights_stream(self):
        """Pre-create the OPEN wpoa-weights output stream on the admin (genesis, has
        create permission) and wait for it to confirm.

        The WeightEngine publishes each miner's w_k here via StreamWeightRegistry,
        which creates the stream lazily -- but only a create-permitted node can. In
        a normal wPoA deployment the genesis node is itself a validator and creates
        it; here the admin is deliberately NOT a cluster miner, so its engine never
        reaches the create step and the miners (no create permission) cannot make
        it. So the admin creates it explicitly. It is created OPEN, exactly as the
        registry would (create ["stream","wpoa-weights",true]), so any miner with
        send permission can then publish its weight -- no per-stream grant needed."""
        ok, streams = self.admin.cli_ok("liststreams", "*")
        have = isinstance(streams, list) and any(
            s.get("name") == "wpoa-weights" for s in streams)
        if have:
            self.log.info("wpoa-weights stream already exists")
            return True
        ok, res = self.admin.cli_ok("create", "stream", "wpoa-weights", "true")
        if ok and looks_txid(res):
            self.wait_confirmed(self.admin, res)
            # subscribe the admin so getallweights (queried on the admin) sees the
            # miners' published weights -- create does not auto-subscribe.
            self.admin.cli_ok("subscribe", "wpoa-weights")
            self.log.info("created open wpoa-weights output stream (admin subscribed)")
            return True
        self.log.error("could not create wpoa-weights stream: %s" % (res,))
        return False

    def demote_admin_from_mining(self):
        """Revoke the admin node's mine permission so it never proposes a block.
        Called once all miners are confirmed able to mine, so the chain never
        stalls for lack of a miner."""
        ok, _ = self.admin.cli_ok("revoke", self.admin.address, "mine")
        if ok:
            self.log.info("admin demoted from mining (mine permission revoked)")
        else:
            self.log.warn("could not revoke admin mine permission (continuing)")

    def teardown(self):
        if not self._up:
            return
        self.log.info("tearing down network ...")
        for node in reversed(self.nodes):
            node.cli_ok("stop")
        time.sleep(2)
        subprocess.run(["pkill", "-x", "multichaind"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for node in self.nodes:
            shutil.rmtree(node.datadir, ignore_errors=True)
        self._up = False
