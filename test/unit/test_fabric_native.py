"""The native fabric answers exactly what the harness used to hardcode.

This is the no-regression contract of the fabric seam, written down. Before the seam
existed, every one of these answers was a literal in a call path: ``profile.host`` in nine
places, an empty prefix implied by calling ``subprocess`` directly, ``os.kill`` in
``NodeRunner.stop``. If any of them changes, a native run stops being the baseline the
CORE runs are compared against, and every figure produced under either regime moves for a
reason nobody chose.
"""

import os
import signal
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "bootstrap"))

import fabric  # noqa: E402
from config_loader import load_profile  # noqa: E402
from fabric.native import NativeFabric  # noqa: E402

PROFILES = Path(__file__).resolve().parent.parent / "config" / "profiles" / "native"


class TestNativeFabric(unittest.TestCase):
    def setUp(self):
        self.profile = load_profile(str(PROFILES / "small.yaml"))
        self.fabric = fabric.build(self.profile)

    def test_a_profile_without_a_fabric_section_is_native(self):
        """The thirteen profiles that predate the fabric must keep working untouched."""
        self.assertEqual(self.profile.fabric_backend, "native")
        self.assertIsInstance(self.fabric, NativeFabric)
        self.assertEqual(self.fabric.name, "native")

    def test_every_node_resolves_to_the_profile_host(self):
        for node in self.profile.nodes:
            with self.subTest(node=node.node_id):
                self.assertEqual(self.profile.rpc_host(node.node_id), self.profile.host)
                self.assertEqual(self.profile.data_host(node.node_id), self.profile.host)

    def test_the_seed_address_is_the_admin_on_the_profile_host(self):
        admin = self.profile.admin
        self.assertEqual(
            self.profile.seed_node_address,
            "%s@%s:%d" % (self.profile.chain_name, self.profile.host, admin.port),
        )

    def test_the_command_prefix_is_empty(self):
        for node in self.profile.nodes:
            self.assertEqual(self.fabric.wrap(node.node_id), [])

    def test_no_extra_daemon_flags(self):
        for node in self.profile.nodes:
            self.assertEqual(self.fabric.extra_node_args(node.node_id), [])

    def test_start_and_stop_do_nothing_and_do_not_raise(self):
        self.fabric.start()
        self.fabric.stop()
        self.fabric.stop()  # teardown runs in a finally and may run twice

    def test_signal_reaches_a_process_in_this_namespace(self):
        child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
        try:
            self.fabric.signal("admin", child.pid, signal.SIGTERM)
            self.assertIsNotNone(child.wait(timeout=10))
        finally:
            if child.poll() is None:  # pragma: no cover - only on a failed signal
                child.kill()
                child.wait(timeout=5)

    def test_describe_names_every_node_and_says_there_is_no_emulation(self):
        described = self.fabric.describe()
        self.assertEqual(described["backend"], "native")
        self.assertIsNone(described["emulation"])
        self.assertEqual(set(described["nodes"]), {n.node_id for n in self.profile.nodes})
        for node in self.profile.nodes:
            entry = described["nodes"][node.node_id]
            self.assertEqual(entry["rpc"], "%s:%d" % (self.profile.host, node.rpc_port))
            self.assertEqual(entry["p2p"], "%s:%d" % (self.profile.host, node.port))

    def test_the_manifest_records_the_regime(self):
        """A result whose regime has to be inferred from the profile name is not
        evidence."""
        self.assertEqual(self.profile.manifest()["fabric"]["backend"], "native")


class TestBackendSelection(unittest.TestCase):
    def test_an_unknown_backend_is_refused_by_name(self):
        profile = load_profile(str(PROFILES / "small.yaml"))
        profile.fabric = {"backend": "carrier-pigeon"}
        with self.assertRaises(fabric.FabricError) as caught:
            fabric.build(profile)
        self.assertIn("carrier-pigeon", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
