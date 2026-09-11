"""The administrative node: genesis, permissions, GAS, and the epoch sampler.

Ported from `role_admin.sh`, whose four phases (grant, refill, epoch_watch,
snapshot) become one controller: `setup` does the granting, `loop` does the
refill and the epoch sampling, `teardown` takes the final snapshot.

Collapsing them is deliberate. As four processes they had no shared state and
each re-derived the node list; the epoch sampler in particular had to be told
which epoch it had last seen through a file. As one controller they share it.
"""

from __future__ import annotations

import json
import time

from .base import RoleController

#: Streams the admin subscribes to. It is not a cluster head, so it publishes
#: no weight and the registry never subscribes it - without this the final
#: snapshot and weightverifyweights fail with "Not subscribed to this stream".
SUBSCRIBE = ["wpoa-weights", "weight-engine-esg", "weight-engine-membership",
             "wpoa-weights-malus"]


class AdminController(RoleController):
    role = "admin"

    def __init__(self, context):
        super().__init__(context)
        w = context.workload
        self.gas_company = float(w.get("gas_company", 100))
        self.gas_miner = float(w.get("gas_miner", 50))
        self.gas_threshold = float(w.get("gas_threshold", 20))
        self.gas_topup = float(w.get("gas_topup", 100))
        self.refill_every_s = float(w.get("refill_every_s", 30))
        self.epoch_margin = int(w.get("epoch_margin_blocks", 8))
        self._last_refill = 0.0
        self._last_epoch = context.setup_blocks // max(1, context.epoch_length)
        self._granted = False

    # -- setup --------------------------------------------------------------
    def setup(self) -> None:
        if not self.wait_rpc(600):
            raise RuntimeError("the admin's own daemon never answered RPC")
        own = self.publish_own_address()
        self.log.info("admin address (Apuana SB): %s", own)
        self._wait_for_peer_addresses()
        self._grant_permissions()
        self._create_streams()
        self._grant_stream_writes()
        self._subscribe()
        self._delegate_ca()
        self._import_treasury()
        self._distribute_gas()
        self._granted = True
        self.log.info("grant phase complete")

    def _wait_for_peer_addresses(self, timeout_s: float = 300.0) -> None:
        """Every other node must have deposited its address before we grant."""
        wanted = list(self.ctx.miners) + list(self.ctx.companies) + list(self.ctx.cas)
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            missing = [n for n in wanted if not self.address_of(n)]
            if not missing:
                self.log.info("all %d peer addresses collected", len(wanted))
                return
            self._sleep(5.0)
        self.log.warning("addresses still missing after %gs: %s", timeout_s,
                         ", ".join(n for n in wanted if not self.address_of(n)))

    def _grant(self, address: str, permissions: str) -> bool:
        if not address:
            return False
        if self.call("grant", [address, permissions]) is not None:
            self.log.info("grant %s -> %s", permissions, address)
            return True
        return False

    def _grant_permissions(self) -> None:
        for node in self.ctx.miners:
            self._grant(self.address_of(node), "connect,send,receive,mine")
        for node in list(self.ctx.companies) + list(self.ctx.cas):
            self._grant(self.address_of(node), "connect,send,receive")

    def _create_streams(self) -> None:
        # wpoa-weights MUST be created explicitly and CLOSED. With the weight
        # engine on, the registry does not create it until it has a weight to
        # publish, and it has no weight until membership and ESG records
        # exist: without this the chain stalls at setup-first-blocks with
        # "cannot score (unsynced or unweighted)".
        if self.call("create", ["stream", "wpoa-weights", False]) is not None:
            self.log.info("stream wpoa-weights created (closed)")
        else:
            self.log.info("stream wpoa-weights already present")
        self.wait_stream("wpoa-weights", 900)
        self.wait_stream("weight-engine-membership", 900)
        self.wait_stream("weight-engine-esg", 900)
        if self.call("create", ["stream", self.ctx.stream, True]) is not None:
            self.log.info("application stream created: %s (open)", self.ctx.stream)

    def _grant_stream_writes(self) -> None:
        # One stream per call: MultiChain rejects
        # grant addr "a.write,b.write" with "Could not parse entity key".
        for node in list(self.ctx.miners) + list(self.ctx.companies):
            address = self.address_of(node)
            self._grant(address, "wpoa-weights.write")
            self._grant(address, "weight-engine-membership.write")

    def _subscribe(self) -> None:
        for stream in SUBSCRIBE:
            if self.call("subscribe", [stream], quiet=True) is not None:
                self.log.info("subscribed to %s", stream)

    def _delegate_ca(self) -> None:
        # high1 carries the Certification Authority role. It is NOT implied by
        # being an administrator: it has to be delegated explicitly.
        for node in self.ctx.cas:
            address = self.address_of(node)
            self._grant(address, "high1")
            self._grant(address, "weight-engine-esg.write")

    def _import_treasury(self) -> None:
        if not self.ctx.treasury:
            self.log.warning("no treasury address: R_k will be zero for the whole run")
            return
        self._grant(self.ctx.treasury, "receive")
        # Watch-only: the admin sees the reconciled balance without those funds
        # entering the spendable balance that funds the refills.
        if self.call("importaddress", [self.ctx.treasury, "treasury", False]) is not None:
            self.log.info("treasury imported watch-only: %s", self.ctx.treasury)

    def _distribute_gas(self) -> None:
        height = self.block_count()
        for node in self.ctx.companies:
            if self.call("send", [self.address_of(node), self.gas_company]) is not None:
                self.csv_append("gas_transfers.csv",
                                [height, "init", node, self.gas_company])
                self.log.info("sent %s GAS to %s", self.gas_company, node)
        for node in list(self.ctx.miners) + list(self.ctx.cas):
            if self.call("send", [self.address_of(node), self.gas_miner]) is not None:
                self.csv_append("gas_transfers.csv",
                                [height, "init", node, self.gas_miner])
                self.log.info("sent %s GAS to %s", self.gas_miner, node)

    # -- loop ---------------------------------------------------------------
    def loop(self, tick: int) -> None:
        del tick
        if not self._granted:
            return
        now = time.monotonic()
        if now - self._last_refill >= self.refill_every_s:
            self._last_refill = now
            self._refill()
        self._sample_epochs()

    def _refill(self) -> None:
        """Keep every node solvent. No run may stop because a node ran dry."""
        height = self.block_count()
        for node in list(self.ctx.companies) + list(self.ctx.miners) + list(self.ctx.cas):
            balance = self.call("getbalance", node_id=node, quiet=True)
            try:
                balance = float(balance)
            except (TypeError, ValueError):
                continue
            self.csv_append("gas_balances.csv", [height, node, balance],
                            header=["height", "host", "balance"])
            if balance < self.gas_threshold:
                if self.call("send", [self.address_of(node), self.gas_topup]) is not None:
                    self.log.info("REFILL: %s had %.4f GAS -> +%s", node, balance,
                                  self.gas_topup)
                    self.csv_append("gas_transfers.csv",
                                    [height, "refill", node, self.gas_topup])

    def _sample_epochs(self) -> None:
        """Record what the end of the run could no longer reconstruct.

        An epoch is sampled only once closed AND buried under epoch_margin
        blocks - the same margin the weight engine takes before publishing.
        Sampling earlier photographs a verdict the engine has not issued.

        All ready epochs are taken, not just the latest: the burial window is
        a few heights wide and with a low target-block-time one sample per
        tick would skip whole epochs.
        """
        height = self.block_count()
        if height <= self.epoch_margin:
            return
        target = (height - self.epoch_margin) // self.ctx.epoch_length
        directory = self.ctx.metrics_dir / "epochs"
        directory.mkdir(parents=True, exist_ok=True)
        while self._last_epoch < target:
            self._last_epoch += 1
            self._sample_one_epoch(self._last_epoch, height, directory)

    def _sample_one_epoch(self, epoch: int, height: int, directory) -> None:
        self.log.info("epoch %d closed and buried (height %d): sampling", epoch, height)
        # weightverifyweights reports only the LAST epoch the node verified,
        # so this is the only moment it can speak about this one.
        verify = self.call("weightverifyweights", quiet=True)
        with (directory / "verify_epochs.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({"epoch_requested": epoch, "height": height,
                                     "verify": verify}) + "\n")
        # Per-node state: a fork that heals before the end of the run leaves no
        # other trace, node_state.csv being a final snapshot.
        for node in self.ctx.all_nodes():
            node_height = self.call("getblockcount", node_id=node, quiet=True)
            best = self.call("getbestblockhash", node_id=node, quiet=True)
            peers = self.call("getpeerinfo", node_id=node, quiet=True)
            self.csv_append(
                "epochs/node_state_epochs.csv",
                [epoch, height, node, node_height if node_height is not None else "n/d",
                 best or "n/d", len(peers) if isinstance(peers, list) else 0],
                header=["epoch", "height_admin", "host", "height", "besthash", "peers"])
        if self.ctx.treasury:
            balances = self.call("getaddressbalances", [self.ctx.treasury], quiet=True)
            qty = ""
            if isinstance(balances, list) and balances:
                qty = balances[0].get("qty", "")
            self.csv_append("epochs/treasury_epochs.csv", [epoch, height, qty],
                            header=["epoch", "height", "treasury_balance_gas"])

    # -- teardown -----------------------------------------------------------
    def teardown(self) -> None:
        """The final snapshot: the primary source of every metric.

        Far more reliable than parsing debug.log, because listblocks reports
        the proposer of each height directly.
        """
        height = self.block_count()
        if height < 0:
            self.log.error("no RPC at teardown: the final snapshot was not taken")
            return
        self.log.info("final snapshot at height=%d", height)
        (self.ctx.metrics_dir).mkdir(parents=True, exist_ok=True)
        (self.ctx.metrics_dir / "final_height.txt").write_text("%d\n" % height,
                                                               encoding="utf-8")
        self.write_json("blocks.json", self.call("listblocks", ["1-%d" % max(height, 1)]) or [])
        self.write_json("weights.json",
                        self.call("liststreamitems", ["wpoa-weights", False, 100000]) or [])
        self.write_json("esg.json",
                        self.call("liststreamitems", ["weight-engine-esg", False, 10000]) or [])
        self.write_json("membership.json",
                        self.call("liststreamitems",
                                  ["weight-engine-membership", False, 10000]) or [])
        self.write_json("malus.json",
                        self.call("liststreamitems",
                                  ["wpoa-weights-malus", False, 10000]) or [])
        self.write_json("verify.json", self.call("weightverifyweights") or {})
        self.write_json("admin_getinfo.json", self.call("getinfo") or {})
        self.write_json("permissions_mine.json", self.call("listpermissions", ["mine"]) or [])
        self.write_json("allweights.json", self.call("getallweights") or {})
        if self.ctx.treasury:
            self.write_json("treasury_balance.json",
                            self.call("getaddressbalances", [self.ctx.treasury]) or [])
        self._node_state(height)

    def _node_state(self, height: int) -> None:
        """Per-node height and hash at a COMMON buried height.

        Using each node's own tip-6 would make nodes at different heights
        compare different blocks by construction, and an ordinary propagation
        delay would read as a fork.
        """
        reference = max(1, height - 6)
        header = ["host", "height", "besthash", "hash_a_%d" % reference, "peers", "balance"]
        for node in self.ctx.all_nodes():
            node_height = self.call("getblockcount", node_id=node, quiet=True)
            best = self.call("getbestblockhash", node_id=node, quiet=True)
            deep = self.call("getblockhash", [reference], node_id=node, quiet=True)
            peers = self.call("getpeerinfo", node_id=node, quiet=True)
            balance = self.call("getbalance", node_id=node, quiet=True)
            self.csv_append("node_state.csv",
                            [node, node_height if node_height is not None else "n/d",
                             best or "n/d", deep or "n/d",
                             len(peers) if isinstance(peers, list) else 0,
                             balance if balance is not None else ""],
                            header=header)
