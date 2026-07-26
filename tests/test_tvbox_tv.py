from dataclasses import replace
import fcntl
import importlib.util
from importlib.machinery import SourceFileLoader
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock


SOURCE = Path(__file__).parents[1] / "bin/tvbox-tv"
SPEC = importlib.util.spec_from_loader(
    "tvbox_tv", SourceFileLoader("tvbox_tv", str(SOURCE)),
)
assert SPEC and SPEC.loader
tv = importlib.util.module_from_spec(SPEC)
sys.modules["tvbox_tv"] = tv
SPEC.loader.exec_module(tv)


def status(**changes):
    base = tv.TVStatus(
        "2026-07-26T00:00:00-05:00", "on", "connected", "enabled", "On",
        "on", "1.0.0.0", 4, "1.0.0.0", True,
        ["drm_connected", "cec_power_on", "cec_playback_ready"],
    )
    return replace(base, **changes)


class ParsingTests(unittest.TestCase):
    def test_power_states(self):
        for expected in ("on", "standby", "to-on", "to-standby"):
            self.assertEqual(tv.parse_power(f"pwr-state: {expected} (0x00)"), expected)
        self.assertEqual(tv.parse_power("Tx, Not Acknowledged"), "unknown")

    def test_adapter_identity(self):
        text = """
Physical Address           : 1.0.0.0
Logical Address            : 4 (Playback Device 1)
"""
        self.assertEqual(tv.parse_adapter(text), ("1.0.0.0", 4))
        self.assertEqual(tv.parse_adapter("Logical Address: Not Allocated"), ("unknown", None))

    def test_active_source(self):
        text = "ACTIVE_SOURCE (0x82):\n  phys-addr: 1.0.0.0"
        self.assertEqual(tv.parse_active_source(text), "1.0.0.0")
        self.assertEqual(tv.parse_active_source("Rx, Timeout"), "unknown")


class ClassificationTests(unittest.TestCase):
    def classify(self, drm="connected", enabled="enabled", dpms="On",
                 power="on", physical="1.0.0.0", logical=4):
        return tv.classify(drm, enabled, dpms, power, physical, logical)[0]

    def test_on_requires_combined_readiness(self):
        self.assertEqual(self.classify(), "on")
        self.assertEqual(self.classify(physical="f.f.f.f", logical=None), "transitioning")

    def test_standby_and_transitions(self):
        self.assertEqual(self.classify(power="standby"), "standby")
        self.assertEqual(self.classify(power="to-on"), "transitioning")
        self.assertEqual(self.classify(power="to-standby"), "transitioning")

    def test_unavailable_and_unknown(self):
        self.assertEqual(
            self.classify(drm="disconnected", enabled="disabled", dpms="Off",
                          power="unknown", physical="unknown", logical=None),
            "unavailable",
        )
        self.assertEqual(self.classify(power="unknown"), "unknown")


class ActivationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old_state = tv.STATE_DIR
        self.old_marker = tv.ACTIVE_MARKER
        tv.STATE_DIR = Path(self.tmp.name)
        tv.ACTIVE_MARKER = tv.STATE_DIR / "tv-active-source.json"

    def tearDown(self):
        tv.STATE_DIR = self.old_state
        tv.ACTIVE_MARKER = self.old_marker
        self.tmp.cleanup()

    @mock.patch.object(tv, "send_active_source")
    @mock.patch.object(tv, "send_image_view_on")
    @mock.patch.object(tv, "observe_status")
    def test_already_active_is_strict_noop(self, observe, wake, active):
        observe.return_value = status()
        self.assertEqual(tv.activate(), 0)
        wake.assert_not_called()
        active.assert_not_called()

    @mock.patch.object(tv, "send_active_source")
    @mock.patch.object(tv, "send_image_view_on")
    @mock.patch.object(tv, "observe_status")
    def test_active_source_waits_for_playback_address(self, observe, wake, active):
        transitioning = status(
            state="transitioning", physical_address="f.f.f.f",
            logical_address=None, active_source="unknown", active=None,
        )
        observe.side_effect = [transitioning, transitioning, status(active=False), status()]
        wake.return_value = tv.CommandResult(True, 0, "Tx, OK", "")
        active.return_value = tv.CommandResult(True, 0, "Tx, OK", "")
        with mock.patch.object(tv.time, "sleep", return_value=None):
            self.assertEqual(tv.activate(), 0)
        active.assert_called_once()

    @mock.patch.object(tv, "observe_status")
    def test_repeated_activation_is_coalesced(self, observe):
        lock_path = tv.STATE_DIR / "tv-activate.lock"
        with lock_path.open("a") as held:
            fcntl.flock(held, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.assertEqual(tv.activate(), 0)
        observe.assert_not_called()

    def test_active_marker_is_volatile_local_evidence(self):
        self.assertFalse(tv.read_active_marker())
        tv.write_active_marker()
        self.assertTrue(tv.read_active_marker())
        tv.clear_active_marker()
        self.assertFalse(tv.read_active_marker())

    @mock.patch.object(tv, "send_active_source")
    @mock.patch.object(tv, "send_image_view_on")
    @mock.patch.object(tv, "observe_status")
    def test_timeout_never_sends_active_source(self, observe, wake, active):
        observe.return_value = status(
            state="transitioning", physical_address="f.f.f.f",
            logical_address=None, active_source="unknown", active=None,
        )
        wake.return_value = tv.CommandResult(True, 0, "Tx, OK", "")
        old_timeout = tv.ACTIVATE_TIMEOUT
        tv.ACTIVATE_TIMEOUT = 0
        try:
            self.assertEqual(tv.activate(), 1)
        finally:
            tv.ACTIVATE_TIMEOUT = old_timeout
        active.assert_not_called()


if __name__ == "__main__":
    unittest.main()
