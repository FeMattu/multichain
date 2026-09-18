"""The map, the physical delay model, the routing and the address plan.

The check points in :class:`TestPublishedCheckPoints` are the reason this file exists.
They are the routes the delay model was validated against, and they are what makes a
regional run and an intercontinental run comparable: a change that moves them is a change
to the meaning of every figure produced under either. If one of them fails, the model has
been altered, and that is a decision to be taken deliberately rather than a test to be
updated.
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "bootstrap"))

from fabric.addressing import (  # noqa: E402
    CONTROL_PREFIX,
    IDENTITY_PREFIX,
    AddressPlan,
)
from fabric.topology import (  # noqa: E402
    Link,
    Site,
    TopologyError,
    great_circle_km,
    load_link_profile,
    load_topology,
)

CONFIG = Path(__file__).resolve().parent.parent / "config"
TOPOLOGIES = CONFIG / "topologies"
NETWORK_PROFILES = CONFIG / "network-profiles"

SHIPPED = ("regional", "national", "continental", "intercontinental", "smoke-4n")


def _site(name, lat, lon, kind="hub"):
    return Site(id=name, kind=kind, lat=lat, lon=lon)


class TestPublishedCheckPoints(unittest.TestCase):
    """The routes the model was validated against, distance and RTT."""

    MILAN = _site("milan", 45.4642, 9.19)
    ROME = _site("rome", 41.9028, 12.4964)
    MADRID = _site("madrid", 40.4168, -3.7038)
    NEW_YORK = _site("new-york", 40.7128, -74.006)

    #: (a, b, published distance km, published RTT ms)
    #:
    #: A fourth row, "Bologna-Geneva 840 km / 12.8 ms", was published alongside these and
    #: is NOT reproduced here: the great-circle distance between those two cities is
    #: 448.5 km, which the model turns into 7.3 ms. The published pair is internally
    #: inconsistent — 840 km is very nearly the two-hop path through Milan — so pinning
    #: it would pin an error. The three below reproduce to better than 0.1 ms.
    CHECK_POINTS = (
        ("Milan-Rome", MILAN, ROME, 477.0, 7.7),
        ("Milan-Madrid", MILAN, MADRID, 1188.0, 17.6),
        ("Milan-New York", MILAN, NEW_YORK, 6464.0, 91.5),
    )

    def _model(self):
        topology = load_topology(TOPOLOGIES / "regional.yaml")
        return topology.latency_model

    def test_distances(self):
        for label, a, b, distance, _ in self.CHECK_POINTS:
            with self.subTest(route=label):
                # 1% of the published figure: the published values are rounded to the
                # kilometre from coordinates quoted to four decimals.
                self.assertAlmostEqual(
                    great_circle_km(a, b), distance, delta=distance * 0.01,
                    msg="%s distance drifted" % label,
                )

    def test_round_trip_times(self):
        model = self._model()
        for label, a, b, _, rtt in self.CHECK_POINTS:
            with self.subTest(route=label):
                one_way = (
                    model["propagation_ms_per_km"]
                    * great_circle_km(a, b)
                    * model["routing_factor"]
                    + model["overhead_backbone_ms"]
                )
                self.assertAlmostEqual(
                    2 * one_way, rtt, delta=0.2, msg="%s RTT drifted" % label
                )

    def test_backbone_loss_matches_the_continental_profile(self):
        """0.02% + 2e-5 %/km over the worst continental hop is the shipped 0.048%."""
        topology = load_topology(TOPOLOGIES / "continental.yaml")
        frankfurt_madrid = topology.distance_km("frankfurt", "madrid")
        self.assertAlmostEqual(frankfurt_madrid, 1420.0, delta=30.0)
        loss = topology.derived_loss_percent(Link("frankfurt", "madrid", "backbone"))
        shipped = load_link_profile(NETWORK_PROFILES / "continental.yaml")
        self.assertAlmostEqual(loss, shipped.forward.loss_percent, delta=0.002)


class TestDerivation(unittest.TestCase):
    def setUp(self):
        self.topology = load_topology(TOPOLOGIES / "regional.yaml")

    def test_access_links_carry_the_larger_overhead(self):
        """An access hop pays 1.0 ms, a backbone hop 0.5 ms, at the same distance."""
        a, b = "firenze", "pisa"
        access = self.topology.derived_delay_ms(Link(a, b, "access"))
        backbone = self.topology.derived_delay_ms(Link(a, b, "backbone"))
        self.assertAlmostEqual(access - backbone, 0.5, places=6)

    def test_access_loss_is_constant_backbone_loss_grows(self):
        near = self.topology.derived_loss_percent(Link("firenze", "prato", "backbone"))
        far = self.topology.derived_loss_percent(Link("firenze", "imperia", "backbone"))
        self.assertLess(near, far)
        for pair in (("pisa", "firenze"), ("rimini", "bologna")):
            self.assertAlmostEqual(
                self.topology.derived_loss_percent(Link(*pair, "access")), 0.04, places=6
            )

    def test_bandwidth_follows_the_link_kind(self):
        self.assertEqual(
            self.topology.derived_bandwidth_mbps(Link("firenze", "genova", "backbone")), 1000.0
        )
        self.assertEqual(
            self.topology.derived_bandwidth_mbps(Link("pisa", "firenze", "access")), 200.0
        )

    def test_derived_jitter_is_a_declared_fraction_of_the_delay(self):
        realised = self.topology.derive(Link("firenze", "genova", "backbone"))
        self.assertAlmostEqual(
            realised.forward.jitter_ms, realised.forward.delay_ms * 0.15, places=6
        )
        self.assertEqual(realised.forward.origin, "derived:latency-model")

    def test_derived_jitter_has_a_floor(self):
        """A 0.2 ms hop must still carry a jitter term: netem rejects a distribution
        without one."""
        topology = load_topology(TOPOLOGIES / "smoke-4n.yaml")
        close = Site(id="a", kind="leaf", lat=43.7696, lon=11.2558)
        topology.sites["a"] = close
        topology.sites["b"] = Site(id="b", kind="leaf", lat=43.7697, lon=11.2559)
        topology.order.extend(["a", "b"])
        realised = topology.derive(Link("a", "b", "access"))
        self.assertGreaterEqual(realised.forward.jitter_ms, 0.02)


class _WritesYaml:
    """A throwaway YAML file, cleaned up with the test.

    ``TestCase.enterContext`` would be the idiom, but it arrived in Python 3.11 and the
    container runs 3.10.
    """

    def _write(self, body):
        import tempfile

        handle = tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False)
        handle.write(body)
        handle.close()
        path = Path(handle.name)
        self.addCleanup(lambda: path.unlink(missing_ok=True))
        return path


class TestLinkProfiles(_WritesYaml, unittest.TestCase):
    def test_every_shipped_profile_loads(self):
        for path in sorted(NETWORK_PROFILES.glob("*.yaml")):
            with self.subTest(profile=path.stem):
                profile = load_link_profile(path)
                self.assertEqual(profile.name, path.stem)
                self.assertEqual(profile.forward.origin, "profile:%s" % path.stem)

    def test_degraded_is_asymmetric_and_the_two_directions_differ(self):
        profile = load_link_profile(NETWORK_PROFILES / "degraded.yaml")
        self.assertIsNotNone(profile.reverse)
        self.assertEqual(profile.forward.delay_ms, 120.0)
        self.assertEqual(profile.reverse.delay_ms, 160.0)
        self.assertEqual(profile.forward.bandwidth_mbps, 100.0)
        self.assertEqual(profile.reverse.bandwidth_mbps, 10.0)

    def test_partitioned_drops_everything_and_says_so(self):
        profile = load_link_profile(NETWORK_PROFILES / "partitioned.yaml")
        self.assertTrue(profile.partition)
        self.assertEqual(profile.forward.loss_percent, 100.0)

    def test_the_symmetric_profiles_are_symmetric(self):
        for name in ("lan", "regional", "national", "continental", "intercontinental"):
            with self.subTest(profile=name):
                self.assertIsNone(load_link_profile(NETWORK_PROFILES / ("%s.yaml" % name)).reverse)

    def test_a_half_declared_asymmetric_profile_is_rejected(self):
        path = self._write("name: half\nforward:\n  delay:\n    mean_ms: 1\n")
        with self.assertRaises(TopologyError) as caught:
            load_link_profile(path)
        self.assertIn("both", str(caught.exception))


class TestShippedTopologies(unittest.TestCase):
    def test_all_load_and_are_connected(self):
        for name in SHIPPED:
            with self.subTest(topology=name):
                topology = load_topology(TOPOLOGIES / ("%s.yaml" % name))
                self.assertEqual(topology.name, name)
                # next_hops() raises on an unreachable site; reaching here proves the map
                # is connected, which is what makes every placed node able to join.
                hops = topology.next_hops()
                self.assertEqual(len(hops), len(topology.sites))
                for site_id, table in hops.items():
                    self.assertEqual(len(table), len(topology.sites) - 1)

    def test_the_four_levels_are_twenty_sites_with_seven_hubs(self):
        for name in ("regional", "national", "continental", "intercontinental"):
            with self.subTest(topology=name):
                topology = load_topology(TOPOLOGIES / ("%s.yaml" % name))
                self.assertEqual(len(topology.sites), 20)
                self.assertEqual(sum(1 for s in topology.sites.values() if s.is_hub), 7)

    def test_the_levels_are_ordered_by_worst_path(self):
        """The geography axis must actually be an axis: each level's worst path is
        slower than the one below it, or the four runs measure the same thing."""
        worst = [
            load_topology(TOPOLOGIES / ("%s.yaml" % name)).worst_path_delay_ms
            for name in ("regional", "national", "continental", "intercontinental")
        ]
        self.assertEqual(worst, sorted(worst))
        self.assertLess(worst[0], 10.0)
        self.assertGreater(worst[3], 50.0)

    def test_no_shipped_map_mentions_a_retired_suite(self):
        """Constraint, not taste: the emulator these maps came from is gone, and a
        pointer into it would be the one trace of it left in the tree."""
        for path in sorted(TOPOLOGIES.glob("*.yaml")) + sorted(NETWORK_PROFILES.glob("*.yaml")):
            with self.subTest(path=path.name):
                text = path.read_text(encoding="utf-8").lower()
                for forbidden in ("shadow", "legacy_gml", "gml_id"):
                    self.assertNotIn(forbidden, text)

    def test_no_shipped_config_carries_a_prose_field(self):
        """`description` and `source` were dropped everywhere. They are checked at the
        top level only: `source` is also a link's endpoint, which is structural."""
        import yaml as _yaml
        for path in sorted(TOPOLOGIES.glob("*.yaml")) + sorted(NETWORK_PROFILES.glob("*.yaml")):
            with self.subTest(path=path.name):
                raw = _yaml.safe_load(path.read_text(encoding="utf-8"))
                self.assertNotIn("description", raw)
                self.assertNotIn("source", raw)
                self.assertNotIn("direction", raw)


