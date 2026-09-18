"""Creating the chain and running the ``multichaind`` processes.

Shared by ``bootstrap_network.py`` (which starts everything) and
``shutdown/stop_network.py`` (which stops it), so that the command line a node was
started with and the way it is asked to stop live in one place.

Nothing here knows about roles, traffic or analysis: it is the thin layer between the
profile and the binaries.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import signal
import socket
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import fabric as fabric_module
from config_loader import Profile

#: Lines of params.dat are ``key = value  # comment``. The comment is preserved on
#: rewrite: it carries the range and the meaning, and a params.dat stripped of them is
#: much harder to diff against a fresh one when something does not match.
_PARAM_LINE = re.compile(r"^([a-z0-9-]+)(\s*=\s*)(\S*)(.*)$")

#: The node prints one of these when its data directory is still locked by a daemon
#: that has not finished shutting down. Matched rather than guessed, because the two
#: spellings come from different layers (MultiChain's own check, and LevelDB's).
_LOCK_HELD = re.compile(
    r"(already running|Resource temporarily unavailable|Couldn't initialize permission database)",
    re.IGNORECASE,
)

#: A joining node prints the grant it is waiting for, and that line is the only place its
#: freshly generated address appears before it has an RPC port to be asked on.
_GRANT_HINT = re.compile(r"grant\s+([A-Za-z0-9]{25,40})\s+connect", re.IGNORECASE)

#: The seed was not serving when a peer tried to join — a sequencing fault, not a
#: permission one, and worth a different message.
_SEED_UNREACHABLE = re.compile(r"Couldn't connect to the seed node", re.IGNORECASE)


class NodeStartError(RuntimeError):
    """A daemon refused to start. Carries whatever it printed before dying."""


@dataclass
class NodeHandle:
    """One running (or startable) node."""

    node_id: str
    role: str
    datadir: Path
    port: int
    rpc_port: int
    stdout_path: Path
    address: Optional[str] = None
    pid: Optional[int] = None
    extra_args: List[str] = field(default_factory=list)


class NodeRunner:
    """Starts, stops and restarts the daemons of one run.

    The engine flags are applied here rather than by the caller, so that no code path can
    produce a node with a different consensus configuration from its peers.
    """

    def __init__(
        self,
        profile: Profile,
        repo_root: Path,
        chain_home: Path,
        fabric: Optional[object] = None,
    ) -> None:
        self.profile = profile
        self.repo_root = Path(repo_root)
        self.chain_home = Path(chain_home)
        # The regime this runner works in. Built from the profile when the caller has no
        # opinion, which is what keeps every entry point that only wants to stop a network
        # from having to know there are two regimes at all.
        self.fabric = fabric if fabric is not None else fabric_module.build(profile)
        bindir = self.repo_root / profile.runtime["bindir"]
        self.multichaind = bindir / "multichaind"
        self.multichain_util = bindir / "multichain-util"
        self.multichain_cli = bindir / "multichain-cli"
        self.treasury_address: Optional[str] = None

    #: Seconds to let LevelDB release its lock after the RPC port has closed. The port
    #: closes first, so a restart issued the instant it does lands on a held lock.
    LOCK_SETTLE_S = 2.0

    # -- preflight ---------------------------------------------------------------------

    def require_binaries(self) -> None:
        missing = [
            str(p)
            for p in (self.multichaind, self.multichain_util, self.multichain_cli)
            if not p.is_file() or not os.access(p, os.X_OK)
        ]
        if missing:
            raise NodeStartError(
                "missing or non-executable binaries: %s\nBuild them first:\n"
                "    ./docker/mcsim run mc-build" % ", ".join(missing)
            )
        probe = subprocess.run(
            [str(self.multichaind), "--version"],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if "MultiChain" not in (probe.stdout + probe.stderr):
            raise NodeStartError(
                "%s did not run. On the host this usually means the shared libraries are "
                "missing (the binaries are built against Ubuntu 22.04 + Boost 1.74); run "
                "the harness inside ./docker/mcsim.\n%s"
                % (self.multichaind, (probe.stderr or probe.stdout).strip()[:400])
            )

    # -- datadirs ----------------------------------------------------------------------

    def datadir(self, node_id: str) -> Path:
        return self.chain_home / node_id

    def prepare_datadirs(self) -> None:
        for node in self.profile.nodes:
            self.datadir(node.node_id).mkdir(parents=True, exist_ok=True)

    # -- chain creation ----------------------------------------------------------------

    def create_chain(self) -> Path:
        """``multichain-util create`` on the admin datadir, then rewrite ``params.dat``.

        The parameters are written into the file rather than passed as creation flags for
        one reason: the file is the thing that is hashed and inherited, so writing it
        directly makes what every node will run visible in one place and diffable.
        """
        admin_dir = self.datadir(self.profile.admin.node_id)
        admin_dir.mkdir(parents=True, exist_ok=True)
        result = subprocess.run(
            [
                str(self.multichain_util),
                "-datadir=%s" % admin_dir,
                "create",
                self.profile.chain_name,
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )
        params = admin_dir / self.profile.chain_name / "params.dat"
        if not params.is_file():
            raise NodeStartError(
                "multichain-util create produced no params.dat\n%s"
                % (result.stderr or result.stdout).strip()[:800]
            )
        return params

    def write_params(self, params_path: Path, overrides: Dict[str, str]) -> Dict[str, str]:
        """Apply ``overrides`` in place, and fail loudly on a key the file does not have.

        MultiChain **silently ignores** an unknown key in params.dat, so a typo would
        leave the default in force and the mistake would surface, if at all, as an
        inexplicable result several phases later. Every key written here must already
        exist in the generated file.
        """
        text = params_path.read_text(encoding="utf-8")
        seen: Dict[str, str] = {}
        out: List[str] = []
        for line in text.split("\n"):
            match = _PARAM_LINE.match(line)
            if match and match.group(1) in overrides:
                key = match.group(1)
                seen[key] = overrides[key]
                out.append("%s = %s%s" % (key, overrides[key], match.group(4)))
            else:
                out.append(line)
        missing = sorted(set(overrides) - set(seen))
        if missing:
            raise NodeStartError(
                "params.dat has no key(s) %s. This binary does not know them, so writing "
                "them would be silently ignored. Check the parameter catalogue against "
                "src/chainparams/paramlist.h." % ", ".join(missing)
            )
        params_path.write_text("\n".join(out), encoding="utf-8")
        return seen

    @staticmethod
    def read_params(params_path: Path) -> Dict[str, str]:
        """Parse a params.dat into ``{key: value}``.

        Used after genesis to read back what the node actually settled on —
        ``setup-first-blocks`` in particular is rewritten by the node itself before the
        hash is taken, so the configured value is not necessarily the effective one.
        """
        out: Dict[str, str] = {}
        if not params_path.is_file():
            return out
        for line in params_path.read_text(encoding="utf-8").split("\n"):
            match = _PARAM_LINE.match(line)
            if match:
                out[match.group(1)] = match.group(3)
        return out

    # -- launching ---------------------------------------------------------------------

    def engine_args(self) -> List[str]:
        """The flags every node carries, without exception.

        ``-enablewpoa=1 -enableweightengine=1`` are fixed for this harness. The treasury
        address is hash-enforced, so it is passed to every node identically or to none.
        ``-maxtxfee`` is wallet policy and merely has to be high enough.
        """
        args = [
            "-enablewpoa=1",
            "-enableweightengine=1",
            "-maxtxfee=%s" % self.profile.maxtxfee,
        ]
        if self.treasury_address:
            args.append("-weighttreasuryaddress=%s" % self.treasury_address)
        if self.profile.runtime.get("wpoa_debug"):
            args.append("-wpoadebug")
        digits = self.profile.runtime.get("api_decimal_digits")
        if digits is not None:
            # How many decimals the node's JSON writer keeps. It is a *diagnostic* lever,
            # not a tuning one: at the default of 14 a double whose fraction rounds up to
            # 1.000...0 is emitted as its floor, because the writer decides the precision
            # by rounding and then emits by truncating
            # (src/json/json_spirit_writer_template.h:257 and :349). Raising it moves the
            # boundary past where any audit value of this harness lands.
            args.append("-apidecimaldigits=%d" % int(digits))
        return args

    def command_line(self, node_id: str, join: bool) -> List[str]:
        """The full argv, including whatever it takes to run *as* this node.

        The fabric contributes at both ends: a prefix that puts the command where the node
        lives, and the flags that pin each plane to its own address. Both are empty in the
        native regime, so the command line there is exactly what it always was.
        """
        node = self.profile.node(node_id)
        target = (
            self.profile.seed_node_address if join else self.profile.chain_name
        )
        return self.fabric.wrap(node_id) + [
            str(self.multichaind),
            target,
            "-datadir=%s" % self.datadir(node_id),
            "-port=%d" % node.port,
            "-rpcport=%d" % node.rpc_port,
            "-daemon",
        ] + self.engine_args() + self.fabric.extra_node_args(node_id)

    def start(self, node_id: str, join: bool, attempts: int = 3) -> NodeHandle:
        """Launch one daemon detached and return its handle.

        ``-daemon`` makes the launcher fork and exit, so ``subprocess.run`` returning does
        not mean the node is up — only that the launcher finished.

        The retry exists for one specific, reproducible failure. A node that has just been
        stopped may still hold its LevelDB lock for a moment after its RPC port has closed,
        and a launch inside that window dies with::

            ERROR: Couldn't initialize permission database ... Probably multichaind for
            this blockchain is already running.
            IO error: lock .../permissions.db/LOCK: Resource temporarily unavailable

        which leaves a node that looks started and is not. Observed on the admin restart
        that installs the treasury address.
        """
        node = self.profile.node(node_id)
        datadir = self.datadir(node_id)
        datadir.mkdir(parents=True, exist_ok=True)
        stdout_path = datadir / "daemon.out"
        command = self.command_line(node_id, join)

        last_tail = ""
        for attempt in range(1, attempts + 1):
            with open(stdout_path, "a", encoding="utf-8") as handle:
                handle.write("\n$ %s\n" % " ".join(command))
                handle.flush()
                result = subprocess.run(
                    command, stdout=handle, stderr=subprocess.STDOUT, timeout=300
                )
            last_tail = _tail(stdout_path, 25)
            if _LOCK_HELD.search(last_tail) and attempt < attempts:
                time.sleep(3.0 * attempt)
                continue
            if result.returncode != 0 and "Node ready" not in last_tail:
                if attempt < attempts:
                    time.sleep(2.0 * attempt)
                    continue
                raise NodeStartError("%s failed to launch:\n%s" % (node_id, last_tail))
            break
        else:  # pragma: no cover - exhausted by the loop above
            raise NodeStartError("%s failed to launch:\n%s" % (node_id, last_tail))

        return NodeHandle(
            node_id=node_id,
            role=node.role,
            datadir=datadir,
            port=node.port,
            rpc_port=node.rpc_port,
            stdout_path=stdout_path,
            pid=self.read_pid(node_id),
            extra_args=self.engine_args(),
        )

    def read_pid(self, node_id: str) -> Optional[int]:
        """The node's PID, from ``<datadir>/<chain>/multichain.pid``.

        MultiChain does write one — an earlier note here claimed it did not, which was
        wrong: the check had been made *after* the daemons exited, and the file is
        correctly removed on a clean shutdown. Verified on a running node.

        It is still not the primary liveness signal, and :meth:`rpc_open` remains that.
        A pid file says a process was started; it cannot say the process has finished
        releasing its LevelDB lock, and on a crash it outlives the process entirely. The
        pid is what lets :meth:`stop` escalate to a signal when the RPC port refuses to
        close, which is the one thing the port alone cannot do.
        """
        for name in ("multichain.pid", "multichaind.pid"):
            pid_file = self.datadir(node_id) / self.profile.chain_name / name
            try:
                return int(pid_file.read_text(encoding="utf-8").strip())
            except (OSError, ValueError):
                continue
        return None

    def rpc_open(self, node_id: str) -> bool:
        """Is anything listening on this node's RPC port?

        The authoritative liveness test. It needs no pid file and no credentials, and a
        node that has closed its RPC port is on its way out even if the process lingers
        for another moment flushing LevelDB.
        """
        node = self.profile.node(node_id)
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.settimeout(1.0)
            return probe.connect_ex(
                (self.profile.rpc_host(node_id), node.rpc_port)
            ) == 0

    def wait_rpc_closed(self, node_id: str, timeout: float) -> bool:
        """Block until the RPC port closes. ``False`` on timeout."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            if not self.rpc_open(node_id):
                return True
            time.sleep(0.5)
        return not self.rpc_open(node_id)

    # -- stopping ----------------------------------------------------------------------

    def stop(self, node_id: str, grace_s: int = 30) -> str:
        """Ask a node to stop, and do not return until it actually has.

        Returns what ended it: ``absent`` (nothing was listening), ``rpc`` (it obeyed
        ``stop``), ``sigterm``, ``sigkill``, or ``timeout``. Reported per node at
        shutdown, because a node that needed a signal may have been wedged for a while
        and its last epoch's data is worth a second look.

        **Waiting is not optional.** An earlier version returned as soon as the ``stop``
        call came back, and a restart issued immediately afterwards died on the still-held
        LevelDB lock — leaving the seed node down while every joining node reported
        "couldn't connect to the seed node" and the whole bootstrap hung. The RPC port is
        the signal: it needs no pid file, which MultiChain does not reliably write.
        """
        if not self.rpc_open(node_id):
            return "absent"

        # Run the CLI *as the node*: inside its own namespace the RPC endpoint is
        # loopback, which is what multichain-cli assumes and what every node accepts
        # without an -rpcallowip of its own.
        result = subprocess.run(
            self.fabric.wrap(node_id)
            + [
                str(self.multichain_cli),
                "-datadir=%s" % self.datadir(node_id),
                "-rpcport=%d" % self.profile.node(node_id).rpc_port,
                self.profile.chain_name,
                "stop",
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
        obeyed = result.returncode == 0

        if self.wait_rpc_closed(node_id, grace_s):
            # The port closes before LevelDB has finished releasing its lock. Without this
            # settle a restart lands inside that window and fails; the node is already
            # gone, so the wait costs nothing but the wall clock.
            time.sleep(self.LOCK_SETTLE_S)
            return "rpc" if obeyed else "exited"

        pid = self.read_pid(node_id)
        if pid is None:
            return "timeout"
        # Through the fabric, never os.kill directly. A node of the emulated regime is a
        # PID namespace as well as a network one: `multichaind -daemon` forks inside it,
        # so the pid in its pid file is node-local and signalling it from out here would
        # reach an unrelated process, or none. It is the one difference between the two
        # regimes that is completely silent when got wrong.
        try:
            self.fabric.signal(node_id, pid, signal.SIGTERM)
        except OSError:
            return "exited"
        if self.wait_rpc_closed(node_id, max(5, grace_s // 3)):
            time.sleep(self.LOCK_SETTLE_S)
            return "sigterm"
        try:
            self.fabric.signal(node_id, pid, signal.SIGKILL)
        except OSError:
            return "sigterm"
        self.wait_rpc_closed(node_id, 10)
        time.sleep(self.LOCK_SETTLE_S)
        return "sigkill"

    def restart(self, node_id: str, join: bool, grace_s: int = 30) -> NodeHandle:
        """Stop a node and bring it back with the current flag set."""
        self.stop(node_id, grace_s)
        return self.start(node_id, join)

    # -- first launch ------------------------------------------------------------------

    def first_launch(self, node_id: str) -> Optional[str]:
        """Initialise a joining node's local chain and return the address it generated.

        A node joining a chain with ``anyone-can-connect = false`` does **not** become a
        daemon on its first run. It fetches the parameters from the seed, creates its
        wallet, prints

            Please ask blockchain admin ... to let you connect and/or transact:
            multichain-cli <chain> grant <ADDRESS> connect

        and **exits**. That is the documented sequence (``Create-Blockchain.md`` §5), and
        it is why the address has to be read from the output here: there is no RPC to ask
        yet, and there will not be one until the node is granted ``connect`` and started
        again.

        Returns the address, or ``None`` if the node came up as a daemon instead — which
        happens when its datadir was already initialised by an earlier run, and is handled
        by reading the address over RPC.
        """
        datadir = self.datadir(node_id)
        datadir.mkdir(parents=True, exist_ok=True)
        stdout_path = datadir / "daemon.out"
        command = self.command_line(node_id, join=True)
        with open(stdout_path, "a", encoding="utf-8") as handle:
            handle.write("\n$ %s   # first launch\n" % " ".join(command))
            handle.flush()
            subprocess.run(command, stdout=handle, stderr=subprocess.STDOUT, timeout=300)

        text = _tail(stdout_path, 40)
        match = _GRANT_HINT.search(text)
        if match:
            return match.group(1)
        if _SEED_UNREACHABLE.search(text):
            raise NodeStartError(
                "%s could not reach the seed node %s. The seed must be serving before any "
                "peer joins.\n%s" % (node_id, self.profile.seed_node_address, text)
            )
        return None

    def stop_all(self, grace_s: int = 30) -> Dict[str, str]:
        """Stop every node, the seed **last**.

        The joined nodes talk to the seed; taking it down first makes each of them spend
        its shutdown retrying a dead peer, which turns a fast teardown into a slow one.
        """
        outcomes: Dict[str, str] = {}
        for node in reversed(self.profile.nodes):
            try:
                outcomes[node.node_id] = self.stop(node.node_id, grace_s)
            except Exception as exc:  # teardown must never raise past this point
                outcomes[node.node_id] = "error: %s" % exc
        return outcomes


# --------------------------------------------------------------------------------------
# small helpers
# --------------------------------------------------------------------------------------


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _tail(path: Path, lines: int) -> str:
    try:
        content = path.read_text(encoding="utf-8", errors="replace").rstrip().split("\n")
    except OSError:
        return ""
    return "\n".join(content[-lines:])


def write_json(path: Path, payload: Any) -> None:
    """Write a manifest atomically: a run that dies mid-write must not leave half a file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=False, default=str), encoding="utf-8")
    shutil.move(str(tmp), str(path))


__all__ = ["NodeHandle", "NodeRunner", "NodeStartError", "write_json"]
