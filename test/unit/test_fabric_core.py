"""The CORE fabric's arithmetic and its flags, without an emulator.

Everything here is what the fabric decides *before* it talks to CORE: the unit
conversions netem wants, the flags that keep each plane on its own address, and the
assertion that catches a peer mesh which has escaped onto the control network. A live
session is a different kind of test and is exercised by an actual run of
``config/profiles/core/smoke.yaml``.

The unit conversions look trivial and are not. CORE takes microseconds, the maps state
milliseconds, and an impairment that is a thousand times too small is a network that looks
healthy and measures nothing.
"""

import signal
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "bootstrap"))

import fabric  # noqa: E402
from config_loader import load_profile  # noqa: E402
from fabric.addressing import CONTROL_PREFIX, IDENTITY_PREFIX  # noqa: E402
from fabric.core import CoreFabric, _bps, _us  # noqa: E402
from fabric.topology import Impairment  # noqa: E402

PROFILES = Path(__file__).resolve().parent.parent / "config" / "profiles" / "core"


class TestUnitConversions(unittest.TestCase):
    def test_delay_is_milliseconds_in_and_microseconds_out(self):
        self.assertEqual(_us(45.8), 45800)
        self.assertEqual(_us(0.02), 20)
        self.assertEqual(_us(0), 0)

    def test_bandwidth_is_megabits_in_and_bits_out(self):
        self.assertEqual(_bps(1000.0), 1_000_000_000)
        self.assertEqual(_bps(10), 10_000_000)

    def test_an_unset_capacity_means_no_shaping(self):
        """CORE reads 0 as "do not shape", which is what an absent `bandwidth` means."""
        self.assertEqual(_bps(None), 0)
        self.assertEqual(_bps(0), 0)


class TestCoreFabricWithoutASession(unittest.TestCase):
    def setUp(self):
        self.profile = load_profile(str(PROFILES / "smoke.yaml"))
        self.fabric = fabric.build(self.profile)

    def test_a_core_profile_selects_the_core_fabric(self):
        self.assertEqual(self.profile.fabric_backend, "core")
        self.assertIsInstance(self.fabric, CoreFabric)
        self.assertEqual(self.fabric.name, "core")

    def test_every_node_resolves_to_its_site(self):
        sites = {n.node_id: self.profile.site_of(n.node_id) for n in self.profile.nodes}
        self.assertEqual(sites["miner-0"], "firenze")
        self.assertEqual(sites["company-0"], "pisa")
        # admin and ca-0 share a site: the addresses match, the ports do not.
        self.assertEqual(sites["admin"], "bologna")
        self.assertEqual(sites["ca-0"], "bologna")
        self.assertEqual(
            self.profile.rpc_host("admin"), self.profile.rpc_host("ca-0")
        )
        self.assertNotEqual(
            self.profile.node("admin").rpc_port, self.profile.node("ca-0").rpc_port
        )

    def test_the_two_planes_are_different_addresses(self):
        for node in self.profile.nodes:
            with self.subTest(node=node.node_id):
                self.assertTrue(
                    self.profile.data_host(node.node_id).startswith(IDENTITY_PREFIX)
                )
                self.assertTrue(
                    self.profile.rpc_host(node.node_id).startswith(CONTROL_PREFIX)
                )

    def test_the_seed_address_is_on_the_data_plane(self):
        """A seed dialled over the control network would build the whole mesh there."""
        seed = self.profile.seed_node_address
        self.assertIn(self.profile.data_host("admin"), seed)
        self.assertNotIn(CONTROL_PREFIX, seed)

    def test_the_daemon_flags_pin_each_plane_to_its_own_address(self):
        args = self.fabric.extra_node_args("miner-0")
        identity = self.profile.data_host("miner-0")
        control = self.profile.rpc_host("miner-0")
        self.assertIn("-bind=%s" % identity, args)
        self.assertIn("-externalip=%s" % identity, args)
        self.assertIn("-discover=0", args)
        self.assertIn("-rpcbind=%s" % control, args)
        # The fabric runs multichain-cli inside the namespace, where the node is on
        # loopback; without this the stop call would have nothing to talk to.
        self.assertIn("-rpcbind=127.0.0.1", args)
        self.assertIn("-rpcallowip=127.0.0.1", args)
        self.assertTrue(any(a.startswith("-rpcallowip=%s" % CONTROL_PREFIX) for a in args))

    def test_nothing_binds_the_peer_listener_to_a_control_address(self):
        for node in self.profile.nodes:
            for arg in self.fabric.extra_node_args(node.node_id):
                if arg.startswith(("-bind=", "-externalip=")):
                    self.assertNotIn(CONTROL_PREFIX, arg)

    def test_wrapping_a_command_before_the_session_exists_is_an_error(self):
        """Better than a prefix naming a directory that is not there yet."""
        with self.assertRaises(fabric.FabricError):
            self.fabric.wrap("miner-0")

    def test_peers_on_the_data_plane_are_accepted(self):
        good = ["%s:7907" % self.profile.data_host(n.node_id) for n in self.profile.nodes]
        self.assertEqual(self.fabric.peers_off_the_data_plane(good), [])

    def test_a_peer_on_the_control_plane_is_reported(self):
        """The failure this exists for: a mesh formed on the unimpaired network would
        finish the run and report numbers describing a network with no delay in it."""
        peers = [
            "%s:7907" % self.profile.data_host("miner-0"),
            "%s:7908" % self.profile.rpc_host("admin"),
        ]
        off = self.fabric.peers_off_the_data_plane(peers)
        self.assertEqual(len(off), 1)
        self.assertIn(CONTROL_PREFIX, off[0])

    def test_stop_is_safe_before_start_and_twice(self):
        self.fabric.stop()
        self.fabric.stop()


