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


def _explorer(tmp_path, tips):
    return RpcExplorer(run_id="r", scenario="s", run_root=tmp_path,
                       explorer_node="admin", clients={"admin": FakeClient(tips)},
                       keep_raw=False)


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