class TestTopologyRejections(_WritesYaml, unittest.TestCase):
    def _load(self, body):
        return load_topology(self._write(body))

    HEAD = (
        "name: t\n"
        "latency_model: {propagation_ms_per_km: 0.005, routing_factor: 1.4,\n"
        "  overhead_backbone_ms: 0.5, overhead_access_ms: 1.0, loss_access: 0.0004,\n"
        "  loss_backbone_base: 0.0002, loss_backbone_per_km: 2.0e-07}\n"
        "defaults: {bandwidth_hub_mbps: 1000.0, bandwidth_leaf_mbps: 200.0}\n"
    )

    def test_an_unreachable_site_is_rejected(self):
        with self.assertRaises(TopologyError) as caught:
            self._load(
                self.HEAD
                + "nodes:\n"
                "- {id: a, kind: hub, lat: 1.0, lon: 1.0}\n"
                "- {id: b, kind: leaf, lat: 2.0, lon: 2.0}\n"
                "- {id: c, kind: leaf, lat: 3.0, lon: 3.0}\n"
                "links:\n- {source: a, target: b, kind: access}\n"
            )
        self.assertIn("cannot reach", str(caught.exception))

    def test_a_duplicate_cable_is_rejected(self):
        with self.assertRaises(TopologyError) as caught:
            self._load(
                self.HEAD
                + "nodes:\n"
                "- {id: a, kind: hub, lat: 1.0, lon: 1.0}\n"
                "- {id: b, kind: leaf, lat: 2.0, lon: 2.0}\n"
                "links:\n"
                "- {source: a, target: b, kind: access}\n"
                "- {source: b, target: a, kind: backbone}\n"
            )
        self.assertIn("duplicate link", str(caught.exception))

    def test_a_link_to_an_unknown_site_is_rejected(self):
        with self.assertRaises(TopologyError) as caught:
            self._load(
                self.HEAD
                + "nodes:\n- {id: a, kind: hub, lat: 1.0, lon: 1.0}\n"
                "links:\n- {source: a, target: nowhere, kind: access}\n"
            )
        self.assertIn("nowhere", str(caught.exception))

    def test_a_site_without_coordinates_is_rejected(self):
        with self.assertRaises(TopologyError) as caught:
            self._load(
                self.HEAD
                + "nodes:\n"
                "- {id: a, kind: hub, lat: 1.0, lon: 1.0}\n"
                "- {id: b, kind: leaf}\n"
                "links:\n- {source: a, target: b, kind: access}\n"
            )
        self.assertIn("lat", str(caught.exception))

    def test_an_unknown_top_level_key_is_rejected(self):
        with self.assertRaises(TopologyError) as caught:
            self._load(
                self.HEAD
                + "description: a prose field that was deliberately removed\n"
                "nodes:\n- {id: a, kind: hub, lat: 1.0, lon: 1.0}\n"
                "links: []\n"
            )
        self.assertIn("description", str(caught.exception))


