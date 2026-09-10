"""Build a resolved :class:`Topology` from its YAML descriptor.

Resolution means: read the locations, read the links, and give every link a
concrete impairment. A link gets its impairment from one of two places, never
both silently — the named profile when it has one, the physical delay model
otherwise. Which one was used is recorded in ``Link.profile_name`` so the
manifest can report it.
"""

from __future__ import annotations

import logging
from pathlib import Path

from ..config import load_document, load_validated, resolve_path, validate
from ..exit_codes import ConfigError
from ..paths import CONFIG_ROOT
from .models import (
    Bandwidth,
    Delay,
    Impairment,
    LatencyModel,
    Link,
    Location,
    Loss,
    NetworkProfile,
    Queue,
    Topology,
    haversine_km,
)

LOG = logging.getLogger("experiments.topology")

DEFAULT_PROFILE_DIR = CONFIG_ROOT / "network-profiles"


def load_profiles(directory: Path | str | None = None) -> dict[str, NetworkProfile]:
    """Load every ``*.yaml`` profile in a directory, keyed by name.

    The file name and the ``name`` field must agree: a mismatch is a
    configuration error, because a link references the name and an operator
    reads the file name.
    """
    directory = Path(directory) if directory else DEFAULT_PROFILE_DIR
    if not directory.is_dir():
        raise ConfigError("network profile directory not found: %s" % directory)
    profiles: dict[str, NetworkProfile] = {}
    for path in sorted(directory.glob("*.y*ml")):
        data = load_validated(path, "network_profile.schema.json")
        profile = NetworkProfile.from_dict(data)
        if profile.name != path.stem:
            raise ConfigError(
                "profile name %r does not match its file name %r (%s)"
                % (profile.name, path.stem, path)
            )
        profiles[profile.name] = profile
    if not profiles:
        raise ConfigError("no network profile found in %s" % directory)
    LOG.debug("loaded %d network profiles from %s", len(profiles), directory)
    return profiles


def _derive_impairment(
    model: LatencyModel,
    source: Location,
    target: Location,
    *,
    access: bool,
    bandwidth_mbps: float | None,
) -> tuple[Impairment, float | None]:
    """Impairment from the physical model, for links that name no profile."""
    if None in (source.lat, source.lon, target.lat, target.lon):
        raise ConfigError(
            "link %s--%s names no profile and at least one endpoint has no "
            "coordinates, so its delay cannot be derived"
            % (source.id, target.id),
            hint="either give both locations lat/lon or set 'profile' on the link",
        )
    distance = haversine_km(source.lat, source.lon, target.lat, target.lon)
    # No rounding here on purpose: the model value is carried at full float
    # precision and rounded once, at emission. Rounding twice is what makes a
    # re-exported topology drift by a microsecond from the historical file.
    imp = Impairment(
        delay=Delay(mean_ms=model.one_way_ms(distance, access=access)),
        loss=Loss(percent=100.0 * model.loss_fraction(distance, access=access)),
        bandwidth=Bandwidth(mbps=bandwidth_mbps),
        queue=Queue(),
    )
    return imp, distance


def build_topology(
    path: Path | str,
    *,
    profile_dir: Path | str | None = None,
) -> Topology:
    """Load and fully resolve a topology descriptor."""
    path = Path(path)
    data = load_validated(path, "topology.schema.json")
    profiles = load_profiles(profile_dir)
    model = LatencyModel.from_dict(data.get("latency_model"))
    defaults = data.get("defaults") or {}
    bw_hub = defaults.get("bandwidth_hub_mbps", 1000.0)
    bw_leaf = defaults.get("bandwidth_leaf_mbps", 200.0)

    locations = [Location(**node) for node in data["nodes"]]
    by_id = {loc.id: loc for loc in locations}
    if len(by_id) != len(locations):
        seen, dupes = set(), set()
        for loc in locations:
            (dupes if loc.id in seen else seen).add(loc.id)
        raise ConfigError("duplicate location ids in %s: %s" % (path, ", ".join(sorted(dupes))))

    links: list[Link] = []
    for raw in data["links"]:
        src_id, dst_id = raw["source"], raw["target"]
        for endpoint in (src_id, dst_id):
            if endpoint not in by_id:
                raise ConfigError(
                    "link %s--%s references unknown location %r; known: %s"
                    % (src_id, dst_id, endpoint, ", ".join(sorted(by_id)))
                )
        if src_id == dst_id:
            raise ConfigError("self link on %s in %s" % (src_id, path))
        source, target = by_id[src_id], by_id[dst_id]
        kind = raw.get("kind", "backbone")
        access = kind == "access"
        default_profile = defaults.get("access_profile" if access else "backbone_profile")
        profile_name = raw.get("profile") or default_profile
        distance = None

        if profile_name:
            if profile_name not in profiles:
                raise ConfigError(
                    "link %s--%s references unknown network profile %r; known: %s"
                    % (src_id, dst_id, profile_name, ", ".join(sorted(profiles)))
                )
            profile = profiles[profile_name].merged(raw.get("profile_overrides"))
            forward, reverse = profile.forward, profile.reverse
        else:
            capacity = _link_capacity(source, target, bw_hub, bw_leaf)
            derived, distance = _derive_impairment(
                model, source, target, access=access, bandwidth_mbps=capacity
            )
            overrides = raw.get("profile_overrides")
            if overrides:
                base = NetworkProfile(name="derived", forward=derived, reverse=derived)
                profile = base.merged(overrides)
                forward, reverse = profile.forward, profile.reverse
            else:
                forward = reverse = derived
            profile_name = "derived:latency-model"

        links.append(
            Link(
                source=src_id,
                target=dst_id,
                kind=kind,
                profile_name=profile_name,
                impairment_forward=forward,
                impairment_reverse=reverse,
                enabled=bool(raw.get("enabled", True)),
                distance_km=None if distance is None else round(distance, 3),
            )
        )

    topology = Topology(
        name=data["name"],
        description=data.get("description", ""),
        source=data.get("source", ""),
        latency_model=model,
        locations=locations,
        links=links,
        defaults=defaults,
    )
    if topology.name != path.stem:
        LOG.warning(
            "topology name %r differs from file name %r (%s)", topology.name, path.stem, path
        )
    return topology


def _link_capacity(source: Location, target: Location, bw_hub: float, bw_leaf: float) -> float:
    """Bottleneck capacity of a link: the smaller of the two endpoints'."""
    def cap(loc: Location) -> float:
        if loc.bandwidth_up_mbps is not None:
            return float(loc.bandwidth_up_mbps)
        return float(bw_hub if loc.is_hub else bw_leaf)

    return min(cap(source), cap(target))


def load_topology_from_experiment(descriptor: dict, *, base: Path) -> Topology:
    """Resolve the topology referenced by an experiment descriptor."""
    topo_path = resolve_path(descriptor["topology"], base=base)
    profile_dir = descriptor.get("network_profile_dir")
    profile_dir = resolve_path(profile_dir, base=base) if profile_dir else None
    return build_topology(topo_path, profile_dir=profile_dir)


def profile_from_file(path: Path | str) -> NetworkProfile:
    """Load a single profile file (used by ``network apply-profile``)."""
    data = load_document(path)
    validate(data, "network_profile.schema.json", origin=str(path))
    return NetworkProfile.from_dict(data)
