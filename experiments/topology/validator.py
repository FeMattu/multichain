"""Structural checks and the end-to-end latency matrix.

Two questions are answered here, and they are the two that decide whether a
run is worth starting:

* is the enabled part of the graph connected, and if not, which components
  does it fall into (a declared partition is legitimate — an accidental one
  is not);
* what is the worst end-to-end one-way delay between two locations, which is
  the number every geographic comparison is indexed on.

Shortest paths are computed on the *delay*, not on the hop count, because that
is what the emulated network will actually do once static routes are installed.
"""

from __future__ import annotations

import heapq
from dataclasses import dataclass
from typing import Iterable

from .models import Link, Topology


@dataclass
class ValidationReport:
    """Outcome of :func:`validate_topology`."""

    errors: list[str]
    warnings: list[str]
    components: list[list[str]]
    rtt_matrix: dict[tuple[str, str], float]
    max_rtt_ms: float
    max_rtt_pair: tuple[str, str] | None

    @property
    def ok(self) -> bool:
        return not self.errors

    @property
    def connected(self) -> bool:
        return len(self.components) <= 1


def _adjacency(topology: Topology) -> dict[str, list[tuple[str, float]]]:
    """Directed adjacency with the one-way delay of that direction as cost.

    A partitioned direction is left out entirely: a link that drops every
    packet is not a path, and treating it as one would make the RTT matrix
    lie about reachability.
    """
    adj: dict[str, list[tuple[str, float]]] = {loc.id: [] for loc in topology.locations}
    for link in topology.enabled_links():
        fwd, rev = link.impairment_forward, link.impairment_reverse
        if not fwd.partition:
            adj[link.source].append((link.target, fwd.delay.mean_ms))
        if not rev.partition:
            adj[link.target].append((link.source, rev.delay.mean_ms))
    return adj


def _dijkstra(adj: dict[str, list[tuple[str, float]]], start: str) -> dict[str, float]:
    dist = {start: 0.0}
    queue: list[tuple[float, str]] = [(0.0, start)]
    while queue:
        cost, node = heapq.heappop(queue)
        if cost > dist.get(node, float("inf")):
            continue
        for neighbour, weight in adj.get(node, ()):
            candidate = cost + weight
            if candidate < dist.get(neighbour, float("inf")):
                dist[neighbour] = candidate
                heapq.heappush(queue, (candidate, neighbour))
    return dist


def shortest_paths(topology: Topology) -> dict[str, dict[str, float]]:
    """One-way shortest-path delay, in ms, from every location to every other."""
    adj = _adjacency(topology)
    return {loc.id: _dijkstra(adj, loc.id) for loc in topology.locations}


def next_hops(topology: Topology) -> dict[str, dict[str, str]]:
    """``next_hops[here][destination] = neighbour`` on the minimum-delay path.

    This is what the netns fabric writes into the routers' routing tables, so
    that the path a packet takes is the path the topology says it takes.
    """
    adj = _adjacency(topology)
    table: dict[str, dict[str, str]] = {}
    for source in adj:
        # Distance from every neighbour to every destination, then pick the
        # neighbour minimising (edge cost + its distance).
        via: dict[str, tuple[float, str]] = {}
        for neighbour, edge_cost in adj[source]:
            dist = _dijkstra(adj, neighbour)
            for destination, cost in dist.items():
                if destination in (source,):
                    continue
                total = edge_cost + cost
                current = via.get(destination)
                if current is None or total < current[0] - 1e-12 or (
                    abs(total - current[0]) <= 1e-12 and neighbour < current[1]
                ):
                    via[destination] = (total, neighbour)
        table[source] = {dest: hop for dest, (_, hop) in via.items()}
    return table


