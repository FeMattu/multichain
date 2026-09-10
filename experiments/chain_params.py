"""Reading and applying the ``KEY=VALUE`` chain-parameter files.

The format is deliberately the historical one — sourceable from bash, one
uppercase key per line — because the same file has to be readable by the shell
helpers and by Python, and because every archived campaign is described by one.

Two groups live in the file and they behave differently:

* chain parameters, which ``multichain-util create`` writes into ``params.dat``
  where they become hash-enforced and inherited by every joining node;
* ``MEASURE_EPOCHS``, which is not a chain parameter at all and only feeds the
  automatic run duration.

:func:`ChainParams.util_flags` and :func:`ChainParams.params_dat_edits` keep
that distinction explicit rather than relying on the caller to remember it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from .exit_codes import ConfigError

LINE_RE = re.compile(r"^\s*([A-Z][A-Z0-9_]*)\s*=\s*(.*?)\s*$")

#: Keys passed to ``multichain-util create`` as flags, in creation order.
#: ``enablewpoa`` is the master switch: it turns on weights, selection, VRF,
#: RANDAO and sortition in one go (see src/wpoa/docs/protocol-parameters.md).
UTIL_FLAGS = [
    ("enablewpoa", None, "1"),
    ("wpoasortitiondelta", "WPOA_SORTITION_DELTA", None),
    ("wpoasortitionlambda", "WPOA_SORTITION_LAMBDA", None),
    ("wpoarandaolookback", "WPOA_RANDAO_LOOKBACK", None),
    ("dumpfunction", "WPOA_DUMPFUNCTION", None),
    ("enablewpoamalus", "ENABLE_WPOA_MALUS", None),
    ("enableweightengine", None, "1"),
    ("weightepochlength", "WEIGHT_EPOCH_LENGTH", None),
    ("weightkappa", "WEIGHT_KAPPA", None),
    ("weightalpha", "WEIGHT_ALPHA", None),
    ("weightlambda", "WEIGHT_LAMBDA", None),
]

#: Keys edited into ``params.dat`` after creation, as ``params.dat`` name.
PARAMS_DAT_EDITS = [
    ("target-block-time", "TARGET_BLOCK_TIME"),
    ("setup-first-blocks", "SETUP_FIRST_BLOCKS"),
    ("mine-empty-rounds", "MINE_EMPTY_ROUNDS"),
    ("mining-diversity", "MINING_DIVERSITY"),
    ("address-pubkeyhash-version", "ADDRESS_PUBKEYHASH_VERSION"),
    ("address-scripthash-version", "ADDRESS_SCRIPTHASH_VERSION"),
    ("private-key-version", "PRIVATE_KEY_VERSION"),
    ("address-checksum-value", "ADDRESS_CHECKSUM_VALUE"),
    ("native-currency-multiple", "NATIVE_CURRENCY_MULTIPLE"),
    ("first-block-reward", "FIRST_BLOCK_REWARD"),
    ("initial-block-reward", "INITIAL_BLOCK_REWARD"),
    ("minimum-relay-fee", "MINIMUM_RELAY_FEE"),
]

#: Not a chain parameter. Kept out of both lists on purpose.
NON_CHAIN_KEYS = {"MEASURE_EPOCHS"}

REQUIRED = {
    "TARGET_BLOCK_TIME", "SETUP_FIRST_BLOCKS", "WEIGHT_EPOCH_LENGTH",
    "WPOA_DUMPFUNCTION", "WPOA_SORTITION_DELTA",
}


@dataclass
class ChainParams:
    """Parsed chain-parameter file."""

    path: Path
    values: dict[str, str]

    @classmethod
    def load(cls, path: Path | str) -> "ChainParams":
        path = Path(path)
        if not path.is_file():
            raise ConfigError("chain parameter file not found: %s" % path)
        values: dict[str, str] = {}
        for lineno, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            stripped = raw.split("#", 1)[0]
            if not stripped.strip():
                continue
            match = LINE_RE.match(stripped)
            if not match:
                raise ConfigError("%s:%d is not KEY=VALUE: %r" % (path, lineno, raw.strip()))
            values[match.group(1)] = match.group(2)
        missing = REQUIRED - set(values)
        if missing:
            raise ConfigError(
                "%s is missing required keys: %s" % (path, ", ".join(sorted(missing)))
            )
        return cls(path=path, values=values)

    # -- typed accessors ----------------------------------------------------
    def get(self, key: str, default: str | None = None) -> str | None:
        return self.values.get(key, default)

    def int_(self, key: str, default: int | None = None) -> int:
        raw = self.values.get(key)
        if raw is None or raw == "":
            if default is None:
                raise ConfigError("%s: %s is not set" % (self.path, key))
            return default
        try:
            return int(raw)
        except ValueError as exc:
            raise ConfigError("%s: %s=%r is not an integer" % (self.path, key, raw)) from exc

    def float_(self, key: str, default: float | None = None) -> float:
        raw = self.values.get(key)
        if raw is None or raw == "":
            if default is None:
                raise ConfigError("%s: %s is not set" % (self.path, key))
            return default
        try:
            return float(raw)
        except ValueError as exc:
            raise ConfigError("%s: %s=%r is not a number" % (self.path, key, raw)) from exc

    @property
    def target_block_time(self) -> int:
        return self.int_("TARGET_BLOCK_TIME")

    @property
    def epoch_length(self) -> int:
        return self.int_("WEIGHT_EPOCH_LENGTH")

    @property
    def dump_function(self) -> str:
        return self.get("WPOA_DUMPFUNCTION", "none")

    @property
    def sortition_delta(self) -> float:
        return self.float_("WPOA_SORTITION_DELTA")

    @property
    def measure_epochs(self) -> int:
        return self.int_("MEASURE_EPOCHS", 16)

    @property
    def setup_first_blocks_raw(self) -> str:
        return self.get("SETUP_FIRST_BLOCKS", "auto")

    def setup_first_blocks(self, *, traffic_start_s: float) -> int:
        """Resolve ``SETUP_FIRST_BLOCKS``, honouring ``auto``.

        The native PoA phase must last long enough for membership and ESG to
        confirm, for the epoch holding them to be buried behind the stability
        margin, and for the first weights to be published. Below that the wPoA
        takes over on an empty weight map and the chain stops with
        ``cannot score (unsynced or unweighted)``.

            setup_min = ceil(traffic_start / tbt) + epoch_length + 6 + 12

        ``6`` is the weight engine's stability margin, ``12`` slack. A floor of
        60 blocks applies, as in the historical harness.
        """
        minimum = self.setup_minimum(traffic_start_s=traffic_start_s)
        raw = self.setup_first_blocks_raw
        if raw.strip().lower() == "auto":
            return max(minimum, 60)
        try:
            explicit = int(raw)
        except ValueError as exc:
            raise ConfigError(
                "%s: SETUP_FIRST_BLOCKS=%r is neither an integer nor 'auto'" % (self.path, raw)
            ) from exc
        if explicit < minimum:
            raise ConfigError(
                "%s: SETUP_FIRST_BLOCKS=%d is below the %d blocks this configuration needs "
                "(target-block-time %ds, epoch %d, traffic starts at %gs)"
                % (self.path, explicit, minimum, self.target_block_time,
                   self.epoch_length, traffic_start_s),
                hint="wPoA would take over before any weight is published and the chain would stall",
            )
        return explicit

    def setup_minimum(self, *, traffic_start_s: float) -> int:
        tbt = self.target_block_time
        return -(-int(traffic_start_s) // tbt) + self.epoch_length + 6 + 12

    # -- rendering ----------------------------------------------------------
    def util_flags(self) -> list[str]:
        """``multichain-util create`` flags derived from the file."""
        flags = []
        for flag, key, constant in UTIL_FLAGS:
            value = constant if key is None else self.values.get(key)
            if value in (None, ""):
                continue
            flags.append("-%s=%s" % (flag, value))
        return flags

    def params_dat_edits(self, *, setup_first_blocks: int) -> list[tuple[str, str]]:
        """``(params.dat key, value)`` pairs to write after creation.

        ``setup-first-blocks`` is passed in already resolved: leaving the
        literal string ``auto`` in ``params.dat`` would produce a chain whose
        setup length is unparseable.
        """
        edits = []
        for name, key in PARAMS_DAT_EDITS:
            value = str(setup_first_blocks) if key == "SETUP_FIRST_BLOCKS" else self.values.get(key)
            if value in (None, ""):
                continue
            edits.append((name, value))
        return edits

    def as_dict(self) -> dict[str, str]:
        return dict(self.values)


PARAMS_DAT_LINE_RE = re.compile(r"^([a-z0-9-]+)\s*=\s*(.*?)\s*(?:#.*)?$")


def read_params_dat(path: Path | str) -> dict[str, str]:
    """Read a generated ``params.dat`` into a dict.

    Used to re-read the *effective* configuration after
    ``multichain-util create``: the tool may raise ``setup-first-blocks`` to a
    floor derived at genesis, and a run that does not re-read it would shorten
    its own measurement window without saying so.
    """
    out: dict[str, str] = {}
    path = Path(path)
    if not path.is_file():
        return out
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line or line.lstrip().startswith("#"):
            continue
        match = PARAMS_DAT_LINE_RE.match(line.strip())
        if match:
            out[match.group(1)] = match.group(2)
    return out