try:  # CORE lives in the project's container and nowhere else.
    from core.api.grpc import wrappers as _core_wrappers
except ImportError:  # pragma: no cover - depends on where the suite is run
    _core_wrappers = None


@unittest.skipIf(_core_wrappers is None,
                 "CORE's Python API is not importable here; run inside ./docker/mcsim")
class TestLinkOptions(unittest.TestCase):
    """The numbers that reach netem, for the two kinds of link profile."""

    def setUp(self):
        self.profile = load_profile(str(PROFILES / "smoke.yaml"))
        self.fabric = fabric.build(self.profile)
        self.wrappers = _core_wrappers

    def test_a_derived_link_becomes_microseconds_and_bits(self):
        impairment = Impairment(
            delay_ms=45.8, jitter_ms=6.87, loss_percent=0.15,
            bandwidth_mbps=1000.0, queue_packets=1000,
        )
        options = self.fabric._link_options(impairment, self.wrappers)
        self.assertEqual(options.delay, 45800)
        self.assertEqual(options.jitter, 6870)
        self.assertAlmostEqual(options.loss, 0.15)
        self.assertEqual(options.bandwidth, 1_000_000_000)
        self.assertEqual(options.buffer, 1000)
        self.assertFalse(options.unidirectional)

    def test_an_asymmetric_half_is_marked_unidirectional(self):
        options = self.fabric._link_options(
            Impairment(delay_ms=160.0, jitter_ms=35.0, loss_percent=1.0, bandwidth_mbps=10.0),
            self.wrappers,
            unidirectional=True,
        )
        self.assertTrue(options.unidirectional)
        self.assertEqual(options.delay, 160000)
        self.assertEqual(options.bandwidth, 10_000_000)

    def test_every_link_of_every_shipped_core_profile_converts(self):
        for path in sorted(PROFILES.glob("*.yaml")):
            with self.subTest(profile=path.stem):
                profile = load_profile(str(path))
                built = fabric.build(profile)
                for realised in profile.realised_links():
                    options = built._link_options(realised.forward, self.wrappers)
                    self.assertGreaterEqual(options.delay, 0)
                    self.assertGreater(options.jitter, 0, "netem rejects a distribution "
                                       "with no jitter term")
                    self.assertGreaterEqual(options.loss, 0.0)
                    self.assertLessEqual(options.loss, 100.0)


if __name__ == "__main__":
    unittest.main()
