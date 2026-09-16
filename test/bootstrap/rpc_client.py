"""An ad-hoc JSON-RPC client for ``multichaind``.

Deliberately built from nothing: HTTP POST to ``/`` with ``Content-Type:
application/json`` and HTTP Basic Auth, exactly what the node's libevent handler expects.
No ``python-bitcoinrpc``, no ``python-multichain-rpc``, no RPC library of any kind — the
whole protocol is four lines of framing and the value of a dedicated dependency here
would be negative.

``requests`` is used when it is importable and the standard library's ``urllib`` when it
is not. The container this harness runs in ships neither ``requests`` nor apt lists to
install it from, and the two paths do the same thing, so the fallback costs nothing and
removes the last reason a run could fail before it starts. ``pip install requests``
silently activates the preferred path.

Credentials come from ``<datadir>/<chain>/multichain.conf`` (``rpcuser`` /
``rpcpassword``, plain ``key=value``, ``#`` comments), which the node writes at chain
creation, or may be passed explicitly.
"""

from __future__ import annotations

import base64
import json
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

try:  # pragma: no cover - environment-dependent
    import requests as _requests
except ImportError:  # pragma: no cover
    _requests = None

#: Which transport is actually in use. Recorded in the run manifest so a result can be
#: traced back to the client that produced it.
TRANSPORT = "requests" if _requests is not None else "urllib"


class RpcError(RuntimeError):
    """The node answered, and the answer was an error.

    ``code`` is MultiChain's own JSON-RPC error code; the ones this harness reacts to
    are ``-6`` (insufficient funds / fee policy) and ``-708`` (entity not found).
    """

    def __init__(self, method: str, code: Any, message: str, params: Any = None) -> None:
        super().__init__("%s: [%s] %s" % (method, code, message))
        self.method = method
        self.code = code
        self.message = message
        self.params = params


class RpcTransportError(RuntimeError):
    """The node did not answer: connection refused, timeout, HTTP error, bad JSON.

    Kept distinct from :class:`RpcError` because the two mean opposite things. A
    transport error during startup is expected and should be retried; one in the middle
    of a run means a daemon died.
    """


def read_credentials(datadir: str | Path, chain_name: str) -> Tuple[str, str]:
    """Parse ``rpcuser`` / ``rpcpassword`` out of ``<datadir>/<chain>/multichain.conf``."""
    conf = Path(datadir) / chain_name / "multichain.conf"
    if not conf.is_file():
        raise RpcTransportError("no multichain.conf at %s" % conf)
    user = password = ""
    for line in conf.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.split("#", 1)[0].strip()
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip()
        if key == "rpcuser":
            user = value
        elif key == "rpcpassword":
            password = value
    if not password:
        raise RpcTransportError(
            "%s carries no rpcpassword; the node writes one at chain creation" % conf
        )
    return user or "multichainrpc", password


