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
# it writes the governance streams without ever proposing a block. In the MyLedger
# model that ADMIN node is the Apuana SB stand-in and the reconciliation counterparty.
#
# TRANSPORT (changed for the MyLedger topology). Node speaks JSON-RPC over a
# persistent HTTP connection instead of spawning `multichain-cli` per call. The
# MyLedger run issues ~50 companies x 10-20 transfers x 30 epochs -> tens of
# thousands of calls, where a per-call process spawn (~100 ms) would dominate the
# whole experiment; over HTTP the same call costs single-digit milliseconds. The
# `cli` / `cli_ok` signatures are UNCHANGED, so every caller is unaffected, and the
# CLI remains the automatic fallback whenever RPC credentials or the socket are
# unavailable.
#
# CALL CONVENTION. Because JSON-RPC is typed (the CLI's RPCConvertValues no longer
# runs), callers pass NATIVE PYTHON VALUES: numbers as int/float, booleans as bool,
# lists as list -- e.g. cli_ok("create", "stream", "wpoa-weights", True) and
# cli_ok("getaddressbalances", addr, 1). MultiChain's "hash-or-height" style
# arguments stay strings (cli_ok("getblock", str(h), 1)).

import json
import os
import shutil
import subprocess
import tempfile
import time

try:
    import http.client as _httplib          # py3
except ImportError:                          # pragma: no cover - py2 fallback
    import httplib as _httplib

import base64

import config


class MCError(Exception):
    """An RPC call returned a MultiChain error (non-zero exit / error payload)."""


