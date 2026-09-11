"""The emulation-native per-epoch summary."""

from __future__ import annotations

import csv

from experiments.analysis import summary_per_epoca as spe


def _write(path, columns, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _run(tmp_path, blocks):
    _write(tmp_path / "raw" / "observations" / "explorer_blocks.csv",
           ["run_id", "scenario", "height", "block_time", "observed_wallclock",
            "miner_host", "proposer_weight"], blocks)
    return tmp_path


def test_shares_and_deviation_come_from_the_weights_in_force(tmp_path):
    blocks = []
    # epoch(h) = h // L + 1, so heights 4..7 are exactly epoch 2.
    for height in range(4, 8):
        host = "m1" if height % 2 else "m2"
        blocks.append({"run_id": "r", "scenario": "s", "height": height,
                       "block_time": 1000 + height * 5,
                       "observed_wallclock": "2026-01-01T00:00:0%d+00:00" % height,
                       "miner_host": host,
                       "proposer_weight": 300 if host == "m1" else 100})
    result = spe.build(_run(tmp_path, blocks), epoch_length=4)

    assert len(result["epochs"]) == 1
    epoch = result["epochs"][0]
    assert epoch["block_count"] == 4
    assert epoch["average_block_time_seconds"] == 5.0

    shares = {row["node_id"]: row for row in result["validators"]}
    assert shares["m1"]["expected_weight_share"] == 0.75
    assert shares["m1"]["observed_block_share"] == 0.5
    assert shares["m1"]["deviation_absolute"] == -0.25


def test_an_absent_number_says_why_instead_of_being_blank(tmp_path):
    """The brief's rule: `dato non disponibile: <motivo>`, never a silent gap."""
    blocks = [{"run_id": "r", "scenario": "s", "height": 1, "block_time": 10,
               "observed_wallclock": "2026-01-01T00:00:01+00:00",
               "miner_host": "m1", "proposer_weight": 100}]
    result = spe.build(_run(tmp_path, blocks), epoch_length=4)
    epoch = result["epochs"][0]

    assert epoch["chi_square_statistic"] == spe.UNAVAILABLE
    assert "fewer than two validators" in epoch["chi_square_note"]
    assert "-debug=wpoa" in epoch["sortition_margin_note"]
    assert spe.UNAVAILABLE in epoch["sortition_margin_mean"]


def test_a_chi_square_too_small_to_read_says_so(tmp_path):
    """Computed, reported, and marked uninterpretable - all three."""
    blocks = [{"run_id": "r", "scenario": "s", "height": h, "block_time": 10 + h,
               "observed_wallclock": "2026-01-01T00:00:0%d+00:00" % h,
               "miner_host": "m1" if h < 6 else "m2",
               "proposer_weight": 100} for h in range(4, 8)]
    epoch = spe.build(_run(tmp_path, blocks), epoch_length=4)["epochs"][0]
    assert epoch["chi_square_statistic"] != spe.UNAVAILABLE
    assert "smallest expected count" in epoch["chi_square_note"]


def test_the_report_declares_the_temporal_model(tmp_path):
    blocks = [{"run_id": "r", "scenario": "s", "height": 1, "block_time": 10,
               "observed_wallclock": "2026-01-01T00:00:01+00:00",
               "miner_host": "m1", "proposer_weight": 100}]
    text = spe.render(spe.build(_run(tmp_path, blocks), epoch_length=4))
    assert "wall-clock" in text
    assert "no simulated" in text
