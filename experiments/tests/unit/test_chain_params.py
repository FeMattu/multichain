"""Chain parameters: the hash-enforced values that define the chain."""

from __future__ import annotations

import pytest

from experiments.chain_params import ChainParams, read_params_dat
from experiments.exit_codes import ConfigError
from experiments.paths import CONFIG_ROOT

FILES = sorted((CONFIG_ROOT / "chain-params").glob("*.dat"))


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.stem)
def test_every_shipped_file_parses(path):
    params = ChainParams.load(path)
    assert params.target_block_time > 0
    assert params.epoch_length > 0
    assert params.dump_function in ("none", "sqrt", "log")


def test_the_one_axis_variants_differ_by_exactly_one_key():
    base = ChainParams.load(CONFIG_ROOT / "chain-params" / "tbt10s-sqrt.dat").values
    for other, expected in (("tbt10s-none.dat", "WPOA_DUMPFUNCTION"),
                            ("tbt10s-log.dat", "WPOA_DUMPFUNCTION"),
                            ("tbt30s-sqrt.dat", "TARGET_BLOCK_TIME")):
        values = ChainParams.load(CONFIG_ROOT / "chain-params" / other).values
        differing = {k for k in set(base) | set(values) if base.get(k) != values.get(k)}
        assert differing == {expected}, (other, differing)


def test_the_long_epoch_variant_is_honestly_not_one_axis():
    """params-tbt10s-log.dat moved four knobs at once; the name says so."""
    base = ChainParams.load(CONFIG_ROOT / "chain-params" / "tbt10s-sqrt.dat").values
    values = ChainParams.load(CONFIG_ROOT / "chain-params" / "tbt10s-log-epoch100.dat").values
    differing = {k for k in set(base) | set(values) if base.get(k) != values.get(k)}
    assert differing == {"WPOA_DUMPFUNCTION", "WEIGHT_EPOCH_LENGTH",
                         "MEASURE_EPOCHS", "WPOA_SORTITION_LAMBDA"}


def test_util_flags_carry_the_master_switch_and_the_engine():
    flags = ChainParams.load(CONFIG_ROOT / "chain-params" / "tbt10s-sqrt.dat").util_flags()
    assert "-enablewpoa=1" in flags
    assert "-enableweightengine=1" in flags
    assert any(f.startswith("-dumpfunction=") for f in flags)


def test_params_dat_edits_resolve_setup_first_blocks():
    """Leaving the literal 'auto' in params.dat would make setup unparseable."""
    params = ChainParams.load(CONFIG_ROOT / "chain-params" / "tbt10s-sqrt.dat")
    edits = dict(params.params_dat_edits(setup_first_blocks=64))
    assert edits["setup-first-blocks"] == "64"
    assert edits["mining-diversity"] == "0"


def test_measure_epochs_is_not_a_chain_parameter():
    params = ChainParams.load(CONFIG_ROOT / "chain-params" / "tbt10s-sqrt.dat")
    names = [name for name, _ in params.params_dat_edits(setup_first_blocks=64)]
    assert "measure-epochs" not in names
    assert not any("MEASURE" in flag.upper() for flag in params.util_flags())


def test_auto_setup_applies_the_documented_formula():
    params = ChainParams.load(CONFIG_ROOT / "chain-params" / "tbt10s-sqrt.dat")
    # ceil(340/10) + 12 + 6 + 12 = 64, above the floor of 60.
    assert params.setup_minimum(traffic_start_s=340) == 64
    assert params.setup_first_blocks(traffic_start_s=340) == 64


def test_auto_setup_respects_the_absolute_floor():
    params = ChainParams.load(CONFIG_ROOT / "chain-params" / "smoke.dat")
    assert params.setup_first_blocks(traffic_start_s=90) >= 60


def test_a_malformed_line_is_a_config_error(tmp_path):
    path = tmp_path / "bad.dat"
    path.write_text("TARGET_BLOCK_TIME 10\n", encoding="utf-8")
    with pytest.raises(ConfigError) as caught:
        ChainParams.load(path)
    assert "KEY=VALUE" in str(caught.value)


def test_missing_required_keys_are_reported_together(tmp_path):
    path = tmp_path / "short.dat"
    path.write_text("TARGET_BLOCK_TIME=10\n", encoding="utf-8")
    with pytest.raises(ConfigError) as caught:
        ChainParams.load(path)
    assert "missing required keys" in str(caught.value)


def test_read_params_dat_parses_a_generated_file(tmp_path):
    path = tmp_path / "params.dat"
    path.write_text(
        "# comment\nchain-name = mychain\ntarget-block-time = 15    # seconds\n"
        "setup-first-blocks = 64\n", encoding="utf-8")
    values = read_params_dat(path)
    assert values["chain-name"] == "mychain"
    assert values["target-block-time"] == "15"
    assert values["setup-first-blocks"] == "64"


def test_read_params_dat_on_a_missing_file_is_empty_not_an_error(tmp_path):
    assert read_params_dat(tmp_path / "absent.dat") == {}
