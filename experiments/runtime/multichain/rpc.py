"""JSON-RPC client for ``multichaind``, standard library only.

Used by the harness on the controlling host, over the management plane, so
polling never travels the impaired paths under measurement. The role scripts
that run *inside* the nodes speak the same protocol with ``curl``; see
``runtime/roles/_common.sh`` for why they do not use ``multichain-cli``.

Errors are values, not exceptions, for the polling paths: a node that is not
up yet answers with a connection refusal several times before it answers with
a block count, and that is normal rather than exceptional.
"""

from __future__ import annotations

import base64
import json
import logging
import socket
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

LOG = logging.getLogger("experiments.runtime.rpc")


@dataclass
class RpcError(Exception):
    """A failure to obtain a result, whatever its layer."""

    method: str
    message: str
    code: int | None = None
    transport: bool = False

    def __str__(self) -> str:  # pragma: no cover - formatting only
        kind = "transport" if self.transport else "rpc"
        return "%s error on %s: %s" % (kind, self.method, self.message)


class RpcClient:
    """One endpoint, one set of credentials."""

    def __init__(self, url: str, user: str, password: str, *, timeout_s: float = 60.0,
                 node_id: str = "") -> None:
        self.url = url
        self.node_id = node_id or "harness"
        self._timeout = timeout_s
        token = base64.b64encode(("%s:%s" % (user, password)).encode()).decode()
        self._headers = {
            "Authorization": "Basic %s" % token,
            "Content-Type": "application/json",
        }

    def call(self, method: str, params: list | None = None, *,
             timeout_s: float | None = None) -> Any:
        """Invoke a method and return its ``result``, raising :class:`RpcError`."""
        payload = json.dumps(
            {"id": self.node_id, "method": method, "params": params or []}
        ).encode()
        request = urllib.request.Request(self.url, data=payload, headers=self._headers)
        try:
            with urllib.request.urlopen(request, timeout=timeout_s or self._timeout) as response:
                body = json.loads(response.read().decode("utf-8", "replace"))
        except urllib.error.HTTPError as exc:
            # MultiChain returns 500 with a JSON error body for rejected calls.
            raw = exc.read().decode("utf-8", "replace")
            try:
                body = json.loads(raw)
            except ValueError:
                raise RpcError(method, "HTTP %d: %s" % (exc.code, raw.strip()[:200]),
                               transport=True) from exc
        except (urllib.error.URLError, socket.timeout, ConnectionError, OSError) as exc:
            raise RpcError(method, str(exc), transport=True) from exc
        except ValueError as exc:
            raise RpcError(method, "malformed JSON response: %s" % exc, transport=True) from exc

        error = body.get("error")
        if error:
            raise RpcError(method, str(error.get("message", error)), code=error.get("code"))
        return body.get("result")

    def try_call(self, method: str, params: list | None = None,
                 *, timeout_s: float | None = None) -> tuple[Any, RpcError | None]:
        """Non-raising variant for polling loops."""
        try:
            return self.call(method, params, timeout_s=timeout_s), None
        except RpcError as exc:
            return None, exc

    # -- convenience --------------------------------------------------------
    def is_up(self) -> bool:
        _, error = self.try_call("getblockcount", timeout_s=min(self._timeout, 10.0))
        return error is None

    def block_count(self) -> int | None:
        value, error = self.try_call("getblockcount")
        return None if error else int(value)

    def wait_ready(self, timeout_s: float, *, poll_s: float = 2.0) -> bool:
        """Block until the daemon answers, or the deadline passes."""
        deadline = time.monotonic() + timeout_s
        last: RpcError | None = None
        while time.monotonic() < deadline:
            value, error = self.try_call("getblockcount", timeout_s=min(10.0, timeout_s))
            if error is None:
                del value
                return True
            last = error
            time.sleep(poll_s)
        if last is not None:
            LOG.debug("%s not ready after %gs: %s", self.url, timeout_s, last)
        return False

    def wait_height(self, target: int, timeout_s: float, *, poll_s: float = 5.0) -> bool:
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            height = self.block_count()
            if height is not None and height >= target:
                return True
            time.sleep(poll_s)
        return False

    def wait_stream(self, name: str, timeout_s: float, *, poll_s: float = 5.0) -> bool:
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            _, error = self.try_call("liststreams", [name])
            if error is None:
                return True
            time.sleep(poll_s)
        return False
