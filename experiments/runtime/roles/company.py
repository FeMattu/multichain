"""The company: a client that generates the supply-chain workload.

Ported from `role_company.sh`. `setup` joins a miner's cluster on
`weight-engine-membership`; `loop` publishes items on the application stream.

Each publication does two things, and the second is the reason the workload
exists at all: it pays ~0.2 GAS of fee to the miner that includes it, and it
increments tau_i, the epoch's activity counter that the contribution
c_i = ESG_i * tau_i / kappa - and therefore the cluster's weight - depends on.

The interval differs per company so the tau_i, and with them the W_k, diverge.
Where the bash original hardcoded the interval, this reads it from the
descriptor and adds optional jitter and bursts.
"""

from __future__ import annotations

from .base import RoleController


class CompanyController(RoleController):
    role = "company"

    def __init__(self, context):
        super().__init__(context)
        w = context.workload
        self.interval = float(w.get("tx_interval_seconds", 12))
        self.jitter = float(w.get("tx_interval_jitter_seconds", 0))
        self.burst_probability = float(w.get("burst_probability", 0.0))
        self.burst_size = int(w.get("burst_size", 1))
        self.tx_type = w.get("tx_type", "publish")
        self.amount_range = w.get("tx_amount_range", [0.01, 1.0])
        self.sequence = 0
        self._next_at = 0.0
        self._ready = False

    def setup(self) -> None:
        if not self.wait_rpc(900):
            raise RuntimeError("this company's daemon never answered RPC")
        own = self.publish_own_address()
        self.log.info("company address: %s (cluster %s, one item every %.1fs)",
                      own, self.ctx.cluster, self.interval)
        if not self.wait_stream("weight-engine-membership", 900):
            self.log.error("weight-engine-membership never appeared: "
                           "this company's activity will count for nobody")
            return
        miner_address = self.address_of(self.ctx.cluster)
        if not miner_address:
            self.log.error("no address for cluster head %r: cannot join",
                           self.ctx.cluster)
            return
        # Self-attested: the reader accepts it only because the signer matches
        # node_address, so nobody can declare somebody else's membership.
        for attempt in range(1, 6):
            if self.call("weightregistermembership", [miner_address], quiet=True) is not None:
                self.log.info("joined cluster %s (%s)", self.ctx.cluster, miner_address)
                self.csv_append("membership.csv",
                                [self.ctx.node_id, own, miner_address])
                break
            self.log.warning("membership attempt %d failed", attempt)
            self._sleep(10.0)
        else:
            self.log.error("membership not registered")
        self.wait_stream(self.ctx.stream, 900)
        self._ready = True

    def loop(self, tick: int) -> None:
        del tick
        if not self._ready:
            return
        now = self._now()
        if now < self._next_at:
            return
        count = 1
        if self.burst_probability > 0 and self.rng.random() < self.burst_probability:
            count = max(1, self.burst_size)
            self.log.info("burst of %d items", count)
        for _ in range(count):
            self._publish_one()
        self._next_at = now + self._interval()

    def _now(self) -> float:
        import time

        return time.monotonic()

    def _interval(self) -> float:
        if self.jitter <= 0:
            return self.interval
        return max(0.5, self.interval + self.rng.uniform(-self.jitter, self.jitter))

    def _publish_one(self) -> None:
        self.sequence += 1
        height = self.block_count()
        own = self.address_of(self.ctx.node_id)
        key = "LOTTO-%s-%05d" % (self.ctx.node_id, self.sequence)
        payload = self.hexlify({"host": self.ctx.node_id, "seq": self.sequence,
                                "height": height})
        result = self.call("publishfrom", [own, self.ctx.stream, key, payload],
                           quiet=True)
        if isinstance(result, str) and len(result) == 64:
            self.csv_append("traffic.csv",
                            [height, self.ctx.node_id, self.sequence, result],
                            header=["height", "host", "seq", "txid_or_error"])
        else:
            self.csv_append("traffic.csv",
                            [height, self.ctx.node_id, self.sequence, "ERRORE"],
                            header=["height", "host", "seq", "txid_or_error"])
            self.log.warning("publish failed (seq %d)", self.sequence)

    def teardown(self) -> None:
        self.log.info("published %d items in total", self.sequence)
        self.csv_append("company_final.csv",
                        [self.ctx.node_id, self.ctx.cluster, self.sequence],
                        header=["host", "cluster", "items_published"])