class _TransportError(Exception):
    """The HTTP/JSON-RPC transport itself failed (socket, auth, malformed body).
    Distinct from MCError: it means 'retry or fall back to the CLI', not 'the node
    rejected the command'."""


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
    """One MultiChain node: its datadir, ports, and an RPC wrapper (HTTP JSON-RPC
    with a multichain-cli fallback)."""

    def __init__(self, index, label, datadir, rpcport, p2pport, bindir, chain):
        self.index = index
        self.label = label          # "ADMIN" / "ClusterMinerA" ...
        self.datadir = datadir
        self.rpcport = rpcport
        self.p2pport = p2pport
        self.bindir = bindir
        self.chain = chain
        self.address = None         # main wallet address, resolved after start
        # -- transport state ------------------------------------------------
        self._auth = None           # cached "Basic ..." header value
        self._conn = None           # persistent HTTPConnection
        self._req_id = 0
        self.rpc_calls = 0          # instrumentation: calls served over HTTP
        self.cli_calls = 0          # instrumentation: calls that fell back to the CLI

    # -- JSON-RPC transport -------------------------------------------------
    def _auth_header(self):
        """Read rpcuser/rpcpassword from <datadir>/<chain>/multichain.conf, which
        the node generates on first initialisation (mc_GenerateConfFiles). Returns
        None until the file exists -- the caller then uses the CLI."""
        if self._auth:
            return self._auth
        path = os.path.join(self.datadir, self.chain, "multichain.conf")
        user = pwd = None
        try:
            with open(path, "r", errors="replace") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("rpcuser="):
                        user = line.split("=", 1)[1].strip()
                    elif line.startswith("rpcpassword="):
                        pwd = line.split("=", 1)[1].strip()
        except (IOError, OSError):
            return None
        if not (user and pwd):
            return None
        token = base64.b64encode(("%s:%s" % (user, pwd)).encode("utf-8")).decode("ascii")
        self._auth = "Basic " + token
        return self._auth

    def _close_conn(self):
        if self._conn is not None:
            try:
                self._conn.close()
            except Exception:
                pass
            self._conn = None

    def _rpc_once(self, method, params):
        """One JSON-RPC round trip on the persistent connection. Returns
        (ok, result); raises _TransportError if the transport (not the node) failed."""
        auth = self._auth_header()
        if not auth:
            raise _TransportError("no rpc credentials yet")
        self._req_id += 1
        body = json.dumps({"method": method, "params": list(params),
                           "id": self._req_id, "chain_name": self.chain})
        headers = {"Authorization": auth, "Content-Type": "application/json",
                   "Connection": "keep-alive"}
        if self._conn is None:
            self._conn = _httplib.HTTPConnection("127.0.0.1", self.rpcport, timeout=120)
        try:
            self._conn.request("POST", "/", body, headers)
            resp = self._conn.getresponse()
            raw = resp.read()
            status = resp.status
        except Exception as exc:
            self._close_conn()
            raise _TransportError("http: %s" % exc)
        if resp.will_close:
            self._close_conn()
        if status == 401:
            self._auth = None                     # credentials rotated / wrong file
            self._close_conn()
            raise _TransportError("http 401 (authorization failed)")
        try:
            payload = json.loads(raw.decode("utf-8", "replace"))
        except ValueError:
            # A non-JSON body on a 5xx is a transport problem; on 200 it is a bug.
            self._close_conn()
            raise _TransportError("http %d: non-JSON body" % status)
        err = payload.get("error")
        if err:
            # Rendered like multichain-cli so log lines read identically either way.
            code = err.get("code") if isinstance(err, dict) else ""
            msg = err.get("message") if isinstance(err, dict) else str(err)
            return False, "error code: %s\nerror message:\n%s" % (code, msg)
        result = payload.get("result")
        return True, ("" if result is None else result)

    # -- multichain-cli (fallback) -----------------------------------------
    def _run_cli(self, args):
        """Spawn multichain-cli. Never raises: this is the LAST resort after the RPC
        transport already failed, so an unusable binary must surface as a normal error
        result (keeping cli_ok's no-raise contract) rather than an exception from
        inside error handling."""
        cmd = [os.path.join(self.bindir, "multichain-cli"),
               "-datadir=%s" % self.datadir, "-rpcport=%d" % self.rpcport,
               self.chain] + [_cli_arg(a) for a in args]
        try:
            p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                               universal_newlines=True)
        except OSError as exc:
            return 1, "error code: -1\nerror message:\ncannot run %s: %s" % (cmd[0], exc)
        return p.returncode, p.stdout

    # -- public API (unchanged signatures) ---------------------------------
    def cli_ok(self, *args):
        """Run a command WITHOUT raising. Returns (ok, result). result is the
        decoded JSON when the body is JSON, else the raw text (a bare txid/address,
        or an error blob when ok is False).

        Prefers JSON-RPC; falls back to multichain-cli on any transport failure
        (one retry first, since a dropped keep-alive is the common case)."""
        if not args:
            return False, "empty command"
        method, params = str(args[0]), args[1:]
        for attempt in (0, 1):
            try:
                ok, res = self._rpc_once(method, params)
                self.rpc_calls += 1
                return ok, res
            except _TransportError:
                self._close_conn()
                if attempt == 1:
                    break
        rc, out = self._run_cli(args)
        self.cli_calls += 1
        result, is_error = _parse_cli_output(out)
        return (rc == 0) and not is_error, result

    def cli(self, *args):
        """Run a command, raising MCError on failure. Returns parsed JSON when
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

    def gas_balance(self, address, minconf=1):
        """Confirmed GAS balance of `address`, as a float in EUR (1 GAS = 1 EUR).

        Reads getaddressbalances on THIS node, so it must be called on the node that
        owns the address's key (miners on their own node, companies/ADMIN/FEEPOOL on
        the admin node). Returns 0.0 when the address holds no GAS -- MultiChain
        simply omits an asset with a zero balance."""
        ok, res = self.cli_ok("getaddressbalances", address, minconf)
        if not ok or not isinstance(res, list):
            return 0.0
        for entry in res:
            if not isinstance(entry, dict):
                continue
            if entry.get("name") == config.GAS_ASSET_NAME:
                try:
                    return float(entry.get("qty", 0.0))
                except (TypeError, ValueError):
                    return 0.0
        return 0.0

    def close(self):
        self._close_conn()


def _cli_arg(a):
    """Render one native Python value for the multichain-cli fallback, where every
    argument is a string and RPCConvertValues re-parses the JSON-ish ones."""
    if isinstance(a, bool):
        return "true" if a else "false"
    if isinstance(a, (list, dict)):
        return json.dumps(a)
    return str(a)


class Network(object):
    """Owns the whole multi-node network: creation, bootstrap, teardown."""

    def __init__(self, mode, log):
        self.mode = mode
        self.log = log                       # log_reporter.LogReporter
        self.bindir = _repo_bindir()
        self.chain = "weexp%d" % os.getpid()
        self.node_args = config.node_args(mode)
        self.nodes = []                      # index 0 = admin, 1..N = cluster miners
        self._up = False
        base = 21000 + (os.getpid() % 15000)
        self._alloc_base = base

    @property
    def admin(self):
        return self.nodes[0]

    @property
    def miners(self):
        return self.nodes[1:]

    @property
    def admin_address(self):
        """The ADMIN (Apuana SB) address: reconciliation counterparty and the only
        writer of the governance streams."""
        return self.admin.address

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
        """Create the chain, bring up the ADMIN (seed) node and all cluster miners."""
        self.require_binaries()
        self.nodes = [self._make_node(0, config.ADMIN_LABEL)]
        for i in range(config.NUM_MINERS):
            self.nodes.append(self._make_node(i + 1, config.miner_id(i)))
        self._up = True  # datadirs exist -> teardown must clean them

        self.log.info("chain=%s mode=%s nodes=%d (1 ADMIN + %d cluster miners)" %
                      (self.chain, self.mode, len(self.nodes), config.NUM_MINERS))

        # 1. create the chain in the admin's datadir.
        admin = self.admin
        rc = subprocess.run([os.path.join(self.bindir, "multichain-util"), "create",
                             self.chain, "-datadir=%s" % admin.datadir],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode
        if rc != 0:
            raise MCError("multichain-util create failed")
        self._tune_params(admin)

        # 2. start the seed (ADMIN / genesis) node.
        self.log.info("starting ADMIN/seed node 0 (Apuana SB stand-in) ...")
        self._daemon(admin, connect_seed=None)
        if not self._wait_rpc(admin, config.RPC_TIMEOUT):
            raise MCError("RPC did not come up on the ADMIN node")
        admin.resolve_address()
        self.log.info("ADMIN address: %s" % admin.address)

        # R_k is DERIVED by the engine from each epoch's confirmed transfers to the
        # TREASURY address, so every node must be told which address that is -- and in
        # this deployment it is the ADMIN (Apuana SB), the counterparty the miners return
        # GAS to. The flag can only be added now, because the genesis address does not
        # exist until the ADMIN node has started and created its wallet.
        #
        # It goes into node_args, so every node launched from here on receives the SAME
        # value: the parameter is consensus-critical, and nodes disagreeing about it would
        # compute different R_k and therefore different w_k. The ADMIN itself is relaunched
        # immediately below for the same reason -- it started without the flag, and leaving
        # it with an empty treasury would make it the one node computing R_k = 0.
        self.node_args = list(self.node_args) + [
            "-weighttreasuryaddress=%s" % admin.address]
        self.log.info("treasury address (defines a reconciliation transfer): %s"
                      % admin.address)
        admin.cli("stop")
        time.sleep(3)
        self._daemon(admin, connect_seed=None)
        if not self._wait_rpc(admin, config.RPC_TIMEOUT):
            raise MCError("ADMIN node did not come back up after setting the treasury "
                          "address")

        # same-host peers dial loopback (getinfo nodeaddress can be a NAT addr on WSL).
        seed = "%s@127.0.0.1:%d" % (self.chain, admin.p2pport)

        # 3. bootstrap each cluster miner: launch -> grant -> relaunch to join.
        for node in self.miners:
            self._bootstrap_miner(node, seed)

        # Bootstrap grants may still be unconfirmed; make mine permission solid on
        # every miner before any wPoA governance can begin (see method docstring).
        self.ensure_miners_can_mine()
        self.log.info("transport: %s"
                      % ("JSON-RPC over HTTP" if admin.rpc_calls > admin.cli_calls
                         else "multichain-cli fallback"))

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
        self.log.info("%s address %s -> granting from ADMIN" % (node.label, addr))
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

    def wait_next_block(self, not_past=None, timeout=None):
        """Wait for ONE new block, quietly. Returns True if the tip advanced.

        Unlike wait_height this never warns on timeout and never waits beyond
        `not_past`: it is used to pace transaction submission inside an epoch, where
        falling behind must degrade to "submit the rest now", not to a stall."""
        h0 = self.admin.block_count()
        if not_past is not None and h0 >= not_past:
            return False
        deadline = time.time() + (timeout if timeout
                                  else max(10, 4 * config.TARGET_BLOCK_TIME))
        while time.time() < deadline:
            if self.admin.block_count() > h0:
                return True
            time.sleep(0.5)
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
            self.log.info("all %d cluster miners hold confirmed mine permission"
                          % len(self.miners))

    def ensure_wpoa_weights_stream(self):
        """Pre-create the OPEN wpoa-weights output stream on the admin (genesis, has
        create permission) and wait for it to confirm.

        The WeightEngine publishes each miner's w_k here via StreamWeightRegistry,
        which creates the stream lazily -- but only a create-permitted node can. In
        a normal wPoA deployment the genesis node is itself a validator and creates
        it; here the ADMIN is deliberately NOT a cluster miner, so its engine never
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
        ok, res = self.admin.cli_ok("create", "stream", "wpoa-weights", True)
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
        """Revoke the ADMIN node's mine permission so it never proposes a block.
        Called once all miners are confirmed able to mine, so the chain never
        stalls for lack of a miner."""
        ok, _ = self.admin.cli_ok("revoke", self.admin.address, "mine")
        if ok:
            self.log.info("ADMIN demoted from mining (mine permission revoked)")
        else:
            self.log.warn("could not revoke ADMIN mine permission (continuing)")

    def rpc_stats(self):
        """(http_calls, cli_fallback_calls) across every node -- reported in the
        summary so a silent fallback to the slow path is visible."""
        return (sum(n.rpc_calls for n in self.nodes),
                sum(n.cli_calls for n in self.nodes))

    def teardown(self):
        if not self._up:
            return
        self.log.info("tearing down network ...")
        for node in reversed(self.nodes):
            node.cli_ok("stop")
            node.close()
        time.sleep(2)
        subprocess.run(["pkill", "-x", "multichaind"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for node in self.nodes:
            shutil.rmtree(node.datadir, ignore_errors=True)
        self._up = False
