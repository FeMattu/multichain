"""The Certification Authority: the only writer of ESG scores.

Ported from `role_ca.sh`. All the work happens in `setup`: the CA publishes
one certified ESG score per miner and per company on `weight-engine-esg`,
then the loop only re-checks that the records landed.

Two properties of the original are preserved exactly.

**The role is a permission, not a status.** It is carried by the custom
`high1` permission, delegated by the admin and revocable. Being an
administrator is NOT enough to certify (weight-engine.md 6.4): an ESG score is
an attestation of trust that no third party can verify cryptographically, and
restricting who may assert it is the only defence there is.

**The score of a host does not depend on how many CAs there are.** Each CA
takes a slice of the targets by rotation, but the counter that seeds the score
walks every target including the ones this CA skips. The same run with one,
two or three CAs produces the same scores.
"""

from __future__ import annotations

import random

from .base import RoleController


class CaController(RoleController):
    role = "ca"

    def __init__(self, context):
        super().__init__(context)
        w = context.workload
        self.index = int(w.get("ca_index", 1))
        self.count = max(1, int(w.get("ca_count", 1)))
        self.published: dict = {}
        self._done = False

    def setup(self) -> None:
        if not self.wait_rpc(900):
            raise RuntimeError("this CA's daemon never answered RPC")
        own = self.publish_own_address()
        self.log.info("CA address: %s (slice %d of %d)", own, self.index, self.count)
        if not self.wait_stream("weight-engine-esg", 900):
            self.log.error("weight-engine-esg never appeared: no ESG can be "
                           "published, and every weight will stay zero")
            return
        self._certify_all()
        self._done = True

    def _certify_all(self) -> None:
        targets = list(self.ctx.miners) + list(self.ctx.companies)
        for position, node in enumerate(targets, start=1):
            # The counter is GLOBAL: it seeds the score, so keeping it global
            # makes a host's ESG independent of the number of CAs.
            if (position - 1) % self.count != (self.index - 1):
                continue
            address = self.address_of(node)
            if not address:
                self.log.warning("no address for %s: ESG skipped", node)
                continue
            score = self._score(position)
            attempts = 5
            for attempt in range(1, attempts + 1):
                # The last attempt is not quiet: "attempt 5 failed for m1"
                # says nothing, and the RPC error is the whole diagnosis -
                # a missing stream, a missing high1, or no GAS to pay the
                # relay fee all look identical from here.
                quiet = attempt < attempts
                if self.call("weightsetesg", [address, score],
                             quiet=quiet) is not None:
                    self.log.info("ESG certified: %s (%s) = %.2f", node, address, score)
                    self.csv_append("esg_scores.csv", [node, address, score])
                    self.published[node] = score
                    break
                self.log.warning("attempt %d of %d failed for %s",
                                 attempt, attempts, node)
                self._sleep(10.0)
            else:
                self.log.error("ESG NOT published for %s", node)
        self.log.info("ESG certification complete: %d scores", len(self.published))

    def _score(self, position: int) -> float:
        """Uniform on (0, 100), endpoints excluded.

        Def. 6.1 requires ESG_i > 0 and the positivity of the weight depends
        on it, so the draw is clamped rather than allowed to reach zero.
        """
        generator = random.Random(self.ctx.seed + position)
        value = min(0.999, max(0.001, generator.random()))
        return round(value * 100, 2)

    def loop(self, tick: int) -> None:
        """Re-check, occasionally, that the ESG records are on chain.

        The bash original exited after publishing. It did so inside a
        simulation where a publish that returned a txid was certain to
        confirm; here a record can still be lost to a reorg, and a CA that had
        already exited would never notice.
        """
        del tick
        if not self._done or not self.published:
            return
        if self.tick_count % 12 != 0:
            return
        items = self.call("liststreamitems", ["weight-engine-esg", False, 1000],
                          quiet=True)
        if not isinstance(items, list):
            return
        confirmed = sum(1 for item in items if int(item.get("confirmations", 0)) > 0)
        if confirmed < len(self.published):
            self.log.warning("only %d of %d ESG records are confirmed",
                             confirmed, len(self.published))

    def teardown(self) -> None:
        self.log.info("CA finished: %d ESG scores published", len(self.published))