def connected_components(topology: Topology) -> list[list[str]]:
    """Weakly connected components of the enabled, non-partitioned graph."""
    adj = _adjacency(topology)
    undirected: dict[str, set[str]] = {node: set() for node in adj}
    for node, edges in adj.items():
        for neighbour, _ in edges:
            undirected[node].add(neighbour)
            undirected[neighbour].add(node)
    seen: set[str] = set()
    components: list[list[str]] = []
    for node in sorted(undirected):
        if node in seen:
            continue
        stack, component = [node], []
        seen.add(node)
        while stack:
            current = stack.pop()
            component.append(current)
            for neighbour in sorted(undirected[current]):
                if neighbour not in seen:
                    seen.add(neighbour)
                    stack.append(neighbour)
        components.append(sorted(component))
    return components


def validate_topology(
    topology: Topology, *, require_connected: bool = True
) -> ValidationReport:
    """Check the graph and compute its latency matrix."""
    errors: list[str] = []
    warnings: list[str] = []

    seen_pairs: set[frozenset[str]] = set()
    for link in topology.links:
        pair = frozenset(link.key)
        if pair in seen_pairs:
            errors.append("duplicate link %s--%s" % (link.source, link.target))
        seen_pairs.add(pair)

    isolated = [loc.id for loc in topology.locations if not topology.neighbours(loc.id)]
    if isolated:
        warnings.append("locations with no enabled link: %s" % ", ".join(isolated))

    components = connected_components(topology)
    if require_connected and len(components) > 1:
        errors.append(
            "topology is not connected: %d components (%s)"
            % (len(components), " | ".join(",".join(c) for c in components))
        )

    distances = shortest_paths(topology)
    matrix: dict[tuple[str, str], float] = {}
    max_rtt, max_pair = 0.0, None
    ids = topology.location_ids
    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            forward = distances.get(a, {}).get(b)
            reverse = distances.get(b, {}).get(a)
            if forward is None or reverse is None:
                continue
            rtt = forward + reverse
            matrix[(a, b)] = round(rtt, 4)
            if rtt > max_rtt:
                max_rtt, max_pair = rtt, (a, b)

    for link in topology.enabled_links():
        if link.impairment_forward.delay.mean_ms < 0:
            errors.append("negative delay on %s--%s" % link.key)
        for imp, label in ((link.impairment_forward, "forward"), (link.impairment_reverse, "reverse")):
            if imp.loss.percent > 100 or imp.loss.percent < 0:
                errors.append("loss out of range on %s--%s (%s)" % (link.source, link.target, label))

    return ValidationReport(
        errors=errors,
        warnings=warnings,
        components=components,
        rtt_matrix=matrix,
        max_rtt_ms=round(max_rtt, 4),
        max_rtt_pair=max_pair,
    )


def rtt_between(topology: Topology, subset: Iterable[str]) -> float:
    """Worst RTT within a subset of locations (e.g. the miners only)."""
    subset = list(subset)
    distances = shortest_paths(topology)
    worst = 0.0
    for i, a in enumerate(subset):
        for b in subset[i + 1:]:
            fwd = distances.get(a, {}).get(b)
            rev = distances.get(b, {}).get(a)
            if fwd is None or rev is None:
                continue
            worst = max(worst, fwd + rev)
    return round(worst, 4)


def format_matrix(report: ValidationReport, ids: list[str], *, limit: int = 24) -> str:
    """Human-readable RTT matrix, trimmed for the terminal."""
    shown = ids[:limit]
    width = max((len(i) for i in shown), default=4) + 1
    head = " " * width + "".join("%9s" % i[:8] for i in shown)
    lines = [head]
    for a in shown:
        row = ["%-*s" % (width, a[:width - 1])]
        for b in shown:
            if a == b:
                row.append("%9s" % "-")
            else:
                value = report.rtt_matrix.get((a, b)) or report.rtt_matrix.get((b, a))
                row.append("%9s" % ("n/a" if value is None else "%.2f" % value))
        lines.append("".join(row))
    if len(ids) > limit:
        lines.append("... %d more locations not shown" % (len(ids) - limit))
    return "\n".join(lines)