class RpcClient:
    """One node's RPC endpoint.

    Every call is a single POST. There is no connection pooling beyond what the
    transport does on its own, because a harness that makes a few calls per second does
    not need it and a shared session would hide which node a failure came from.
    """

    def __init__(
        self,
        host: str,
        port: int,
        user: str,
        password: str,
        chain_name: str = "",
        node_id: str = "",
        timeout: int = 30,
    ) -> None:
        self.host = host
        self.port = int(port)
        self.user = user
        self.password = password
        self.chain_name = chain_name
        self.node_id = node_id or "%s:%d" % (host, port)
        self.timeout = int(timeout)
        self.url = "http://%s:%d/" % (host, self.port)
        self._auth = base64.b64encode(
            ("%s:%s" % (user, password)).encode("utf-8")
        ).decode("ascii")
        self._counter = 0
        #: Cumulative call count and failure count, reported at shutdown.
        self.calls = 0
        self.failures = 0

    # -- construction ------------------------------------------------------------------

    @classmethod
    def from_datadir(
        cls,
        datadir: str | Path,
        chain_name: str,
        host: str,
        port: int,
        node_id: str = "",
        timeout: int = 30,
    ) -> "RpcClient":
        user, password = read_credentials(datadir, chain_name)
        return cls(host, port, user, password, chain_name, node_id, timeout)

    def __repr__(self) -> str:  # pragma: no cover - diagnostics only
        return "<RpcClient %s %s>" % (self.node_id, self.url)

    # -- the call ----------------------------------------------------------------------

    def call(self, method: str, *params: Any) -> Any:
        """Invoke ``method``. Returns ``result``; raises on anything else.

        ``None`` arguments are dropped from the tail only — MultiChain's positional
        arguments mean a hole in the middle would shift every later one, so a ``None``
        before a non-``None`` is a programming error and is reported as such.
        """
        args = list(params)
        while args and args[-1] is None:
            args.pop()
        if any(a is None for a in args):
            raise ValueError(
                "%s: a None argument precedes a non-None one; MultiChain arguments are "
                "positional and cannot be skipped" % method
            )

        self._counter += 1
        self.calls += 1
        payload = json.dumps(
            {
                "id": "%s-%d" % (self.node_id, self._counter),
                "method": method,
                "params": args,
            }
        ).encode("utf-8")

        try:
            body = self._post(payload)
        except Exception:
            self.failures += 1
            raise

        try:
            answer = json.loads(body)
        except ValueError as exc:
            self.failures += 1
            raise RpcTransportError(
                "%s on %s returned unparsable JSON: %s" % (method, self.node_id, exc)
            ) from exc

        error = answer.get("error")
        if error:
            self.failures += 1
            if isinstance(error, dict):
                raise RpcError(method, error.get("code"), str(error.get("message")), args)
            raise RpcError(method, None, str(error), args)
        return answer.get("result")

    def _post(self, payload: bytes) -> str:
        headers = {
            "Content-Type": "application/json",
            "Authorization": "Basic %s" % self._auth,
            "Connection": "close",
        }
        if _requests is not None:
            try:
                response = _requests.post(
                    self.url, data=payload, headers=headers, timeout=self.timeout
                )
            except Exception as exc:  # requests wraps everything in its own tree
                raise RpcTransportError(
                    "%s is unreachable: %s" % (self.node_id, exc)
                ) from exc
            # A 500 still carries a JSON-RPC error body, which is more informative than
            # the status line; only an empty body is hopeless.
            if response.status_code >= 400 and not response.text:
                raise RpcTransportError(
                    "%s answered HTTP %d with no body" % (self.node_id, response.status_code)
                )
            return response.text

        request = urllib.request.Request(self.url, data=payload, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as handle:
                return handle.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            if body:
                return body
            raise RpcTransportError(
                "%s answered HTTP %d with no body" % (self.node_id, exc.code)
            ) from exc
        except Exception as exc:
            raise RpcTransportError("%s is unreachable: %s" % (self.node_id, exc)) from exc

    # -- convenience -------------------------------------------------------------------

    def try_call(self, method: str, *params: Any) -> Tuple[bool, Any]:
        """``(ok, result_or_exception)``. For calls whose failure is not fatal.

        Used for grants that may already be in place and stream creations that may have
        raced another node — cases where the exception is the answer, not a problem.
        """
        try:
            return True, self.call(method, *params)
        except (RpcError, RpcTransportError) as exc:
            return False, exc

    def wait_ready(self, timeout: int, poll_s: float = 1.0) -> Dict[str, Any]:
        """Block until ``getinfo`` answers, or raise.

        Transport errors are expected here — the daemon binds its RPC port some way into
        startup — so they are swallowed until the deadline and only the last one is
        reported.
        """
        deadline = time.time() + timeout
        last = "no attempt completed"
        while time.time() < deadline:
            try:
                return self.call("getinfo")
            except (RpcTransportError, RpcError) as exc:
                last = str(exc)
                time.sleep(poll_s)
        raise RpcTransportError(
            "%s did not serve RPC within %ds; last error: %s" % (self.node_id, timeout, last)
        )

    def block_height(self) -> int:
        """Current tip height. ``getinfo.blocks``."""
        return int(self.call("getinfo")["blocks"])

    def wait_for_height(
        self, height: int, timeout: int, poll_s: float = 2.0
    ) -> Optional[int]:
        """Block until the tip reaches ``height``. Returns the tip, or ``None`` on timeout."""
        deadline = time.time() + timeout
        tip = -1
        while time.time() < deadline:
            try:
                tip = self.block_height()
            except (RpcTransportError, RpcError):
                tip = -1
            if tip >= height:
                return tip
            time.sleep(poll_s)
        return None

    def wait_for_confirmations(self, blocks: int = 1, timeout: int = 120) -> Optional[int]:
        """Block until ``blocks`` further blocks have been mined."""
        try:
            start = self.block_height()
        except (RpcTransportError, RpcError):
            return None
        return self.wait_for_height(start + blocks, timeout)

    def own_address(self) -> str:
        """This node's wallet address.

        ``getaddresses`` can return several once a treasury key has been created, and
        the node's *identity* — the one that signs its blocks and its self-attested
        records — is the first. Taking a later one would silently break self-attestation.
        """
        addresses = self.call("getaddresses")
        if not addresses:
            raise RpcTransportError("%s has no wallet address" % self.node_id)
        first = addresses[0]
        return first["address"] if isinstance(first, dict) else str(first)

    def native_balance(self) -> float:
        """Spendable native currency held by this node's wallet."""
        return float(self.call("getinfo").get("balance") or 0.0)

    def stream_items(self, stream: str, count: int = 100000, start: int = 0) -> list:
        """Read a stream.

        ``liststreamitems`` defaults to ``count = 10``, which silently truncates every
        read of a real stream; the count is always passed explicitly here.
        """
        return self.call("liststreamitems", stream, True, count, start)


__all__ = [
    "RpcClient",
    "RpcError",
    "RpcTransportError",
    "TRANSPORT",
    "read_credentials",
]
