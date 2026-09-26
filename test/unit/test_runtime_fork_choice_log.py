"""The fork choice has no knob; its per-candidate log is on unless a profile turns it off.

The node always breaks same-height ties on the true sortition score under private
sortition: the score-aware activation lets the argmin propose after a worse-scored block
for its round has arrived, and only the score tie-break turns that second block into the
tip. So there is no control arm to select, and a profile that still says ``fork_score``
is refused rather than silently ignored -- it would believe it measured a baseline that
no longer exists.

What stays configurable is the log (``-debug=wpoafork``), which the analysis reads.
"""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "bootstrap"))

import yaml  # noqa: E402

from config_loader import ConfigError, load_profile  # noqa: E402
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


class TestForkScoreIsGone(unittest.TestCase):
    def test_the_old_key_is_refused(self):
        for value in (True, False):
            with self.subTest(fork_score=value):
                with self.assertRaises(ConfigError):
                    _profile({"fork_score": value})

    def test_the_node_is_never_asked_for_it(self):
        args = _engine_args(_profile(drop=("fork_score_log",)))
        self.assertFalse(any(a.startswith("-enablewpoaforkscore") for a in args))


class TestLog(unittest.TestCase):
    def test_absent_means_on(self):
        profile = _profile(drop=("fork_score_log",))
        self.assertTrue(profile.runtime["fork_score_log"])
        # Without the category the per-candidate lines would not be emitted at all.
        self.assertIn("-debug=wpoafork", _engine_args(profile))

    def test_explicit_false_is_honoured(self):
        profile = _profile({"fork_score_log": False})
        self.assertFalse(profile.runtime["fork_score_log"])
        self.assertNotIn("-debug=wpoafork", _engine_args(profile))

    def test_a_non_boolean_is_refused(self):
        with self.assertRaises(ConfigError):
            _profile({"fork_score_log": "yes"})


class TestShippedProfiles(unittest.TestCase):
    def test_no_shipped_profile_still_carries_the_old_key(self):
        for path in sorted(PROFILES.glob("*/*.yaml")):
            raw = yaml.safe_load(path.read_text(encoding="utf-8"))
            with self.subTest(profile=path.name):
                self.assertNotIn("fork_score", raw.get("runtime") or {})


if __name__ == "__main__":
    unittest.main()
