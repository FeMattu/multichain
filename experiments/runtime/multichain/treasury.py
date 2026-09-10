"""The reconciliation treasury address, and why it needs machinery at all.

``weight-treasury-address`` is a hash-enforced chain parameter: it has to be in
``params.dat`` *before* the genesis. But the admin's own address is only born
*with* the genesis. That circularity is broken by pinning the address space —
``address-pubkeyhash-version`` and its three companions are random per chain by
default but editable in ``params.dat``, so an address generated on any chain
that pins the same four constants stays valid on every other chain that pins
them. One key pair is therefore generated once, on a throwaway chain, and
reused by every experiment.

**Only the address is needed at run time.** The admin imports it with
``importaddress`` (watch-only), never ``importprivkey``: it sees the
reconciled balance without those funds entering the spendable balance that
funds the GAS refills. Nothing in the harness ever spends from the treasury,
so the private key is not part of the versioned configuration — the shipped
``configs/treasury.json`` carries the address alone. ``--with-key`` regenerates
a full pair into a file that ``.gitignore`` excludes, for the rare case where
someone wants to sweep the treasury by hand.
"""

from __future__ import annotations

import json
import logging
import os
import random
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

from ...chain_params import ChainParams
from ...exit_codes import RuntimeFailure

LOG = logging.getLogger("experiments.runtime.multichain.treasury")

PINNED_KEYS = [
    ("address-pubkeyhash-version", "ADDRESS_PUBKEYHASH_VERSION"),
    ("address-scripthash-version", "ADDRESS_SCRIPTHASH_VERSION"),
    ("private-key-version", "PRIVATE_KEY_VERSION"),
    ("address-checksum-value", "ADDRESS_CHECKSUM_VALUE"),
]


@dataclass
class Treasury:
    address: str
    source: str
    pinned: dict

    def as_dict(self) -> dict:
        return {"address": self.address, "source": self.source, "pinned": self.pinned}


def load(path: Path | str) -> Treasury | None:
    """Read a treasury descriptor, if one exists."""
    path = Path(path)
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    address = data.get("address", "")
    if not address:
        return None
    return Treasury(
        address=address,
        source=str(path),
        pinned={key: data.get(key, "") for _, key in
                (("", "address_pubkeyhash_version"), ("", "address_checksum_value"))},
    )


def check_compatible(treasury: Treasury, chain_params: ChainParams) -> list[str]:
    """Warn when the chain no longer pins the address space the treasury needs.

    Silence here would be expensive: the address would simply not validate on
    the new chain, ``weight-treasury-address`` would be rejected or, worse,
    accepted and unspendable, and R_k would be zero for the whole campaign
    with no visible error.
    """
    warnings = []
    expected = treasury.pinned.get("address_pubkeyhash_version")
    actual = chain_params.get("ADDRESS_PUBKEYHASH_VERSION")
    if expected and actual and expected != actual:
        warnings.append(
            "treasury %s was generated with address-pubkeyhash-version %s but the chain "
            "parameters pin %s; the address will not validate and R_k would stay zero"
            % (treasury.address, expected, actual)
        )
    for name, key in PINNED_KEYS:
        if not chain_params.get(key):
            warnings.append(
                "chain parameters do not pin %s, so a treasury address is not portable "
                "between chains" % name
            )
    return warnings


