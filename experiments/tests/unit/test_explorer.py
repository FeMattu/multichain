"""The block explorer: gap-free walking, and noticing when the chain stops."""

from __future__ import annotations

from experiments.runtime.collectors.rpc_explorer import RpcExplorer


class FakeClient:
    """Answers getblockcount from a scripted sequence of tips."""

    def __init__(self, tips):
        self.tips = list(tips)
        self.calls = []

    def call(self, method, params=None):
        self.calls.append((method, params))
        if method == "getblockcount":
            return self.tips.pop(0) if self.tips else 0
        if method == "getblockhash":
            return "hash-%s" % (params or [0])[0]
        if method == "getblock":
            return {"height": 0, "hash": "h", "previousblockhash": "p",
                    "time": 0, "miner": "", "size": 0, "tx": []}
        return {}


def _explorer(tmp_path, tips, mode="backfill"):
    return RpcExplorer(run_id="r", scenario="s", run_root=tmp_path,
                       explorer_node="admin", clients={"admin": FakeClient(tips)},
                       keep_raw=False, mode=mode)


def test_a_tip_that_never_moves_is_reported(tmp_path, monkeypatch):
    """A frozen chain still yields contiguous heights and no measurement.

    Observed: the tip stood at 59 for the rest of a 600s run because the
    miner had marked height 60 "already proposed". Every block up to 59 was
    collected, contiguously, and not one of them was measurable.
    """
    explorer = _explorer(tmp_path, [59, 59, 59])
    clock = [1000.0]
    monkeypatch.setattr("experiments.runtime.collectors.rpc_explorer.time.monotonic",
                        lambda: clock[0])

    explorer.poll()                     # first sight of the tip
    for _ in range(2):
        clock[0] += 120.0
        explorer.poll()                 # ... and it has not moved since

    stall = explorer.longest_stall()
    assert stall["height"] == 59
    assert stall["seconds"] >= 240
    assert explorer.contiguity()["ok"], "a stalled chain has no gaps to find"


def test_a_moving_tip_reports_no_stall(tmp_path, monkeypatch):
    explorer = _explorer(tmp_path, [1, 2, 3])
    clock = [1000.0]
    monkeypatch.setattr("experiments.runtime.collectors.rpc_explorer.time.monotonic",
                        lambda: clock[0])
    for _ in range(3):
        clock[0] += 5.0
        explorer.poll()
    assert explorer.longest_stall()["seconds"] == 0


def test_a_live_collector_joins_at_the_tip(tmp_path):
    """`live` observes from now on; it does not invent a first sighting.

    A block mined before the collector existed has no first_seen to measure,
    so live mode records the tip and starts from there. `backfill` is the
    harness's own default, because a run owns the chain it created and wants
    every height of it.
    """
    explorer = _explorer(tmp_path, [40, 41], mode="live")
    explorer.poll()
    assert explorer.state.last_height == 40
    assert explorer.contiguity()["checked"] == 0, "history was not invented"


def test_a_restarted_collector_resumes_instead_of_replaying(tmp_path):
    """The index is the reason a restart neither duplicates nor skips."""
    first = _explorer(tmp_path, [3])
    first.poll()
    assert first.state.last_height == 3
    assert first.index_path.is_file()

    second = _explorer(tmp_path, [3])
    assert second.state.last_height == 3, "the index was not read back"
    assert second.resumed_from == 3
    produced = second.poll()
    assert produced["blocks"] == 0, "a resumed collector re-walked the chain"
