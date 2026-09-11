"""The miner: cluster head, validator, and source of the reconciliation R_k.

Ported from `role_miner.sh`. `setup` registers the node as the head of its own
cluster on `weight-engine-membership`; `loop` returns a fraction of the GAS
collected in fees to the treasury once per epoch.

That transfer is not bookkeeping. Derived from confirmed blocks and never
declared, it constitutes R_k (Def. 6.7) and therefore the compliance rate
rho_k that feeds back into the next epoch's weight (Def. 6.8-6.9). The rate
differs per miner so the rho_k diverge and the feedback is observable at all.
"""

from __future__ import annotations

from .base import RoleController


class MinerController(RoleController):
    role = "miner"

    def __init__(self, context):
        super().__init__(context)
        w = context.workload
        self.rate = float(w.get("reconcile_rate", 0.6))
        self.reserve = float(w.get("reconcile_reserve_gas", 2))
        self.min_transfer = float(w.get("reconcile_min_gas", 0.1))
        self._last_epoch = -1
        self._registered = False

    def setup(self) -> None:
        if not self.wait_rpc(900):
            raise RuntimeError("this miner's daemon never answered RPC")
        own = self.publish_own_address()
        self.log.info("miner address: %s (reconcile rate %.2f)", own, self.rate)
        if not self.wait_stream("weight-engine-membership", 900):
            self.log.error("weight-engine-membership never appeared: "
                           "this cluster will carry no weight")
            return
        # A miner registers with its OWN address: it is the head of its cluster.
        for attempt in range(1, 6):
            if self.call("weightregistermembership", [own], quiet=True) is not None:
                self.log.info("registered as cluster head: %s", own)
                self.csv_append("membership.csv", [self.ctx.node_id, own, own])
                self._registered = True
                return
            self.log.warning("membership attempt %d failed", attempt)
            self._sleep(10.0)
        self.log.error("membership not registered: this cluster will carry no weight")

    def loop(self, tick: int) -> None:
        del tick
        height = self.block_count()
        if height < 0:
            return
        epoch = self.epoch_of(height)
        if epoch == self._last_epoch:
            return
        self._last_epoch = epoch
        self._reconcile(height, epoch)

    def _reconcile(self, height: int, epoch: int) -> None:
        if not self.ctx.treasury:
            return
        balance = self.call("getbalance", quiet=True)
        try:
            balance = float(balance)
        except (TypeError, ValueError):
            return
        amount = round(max(0.0, (balance - self.reserve) * self.rate), 4)
        if amount < self.min_transfer:
            self.csv_append("reconciliation.csv",
                            [height, epoch, self.ctx.node_id, balance, 0],
                            header=["height", "epoch", "miner", "balance", "sent"])
            return
        if self.call("send", [self.ctx.treasury, amount]) is not None:
            self.log.info("epoch %d: reconciled %.4f GAS out of %.4f (rate %.2f)",
                          epoch, amount, balance, self.rate)
            self.csv_append("reconciliation.csv",
                            [height, epoch, self.ctx.node_id, balance, amount],
                            header=["height", "epoch", "miner", "balance", "sent"])
        else:
            self.csv_append("reconciliation.csv",
                            [height, epoch, self.ctx.node_id, balance, 0],
                            header=["height", "epoch", "miner", "balance", "sent"])

    def teardown(self) -> None:
        """Record this miner's own view of its weight.

        getlocalweight is the node's own answer; the admin's getallweights is
        the registry's. Keeping both lets a disagreement between them be seen
        rather than averaged away.
        """
        local = self.call("getlocalweight", quiet=True)
        self.csv_append("miner_final_weight.csv",
                        [self.ctx.node_id, self.address_of(self.ctx.node_id),
                         local if local is not None else "",
                         int(self._registered)],
                        header=["host", "address", "local_weight", "registered"])