class TestAddressPlan(unittest.TestCase):
    def setUp(self):
        self.topology = load_topology(TOPOLOGIES / "regional.yaml")
        self.plan = AddressPlan(self.topology)

    def test_every_site_has_a_distinct_identity_and_control_address(self):
        identities = {self.plan.identity(s) for s in self.topology.order}
        controls = {self.plan.control(s) for s in self.topology.order}
        self.assertEqual(len(identities), len(self.topology.order))
        self.assertEqual(len(controls), len(self.topology.order))
        first = self.topology.order[0]
        self.assertEqual(self.plan.identity(first), "%s.1" % IDENTITY_PREFIX)
        self.assertEqual(self.plan.control(first), "%s.1" % CONTROL_PREFIX)

    def test_the_plan_is_a_pure_function_of_the_map(self):
        again = AddressPlan(load_topology(TOPOLOGIES / "regional.yaml"))
        self.assertEqual(self.plan.as_dict(), again.as_dict())

    def test_every_cable_gets_its_own_thirty(self):
        prefixes = {cable.source_ip.rsplit(".", 1)[0] for cable in self.plan.links}
        self.assertEqual(len(prefixes), len(self.topology.links))
        for cable in self.plan.links:
            self.assertEqual(cable.prefix_len, 30)
            self.assertNotEqual(cable.source_ip, cable.target_ip)

    def test_interfaces_are_numbered_from_zero_per_site(self):
        for site_id in self.topology.order:
            names = [cable.near_iface(site_id) for cable in self.plan.links_of(site_id)]
            self.assertEqual(names, ["eth%d" % i for i in range(len(names))])

    def test_routes_reach_every_other_site_through_a_real_neighbour(self):
        routes = self.plan.routes()
        for site_id, entries in routes.items():
            with self.subTest(site=site_id):
                self.assertEqual(len(entries), len(self.topology.order) - 1)
                neighbour_addresses = {
                    cable.far_end(site_id) for cable in self.plan.links_of(site_id)
                }
                destinations = set()
                for route in entries:
                    self.assertIn(route.via, neighbour_addresses)
                    self.assertEqual(route.src, self.plan.identity(site_id))
                    self.assertTrue(route.destination.endswith("/32"))
                    destinations.add(route.destination)
                self.assertEqual(len(destinations), len(entries))
                self.assertNotIn(
                    self.plan.site(site_id).identity_cidr, destinations,
                    "a site must not hold a route to itself",
                )

    def test_a_leaf_reaches_a_distant_leaf_through_its_hub(self):
        routes = {r.destination: r for r in self.plan.routes()["pisa"]}
        target = self.plan.site("ravenna").identity_cidr
        firenze = self.plan.link_between("pisa", "firenze")
        self.assertEqual(routes[target].via, firenze.far_end("pisa"))