def generate(util: str, daemon: str, cli: str, chain_params: ChainParams,
             out_path: Path, *, with_key: bool = False, force: bool = False) -> Treasury:
    """Create a key pair on a throwaway chain and record the address.

    The daemon is started on a random high port pair so a generation run never
    collides with a live experiment.
    """
    out_path = Path(out_path)
    if out_path.is_file() and not force:
        existing = load(out_path)
        if existing:
            LOG.info("treasury already present: %s (%s)", existing.address, out_path)
            return existing

    workdir = Path(tempfile.mkdtemp(prefix="poesia-treasury-"))
    chain = "tsygen"
    port = random.randint(30000, 49000)
    rpc_port = port + 1
    try:
        _run([util, "create", chain, "-datadir=%s" % workdir], "create the throwaway chain")
        params_path = workdir / chain / "params.dat"
        _pin_address_space(params_path, chain_params)
        _run([daemon, chain, "-datadir=%s" % workdir, "-port=%d" % port,
              "-rpcport=%d" % rpc_port, "-daemon"], "start the throwaway daemon", check=False)
        if not _wait_cli(cli, chain, workdir, rpc_port, timeout_s=60):
            raise RuntimeFailure(
                "the throwaway chain did not come up, so no treasury key pair could be "
                "generated (see %s)" % workdir
            )
        raw = _run([cli, chain, "-datadir=%s" % workdir, "-rpcport=%d" % rpc_port,
                    "createkeypairs", "1"], "create the key pair").stdout
        pair = json.loads(raw[raw.index("["):])[0]
        _run([cli, chain, "-datadir=%s" % workdir, "-rpcport=%d" % rpc_port, "stop"],
             "stop the throwaway daemon", check=False)
        time.sleep(2)
    finally:
        shutil.rmtree(workdir, ignore_errors=True)

    document = {
        "address": pair["address"],
        "address_pubkeyhash_version": chain_params.get("ADDRESS_PUBKEYHASH_VERSION", ""),
        "address_checksum_value": chain_params.get("ADDRESS_CHECKSUM_VALUE", ""),
        "note": (
            "Reconciliation treasury address (R_k). Valid on any chain pinning the same "
            "address-space constants. The private key is deliberately NOT stored here: the "
            "admin imports this address watch-only and nothing in the harness spends from "
            "it. Regenerate with 'experiments.cli multichain treasury --force'."
        ),
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    LOG.info("treasury address %s written to %s", pair["address"], out_path)

    if with_key:
        key_path = out_path.with_name(out_path.stem + ".key.json")
        key_path.write_text(
            json.dumps({"address": pair["address"], "privkey": pair["privkey"],
                        "pubkey": pair["pubkey"],
                        "note": "NOT versioned; see .gitignore"}, indent=2) + "\n",
            encoding="utf-8",
        )
        os.chmod(key_path, 0o600)
        LOG.warning("private key written to %s - it is excluded by .gitignore", key_path)

    return Treasury(address=pair["address"], source=str(out_path),
                    pinned={"address_pubkeyhash_version": document["address_pubkeyhash_version"],
                            "address_checksum_value": document["address_checksum_value"]})


def _pin_address_space(params_path: Path, chain_params: ChainParams) -> None:
    import re

    text = params_path.read_text(encoding="utf-8")
    for name, key in PINNED_KEYS:
        value = chain_params.get(key)
        if not value:
            continue
        text = re.sub(
            r"^(%s\s*=\s*)[0-9a-fA-F]+" % re.escape(name), r"\g<1>%s" % value,
            text, flags=re.M,
        )
    params_path.write_text(text, encoding="utf-8")


def _run(argv: list[str], what: str, *, check: bool = True) -> subprocess.CompletedProcess:
    proc = subprocess.run([str(a) for a in argv], capture_output=True, text=True, timeout=180)
    if check and proc.returncode != 0:
        raise RuntimeFailure(
            "could not %s (rc=%d): %s" % (what, proc.returncode,
                                          (proc.stderr or proc.stdout).strip()[:400])
        )
    return proc


def _wait_cli(cli: str, chain: str, datadir: Path, rpc_port: int, *, timeout_s: float) -> bool:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        proc = subprocess.run(
            [cli, chain, "-datadir=%s" % datadir, "-rpcport=%d" % rpc_port, "getinfo"],
            capture_output=True, text=True,
        )
        if proc.returncode == 0:
            return True
        time.sleep(1)
    return False
