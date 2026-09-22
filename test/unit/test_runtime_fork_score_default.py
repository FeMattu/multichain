"""``runtime.fork_score`` is on unless a profile turns it off.

The node keeps ``-enablewpoaforkscore`` off by default, and that is correct for
MultiChain: it is an opt-in change of local fork-choice policy. This harness is not
MultiChain — it exists to run the mechanism — so a profile that says nothing gets the
complete stack, exactly as it gets ``-enablewpoa`` and ``-enableweightengine``.

The inversion has one consequence worth a test of its own: a control arm can no longer be
produced by omission. It has to say ``fork_score: false``, which is the right way round —
a measured configuration should be written down, not inherited from a default that may
change.
"""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "bootstrap"))

import yaml  # noqa: E402

from config_loader import load_profile  # noqa: E402
from node_process import NodeRunner  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
PROFILES = ROOT / "config" / "profiles"
BASE = PROFILES / "native" / "small.yaml"


def _profile(runtime_patch=None, drop=()):
    raw = yaml.safe_load(BASE.read_text(encoding="utf-8"))
    runtime = raw.setdefault("runtime", {})
    for key in drop:
        runtime.pop(key, None)
    if runtime_patch:
        runtime.update(runtime_patch)
    tmp = Path(tempfile.mkdtemp()) / "profile.yaml"
    tmp.write_text(yaml.safe_dump(raw), encoding="utf-8")
    return load_profile(str(tmp))


def _engine_args(profile):
    runner = NodeRunner(profile, ROOT.parent, Path(tempfile.mkdtemp()), fabric=object())
    return runner.engine_args()


class TestDefault(unittest.TestCase):
    def test_absent_means_on(self):
        self.assertTrue(_profile(drop=("fork_score",)).runtime["fork_score"])

    def test_explicit_false_is_honoured(self):
        self.assertFalse(_profile({"fork_score": False}).runtime["fork_score"])

    def test_explicit_true_is_honoured(self):
        self.assertTrue(_profile({"fork_score": True}).runtime["fork_score"])

    def test_a_non_boolean_is_still_refused(self):
        from config_loader import ConfigError

        with self.assertRaises(ConfigError):
            _profile({"fork_score": "yes"})


class TestDaemonArguments(unittest.TestCase):
    def test_default_profile_carries_the_mechanism_and_its_log(self):
        args = _engine_args(_profile(drop=("fork_score",)))
        self.assertIn("-enablewpoaforkscore=1", args)
        # Without the category the per-candidate lines would not be emitted at all.
        self.assertIn("-debug=wpoafork", args)

    def test_control_arm_carries_neither_unless_it_asks_for_the_log(self):
        args = _engine_args(_profile({"fork_score": False}))
        self.assertNotIn("-enablewpoaforkscore=1", args)
        self.assertNotIn("-debug=wpoafork", args)

        args = _engine_args(_profile({"fork_score": False, "fork_score_log": True}))
        self.assertNotIn("-enablewpoaforkscore=1", args)
        self.assertIn("-debug=wpoafork", args)


class TestShippedProfiles(unittest.TestCase):
    def test_a_profile_that_says_nothing_gets_the_mechanism(self):
        for path in sorted(PROFILES.glob("*/*.yaml")):
            raw = yaml.safe_load(path.read_text(encoding="utf-8"))
            if "fork_score" in (raw.get("runtime") or {}):
                continue
            with self.subTest(profile=path.name):
                self.assertTrue(load_profile(str(path)).runtime["fork_score"])


if __name__ == "__main__":
    unittest.main()