class TestRealisation(unittest.TestCase):
    def setUp(self):
        self.topology = load_topology(TOPOLOGIES / "regional.yaml")

    def test_without_a_profile_every_link_is_derived(self):
        for realised in self.topology.realise():
            self.assertEqual(realised.forward.origin, "derived:latency-model")

    def test_a_profile_overrides_rather_than_adds(self):
        profile = load_link_profile(NETWORK_PROFILES / "intercontinental.yaml")
        for realised in self.topology.realise(profile):
            self.assertEqual(realised.forward.origin, "profile:intercontinental")
            self.assertEqual(realised.forward.delay_ms, 45.8)

    def test_apply_to_selects_the_links_it_names(self):
        profile = load_link_profile(NETWORK_PROFILES / "partitioned.yaml")
        realised = self.topology.realise(profile, apply_to="access")
        kinds = {r.link.kind: r.forward.origin for r in realised}
        self.assertEqual(kinds["access"], "profile:partitioned")
        self.assertEqual(kinds["backbone"], "derived:latency-model")

    def test_an_unknown_apply_to_is_rejected(self):
        with self.assertRaises(TopologyError):
            self.topology.realise(
                load_link_profile(NETWORK_PROFILES / "lan.yaml"), apply_to="hubs"
            )


if __name__ == "__main__":
    unittest.main()
