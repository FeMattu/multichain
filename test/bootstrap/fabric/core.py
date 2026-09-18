"""The CORE regime: one network namespace per site, netem on every cable.

What this builds, and why it is built this way:

**Two planes.** The cables of the topology carry the chain's peer-to-peer traffic and all
the impairment; a separate control network, which CORE creates and bridges into the
container's root namespace, carries the harness's RPC and nothing else. The orchestrator,
the observer, the CA assigner, the detector and every traffic daemon therefore stay
ordinary processes with their existing logs and process groups — and, more importantly,
the instrument does not sit inside the thing it measures. Pushing those daemons into the
namespaces would make every RPC call pay the emulated latency and would put the
measurement plumbing on the critical path of the measurement. This is a declared property
of the method, stated in ``config/schema.md``, not a convenience.

**A site, not a node, is the unit.** Each site of the map becomes one namespace. Chain
nodes are *placed* at a site and run inside its namespace, so several nodes at one site
share its addresses and are told apart by port — which is what the profile's
``base_port + index`` map already guarantees and what co-location means. A site with no
chain node is a pure transit router.

**Static routes.** Computed from the map by :mod:`.topology` and installed at start. No
routing daemon: a protocol's convergence time is wall-clock nondeterminism, and it would
land in the one part of a measurement harness that must not have any.

**The peer mesh must not escape onto the control plane.** That is the one failure that
would invalidate a whole campaign with no visible symptom: the chain would form on an
unimpaired network and every figure would describe a geography nobody ran. Three
mechanisms prevent it — ``-bind`` so the listener exists only on the data address,
``-externalip`` with ``-discover=0`` so the node advertises that address and does not go
looking for another, and a seed address that resolves to the admin's data address — and
:meth:`peers_off_the_data_plane` gives the orchestrator the fourth: an assertion, after
the fact, over what the nodes actually connected to.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from . import FabricError
from .addressing import CONTROL_NETWORK
from .topology import Impairment, RealisedLink

#: Where the CORE daemon answers. The container's entrypoint starts it here.
DEFAULT_GRPC_ADDRESS = os.environ.get("CORE_GRPC_ADDRESS", "127.0.0.1:50051")

#: CORE keeps one directory per node, holding the socket ``vcmd`` connects to and the
#: ``vnoded`` pid file. The session id is only known once the session exists.
NODE_DIR_TEMPLATE = "/tmp/pycore.%d/%s"

#: Enough for a twenty-node map to appear sanely in CORE's GUI if anyone opens one. The
#: emulation ignores position entirely; this is purely so the picture is readable.
CANVAS_SCALE = 4.0


def _us(milliseconds: float) -> int:
    """netem takes microseconds, the maps state milliseconds."""
    return int(round(float(milliseconds) * 1000.0))


def _bps(mbps: Optional[float]) -> int:
    """0 means "no shaping" to CORE, which is what an unset capacity means here."""
    return int(round(float(mbps) * 1_000_000.0)) if mbps else 0


class CoreFabric:
    """A live CORE session, built from a topology and torn down with the run."""

    name = "core"

    def __init__(self, profile, run_dir=None, grpc_address: str = DEFAULT_GRPC_ADDRESS) -> None:
        self.profile = profile
        self.run_dir = Path(run_dir) if run_dir else None
        self.grpc_address = grpc_address
        self.topology = profile.topology
        self.plan = profile.address_plan
        if self.topology is None or self.plan is None:
            raise FabricError(
                "the CORE fabric needs a topology: the profile must name one with "
                "`topology: topologies/<name>.yaml`."
            )
        self.realised: List[RealisedLink] = profile.realised_links()
        self.session_id: Optional[int] = None
        self._client = None
        self._session = None
        self._core_nodes: Dict[str, Any] = {}
        self._started = False
        #: Cables whose two directions differ, applied once the session is up.
        self._reverse: List[Tuple[Any, Impairment]] = []
        #: What CORE reported once the session was up, as opposed to what was asked for.
        self._observed: Dict[str, Any] = {}

    # -- naming ------------------------------------------------------------------------

    def site_of(self, node_id: str) -> str:
        site = self.profile.site_of(node_id)
        if not site:
            raise FabricError("node %r has no location on this map" % node_id)
        return site

    def node_dir(self, node_id: str) -> str:
        """The CORE node directory of the *site* this chain node runs at."""
        if self.session_id is None:
            raise FabricError("the CORE session is not started")
        return NODE_DIR_TEMPLATE % (self.session_id, self.site_of(node_id))

    # -- lifecycle ---------------------------------------------------------------------

    def start(self) -> None:
        if self._started:
            return
        client, wrappers = _import_core()
        self._client = client.CoreGrpcClient(self.grpc_address)
        try:
            self._client.connect()
        except Exception as exc:  # grpc raises its own tree
            raise FabricError(
                "no CORE daemon answering at %s (%s). Inside the project's container, "
                "bring it up with `core-up`; outside it, there is no emulator to use."
                % (self.grpc_address, exc)
            ) from exc

        session = self._client.create_session()
        self.session_id = session.id
        self._session = session

        self._add_sites(session, wrappers)
        self._add_links(session, wrappers)

        # The out-of-band plane. Set before start_session, because CORE builds it with
        # the rest of the network rather than afterwards.
        session.options["controlnet"].value = CONTROL_NETWORK

        self._client.start_session(session)
        self._started = True

        # Everything below is configuration CORE does not model from the session alone:
        # the second half of an asymmetric cable, the identity address the chain binds
        # to, and the routes that reach it.
        self._apply_reverse_links()
        self._install_identities()
        self._install_routes()
        self._read_back()

    def stop(self) -> None:
        """Delete the session. Never raises: this runs in a ``finally``."""
        if self._client is None or self.session_id is None:
            return
        for step in ("stop_session", "delete_session"):
            try:
                getattr(self._client, step)(self.session_id)
            except Exception as exc:  # pragma: no cover - teardown is best effort
                print("[fabric] %s(%s) failed: %s" % (step, self.session_id, exc), flush=True)
        try:
            self._client.close()
        except Exception:  # pragma: no cover
            pass
        self._started = False

    # -- building ----------------------------------------------------------------------

    def _add_sites(self, session, wrappers) -> None:
        """One CORE node per site, numbered as the address plan numbered them.

        The node id is the site's index, which is what makes its control address
        (``prefix + id``, assigned by CORE) equal to the one the plan predicted — so a
        child process can resolve an RPC endpoint without asking the emulator.
        """
        for site_id in self.topology.order:
            site = self.topology.site(site_id)
            address = self.plan.site(site_id)
            node = session.add_node(
                address.index,
                name=site_id,
                _type=wrappers.NodeType.DEFAULT,
                position=wrappers.Position(
                    x=(site.lon + 180.0) * CANVAS_SCALE,
                    y=(90.0 - site.lat) * CANVAS_SCALE,
                ),
            )
            # No services and no model. CORE's stock models start things of their own --
            # a routing daemon, a default route pointing at the node itself -- and this
            # fabric installs its own routes from the map. A service that quietly added a
            # route would change which path a packet takes, and therefore its delay.
            node.model = None
            node.services = set()
            self._core_nodes[site_id] = node

    def _link_options(self, impairment: Impairment, wrappers, unidirectional: bool = False):
        return wrappers.LinkOptions(
            delay=_us(impairment.delay_ms),
            jitter=_us(impairment.jitter_ms),
            loss=float(impairment.loss_percent),
            bandwidth=_bps(impairment.bandwidth_mbps),
            buffer=int(impairment.queue_packets),
            unidirectional=unidirectional,
        )

    def _add_links(self, session, wrappers) -> None:
        """One veth pair per cable, with its qdisc.

        CORE puts the impairment on **each** end, so ``delay`` is one way and the round
        trip is twice it — which is exactly what the maps' ``mean_ms`` means. An
        asymmetric profile is the one case where the two ends differ, and it is expressed
        by two unidirectional links rather than by an average: averaging them would be a
        third network that nobody configured.
        """
        for realised in self.realised:
            cable = self.plan.link_between(realised.link.source, realised.link.target)
            iface1 = wrappers.Interface(
                id=cable.source_iface_id,
                name=cable.source_iface,
                ip4=cable.source_ip,
                ip4_mask=cable.prefix_len,
            )
            iface2 = wrappers.Interface(
                id=cable.target_iface_id,
                name=cable.target_iface,
                ip4=cable.target_ip,
                ip4_mask=cable.prefix_len,
            )
            asymmetric = realised.is_asymmetric
            session.add_link(
                node1=self._core_nodes[cable.source],
                node2=self._core_nodes[cable.target],
                iface1=iface1,
                iface2=iface2,
                options=self._link_options(realised.forward, wrappers, asymmetric),
            )
            if asymmetric:
                # The reverse direction is a second, unidirectional statement about the
                # same pair of interfaces; the session has to be up before it is made.
                self._reverse.append((cable, realised.reverse))

    # -- per-namespace configuration ---------------------------------------------------

    def _run_in(self, site_id: str, command: str, why: str) -> None:
        """Run one configuration command inside a site's namespace."""
        node = self._core_nodes[site_id]
        returncode, output = self._client.node_command(self.session_id, node.id, command)
        if returncode != 0:
            raise FabricError(
                "%s failed on site %s: `%s` exited %d\n%s"
                % (why, site_id, command, returncode, (output or "").strip()[:400])
            )

    def _install_identities(self) -> None:
        """The address the chain binds to, on ``lo``.

        A /32 on loopback rather than an address on one of the cables: a node has several
        cables, and an identity that changes with the interface a packet happens to leave
        by is not an identity. Every route below carries ``src`` so that the kernel
        sources from it.
        """
        for site_id in self.topology.order:
            identity = self.plan.site(site_id).identity_cidr
            self._run_in(
                site_id,
                "ip addr replace %s dev lo" % identity,
                "installing the identity address",
            )
            self._run_in(site_id, "sysctl -w net.ipv4.ip_forward=1", "enabling forwarding")

    def _apply_reverse_links(self) -> None:
        """The second half of every asymmetric cable."""
        if not self._reverse:
            return
        _, wrappers = _import_core()
        for cable, reverse in self._reverse:
            self._apply_reverse(cable, reverse, wrappers)

    def _apply_reverse(self, cable, reverse: Impairment, wrappers) -> None:
        """One reverse half, as a unidirectional statement about the same pair.

        Node 1 of this statement is the cable's *target*: netem shapes egress only, so the
        impairment a packet meets travelling target -> source is the qdisc on the target's
        interface. Naming the ends the other way round would apply the reverse numbers to
        the forward direction, which is a network nobody configured and one that no
        summary statistic would reveal.
        """
        link = wrappers.Link(
            node1_id=self._core_nodes[cable.target].id,
            node2_id=self._core_nodes[cable.source].id,
            iface1=wrappers.Interface(id=cable.target_iface_id),
            iface2=wrappers.Interface(id=cable.source_iface_id),
            options=self._link_options(reverse, wrappers, unidirectional=True),
        )
        try:
            self._client.edit_link(self.session_id, link)
        except Exception as exc:
            raise FabricError(
                "could not apply the reverse impairment of %s-%s: %s. An asymmetric "
                "profile that silently became symmetric would report a network nobody "
                "configured." % (cable.source, cable.target, exc)
            ) from exc

    def _install_routes(self) -> None:
        for site_id, routes in self.plan.routes().items():
            for route in routes:
                self._run_in(
                    site_id,
                    "ip route replace %s via %s dev %s src %s"
                    % (route.destination, route.via, route.dev, route.src),
                    "installing a static route",
                )

    def _read_back(self) -> None:
        """What CORE actually assigned, as opposed to what was asked for.

        The control address in particular is CORE's to allocate. The plan predicts it, and
        the prediction is what child processes use, so a disagreement has to be an error
        here rather than a mystery three steps later.
        """
        observed: Dict[str, Any] = {}
        for site_id in self.topology.order:
            node = self._core_nodes[site_id]
            returncode, output = self._client.node_command(
                self.session_id, node.id, "ip -4 -o addr show"
            )
            addresses = _parse_addresses(output if returncode == 0 else "")
            observed[site_id] = addresses
            expected = self.plan.site(site_id).control
            if expected not in addresses.get("ctrl0", []):
                raise FabricError(
                    "site %s has control addresses %s, and the address plan predicted %s. "
                    "Every child process resolves an RPC endpoint from that prediction, so "
                    "they must agree."
                    % (site_id, addresses.get("ctrl0", []) or "none", expected)
                )
        self._observed = observed

    # -- running as a node -------------------------------------------------------------

    def wrap(self, node_id: str) -> List[str]:
        """Enter the namespace of the site this node is placed at.

        ``vcmd`` talks to the ``vnoded`` that owns the namespace, which is how CORE runs
        anything in a node. The alternative, ``nsenter`` on the vnoded pid, enters the
        network namespace only; ``vcmd`` enters the node as CORE understands it, which is
        what makes a process started here look the same as one CORE started itself.
        """
        return [_vcmd(), "-c", self.node_dir(node_id), "--"]

    def signal(self, node_id: str, pid: int, sig: int) -> None:
        """Signal inside the node, because the pid only means anything there.

        A CORE node is a PID namespace as well as a network one. ``multichaind -daemon``
        forks inside it, so the pid it writes into its pid file is node-local: sending it
        a signal from the root namespace would hit an unrelated process, or none. This is
        the one difference between the regimes that is silent when got wrong.
        """
        subprocess.run(
            self.wrap(node_id) + ["kill", "-%d" % int(sig), str(int(pid))],
            capture_output=True,
            timeout=30,
            check=False,
        )

    def extra_node_args(self, node_id: str) -> List[str]:
        """Pin each plane to its own address.

        ``-bind`` puts the peer-to-peer listener on the data address only, so nothing can
        peer over the control network even by accident. ``-externalip`` with
        ``-discover=0`` makes the node advertise that same address instead of guessing one
        from its interfaces — and it has two, one of which would form the mesh on the
        unimpaired plane.

        RPC goes exactly the other way. MultiChain binds loopback unless ``-rpcallowip``
        is given, and warns when ``-rpcbind`` is given without it, so the two are passed
        together: loopback for the ``multichain-cli`` calls this fabric makes *inside* the
        namespace, and the control address for the harness outside it.
        """
        site_id = self.site_of(node_id)
        identity = self.plan.identity(site_id)
        control = self.plan.control(site_id)
        return [
            "-bind=%s" % identity,
            "-externalip=%s" % identity,
            "-discover=0",
            "-rpcbind=%s" % control,
            "-rpcbind=127.0.0.1",
            "-rpcallowip=%s" % CONTROL_NETWORK,
            "-rpcallowip=127.0.0.1",
        ]

    # -- the assertion that protects the campaign --------------------------------------

    def peers_off_the_data_plane(self, peers: Iterable[str]) -> List[str]:
        """Which of these peer addresses are not on the emulated plane.

        The orchestrator calls this with every address in every node's ``getpeerinfo``. A
        non-empty answer means the chain formed, wholly or partly, on the control network:
        the run would complete, the report would read normally, and every number in it
        would describe a network with no delay in it. There is no recovering from that
        after the fact, so it fails the run.
        """
        allowed = {self.plan.identity(site) for site in self.topology.order}
        off = []
        for peer in peers:
            address = str(peer).rsplit(":", 1)[0].strip("[]")
            if address and address not in allowed:
                off.append(str(peer))
        return off

    # -- evidence ----------------------------------------------------------------------

    def describe(self) -> Dict[str, Any]:
        return {
            "backend": self.name,
            "session_id": self.session_id,
            "grpc_address": self.grpc_address,
            "topology": self.topology.as_dict(),
            "network_profile": self.profile.network_profile_description,
            "addressing": self.plan.as_dict(),
            "links": [realised.as_dict() for realised in self.realised],
            "routes": {
                site_id: [
                    {"to": r.destination, "via": r.via, "dev": r.dev, "src": r.src}
                    for r in routes
                ]
                for site_id, routes in self.plan.routes().items()
            },
            "observed_addresses": self._observed,
            "nodes": {
                node.node_id: {
                    "site": self.profile.site_of(node.node_id),
                    "rpc": "%s:%d" % (self.profile.rpc_host(node.node_id), node.rpc_port),
                    "p2p": "%s:%d" % (self.profile.data_host(node.node_id), node.port),
                }
                for node in self.profile.nodes
            },
        }


# --------------------------------------------------------------------------------------
# small helpers
# --------------------------------------------------------------------------------------


def _import_core():
    """CORE's gRPC client and its wrappers, imported only when a run asks for them."""
    from core.api.grpc import client, wrappers

    return client, wrappers


def _vcmd() -> str:
    path = shutil.which("vcmd")
    if not path:
        raise FabricError(
            "vcmd is not on PATH, so nothing can be run inside a node. It ships with "
            "CORE; this harness expects the project's container."
        )
    return path


def _parse_addresses(output: str) -> Dict[str, List[str]]:
    """``ip -4 -o addr show`` -> ``{interface: [address, ...]}``."""
    found: Dict[str, List[str]] = {}
    for line in (output or "").splitlines():
        parts = line.split()
        if len(parts) >= 4 and parts[2] == "inet":
            found.setdefault(parts[1], []).append(parts[3].split("/")[0])
    return found


__all__ = ["CoreFabric", "DEFAULT_GRPC_ADDRESS"]
