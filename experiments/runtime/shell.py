"""Running external commands, with privilege handling and honest errors.

Everything the fabric does is ``ip``, ``tc`` and ``nsenter``, and all three
need ``CAP_NET_ADMIN``. Rather than scatter ``sudo`` through the code, one
:class:`Runner` decides once how a privileged command is invoked and every
call site goes through it. That makes the privilege requirement testable
(``--dry-run`` prints exactly what would run) and keeps a run reproducible on a
machine where the user is already root.
"""

from __future__ import annotations

import logging
import os
import shlex
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from ..exit_codes import EnvironmentError_, RuntimeFailure

LOG = logging.getLogger("experiments.runtime.shell")


@dataclass
class Result:
    argv: list[str]
    returncode: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.returncode == 0

    def check(self, what: str = "") -> "Result":
        if not self.ok:
            raise RuntimeFailure(
                "%s failed (rc=%d): %s\n%s"
                % (what or shlex.join(self.argv), self.returncode,
                   self.stderr.strip() or self.stdout.strip(), shlex.join(self.argv))
            )
        return self


@dataclass
class Runner:
    """Executes commands, optionally elevating them and optionally faking them.

    ``dry_run`` records the command and returns success without executing it.
    It is what ``experiment dry-run`` uses to show the full sequence a real run
    would issue, which is the only way to review privileged plumbing before
    granting it privileges.
    """

    dry_run: bool = False
    sudo: str | None = None
    recorded: list[list[str]] = field(default_factory=list)
    timeout_s: float = 120.0

    def __post_init__(self) -> None:
        if self.sudo is None:
            self.sudo = "" if os.geteuid() == 0 else (shutil.which("sudo") or "")

    # -- privilege ----------------------------------------------------------
    @property
    def is_root(self) -> bool:
        return os.geteuid() == 0

    def privileged_argv(self, argv: list[str]) -> list[str]:
        if self.is_root or not self.sudo:
            return list(argv)
        return [self.sudo, "-n"] + list(argv)

    def require_privileges(self) -> None:
        """Fail early and clearly when the fabric cannot be built at all."""
        if self.dry_run or self.is_root:
            return
        if not self.sudo:
            raise EnvironmentError_(
                "creating network namespaces needs root and sudo was not found",
                hint="run as root, or install sudo, or use --dry-run to inspect the plan",
            )
        probe = subprocess.run(
            [self.sudo, "-n", "true"], capture_output=True, text=True
        )
        if probe.returncode != 0:
            raise EnvironmentError_(
                "sudo needs a password, so the harness cannot create namespaces "
                "unattended",
                hint="configure NOPASSWD for ip/tc/nsenter, run the harness as root, "
                     "or use --dry-run",
            )

    # -- execution ----------------------------------------------------------
    def run(self, argv: list[str], *, privileged: bool = False, check: bool = True,
            input_text: str | None = None, timeout_s: float | None = None,
            what: str = "") -> Result:
        argv = [str(a) for a in argv]
        final = self.privileged_argv(argv) if privileged else argv
        self.recorded.append(final)
        if self.dry_run:
            LOG.debug("dry-run: %s", shlex.join(final))
            return Result(final, 0, "", "")
        LOG.debug("exec: %s", shlex.join(final))
        try:
            proc = subprocess.run(
                final, capture_output=True, text=True, input=input_text,
                timeout=timeout_s or self.timeout_s,
            )
        except FileNotFoundError as exc:
            raise EnvironmentError_(
                "%s is not installed or not on PATH" % final[0]
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise RuntimeFailure(
                "%s timed out after %gs" % (shlex.join(final), timeout_s or self.timeout_s)
            ) from exc
        result = Result(final, proc.returncode, proc.stdout, proc.stderr)
        if check:
            result.check(what)
        return result

    def ip(self, *args: str, check: bool = True, what: str = "") -> Result:
        return self.run(["ip", *args], privileged=True, check=check, what=what)

    def tc(self, *args: str, check: bool = True, what: str = "") -> Result:
        return self.run(["tc", *args], privileged=True, check=check, what=what)

    def in_netns(self, namespace: str, argv: list[str], *, check: bool = True,
                 what: str = "", timeout_s: float | None = None) -> Result:
        return self.run(
            ["ip", "netns", "exec", namespace, *[str(a) for a in argv]],
            privileged=True, check=check, what=what, timeout_s=timeout_s,
        )

    def spawn_detached(self, argv: list[str], *, stdout: Path,
                       stderr: Path | None = None, cwd: Path | None = None,
                       env: dict | None = None) -> subprocess.Popen | None:
        """Start a long-lived process in its own session, already wrapped.

        ``argv`` is taken as final: privilege elevation and any namespace
        wrapper are the caller's business, because only the fabric knows which
        one applies. Returns ``None`` in dry-run.

        ``start_new_session=True`` matters: without it a Ctrl+C on the harness
        reaches every daemon at once through the shared process group, and the
        run dies before the cleanup path can take a final snapshot. The caller
        owns the handle; :class:`~experiments.runtime.session.Session`
        terminates it from cleanup so a crash never leaves a daemon behind.
        """
        final = [str(a) for a in argv]
        self.recorded.append(final)
        if self.dry_run:
            LOG.debug("dry-run spawn: %s", shlex.join(final))
            return None
        stdout.parent.mkdir(parents=True, exist_ok=True)
        out = stdout.open("ab")
        err = stderr.open("ab") if stderr else subprocess.STDOUT
        merged = dict(os.environ)
        merged.update({k: str(v) for k, v in (env or {}).items()})
        LOG.debug("spawn: %s", shlex.join(final))
        return subprocess.Popen(
            final, stdout=out, stderr=err, cwd=str(cwd) if cwd else None,
            env=merged, start_new_session=True,
        )

    def spawn_in_netns(self, namespace: str, argv: list[str], *, stdout: Path,
                       stderr: Path | None = None, cwd: Path | None = None,
                       env: dict | None = None) -> subprocess.Popen | None:
        """Start a long-lived process inside a network namespace."""
        wrapped = self.privileged_argv(
            ["ip", "netns", "exec", namespace, *[str(a) for a in argv]]
        )
        return self.spawn_detached(wrapped, stdout=stdout, stderr=stderr, cwd=cwd, env=env)


def which(name: str) -> str | None:
    """``shutil.which`` that also looks in the sbin directories.

    ``ip`` and ``tc`` live in ``/usr/sbin`` on Debian and Ubuntu, which is not
    on a non-root user's PATH — the single most common reason the harness
    appears to be missing a tool that is in fact installed.
    """
    found = shutil.which(name)
    if found:
        return found
    for directory in ("/sbin", "/usr/sbin", "/usr/local/sbin"):
        candidate = Path(directory) / name
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
    return None
