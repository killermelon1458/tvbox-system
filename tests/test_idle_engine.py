import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).parents[1] / "lib"))

from tvbox.idle.config import load_config
from tvbox.idle.engine import IdleEngine, load_inputs
from tvbox.idle.providers import select_provider


CONFIG = """
[global]
enabled = true
stability_delay_seconds = 2
poll_interval_seconds = 0.1
display_status_path = "/unused"
[activity]
pointer_distance_px = 12
pointer_window_ms = 500
device_rescan_seconds = 1
activity_stale_seconds = 5
[providers.desktop]
enabled = true
timeout_seconds = 5
required_sources = ["keyboard", "pointer"]
[providers.kodi]
enabled = false
timeout_seconds = 10
[providers.unknown]
enabled = false
timeout_seconds = 10
"""


class Clock:
    def __init__(self):
        self.value = 100.0

    def __call__(self):
        return self.value

    def advance(self, seconds):
        self.value += seconds


class IdleEngineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.config_path = self.root / "idle.toml"
        self.config_path.write_text(CONFIG)
        self.config = load_config(self.config_path)
        self.clock = Clock()
        self.env = mock.patch.dict(os.environ, {
            "TVBOX_RUNTIME_ROOT": str(self.root / "runtime"),
            "TVBOX_BOOT_ID": "test-boot",
        })
        self.env.start()
        self.runtime = self.root / "runtime"
        self.runtime.mkdir()
        self.engine = IdleEngine(self.config, root=self.runtime,
                                 monotonic=self.clock)

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def inputs(self, application="desktop", generation=0,
               keyboard="healthy", pointer="healthy", transition=None,
               display="connected", observed=None):
        return {
            "stable": {"application": application, "request_id": "stable-1"},
            "observed": observed or {"application": application,
                                     "conflicting_toplevels": []},
            "transition": transition,
            "display": display,
            "activity": {
                "activity_generation": generation,
                "last_activity_monotonic": None,
                "updated_monotonic": self.clock.value,
                "source_health": {"keyboard": keyboard, "pointer": pointer,
                                  "flirc": "missing"},
            },
        }

    def test_timeout_pending_stability_and_only_idle_is_true(self):
        active = self.engine.evaluate(self.inputs())
        self.assertEqual((active["state"], active["idle"]), ("active", False))
        self.clock.advance(5)
        pending = self.engine.evaluate(self.inputs())
        self.assertEqual((pending["state"], pending["idle"]),
                         ("idle-pending", False))
        self.clock.advance(2)
        idle = self.engine.evaluate(self.inputs())
        self.assertEqual((idle["state"], idle["idle"]), ("idle", True))

    def test_late_activity_resets_epoch_to_active(self):
        self.engine.evaluate(self.inputs())
        self.clock.advance(5)
        self.engine.evaluate(self.inputs())
        old_epoch = self.engine.epoch_started
        self.clock.advance(1)
        active = self.engine.evaluate(self.inputs(generation=1))
        self.assertEqual(active["state"], "active")
        self.assertGreater(self.engine.epoch_started, old_epoch)

    def test_provider_change_resets_epoch_and_unsupported_inhibits(self):
        self.engine.evaluate(self.inputs())
        self.clock.advance(4)
        result = self.engine.evaluate(self.inputs(application="youtube"))
        self.assertEqual(result["state"], "inhibited")
        self.assertEqual(result["provider"], "youtube")
        self.assertEqual(result["epoch_started_monotonic"], self.clock.value)

    def test_kodi_is_conservatively_inhibited(self):
        result = self.engine.evaluate(self.inputs(application="kodi"))
        self.assertEqual(result["state"], "inhibited")
        self.assertIn("provider-disabled", result["inhibit_reasons"])

    def test_transition_recovery_disagreement_and_display_fail_safe(self):
        transition = self.engine.evaluate(self.inputs(
            transition={"request_id": "t", "phase": "client-starting"}))
        self.assertEqual(transition["state"], "inhibited")
        recovering = self.engine.evaluate(self.inputs(
            transition={"request_id": "t", "phase": "returning"}))
        self.assertEqual(recovering["state"], "recovering")
        disagreement = self.engine.evaluate(self.inputs(observed={
            "application": "kodi", "process_observed": True,
            "conflicting_toplevels": [],
        }))
        self.assertEqual(disagreement["state"], "degraded")
        absent = self.engine.evaluate(self.inputs(display="disconnected"))
        self.assertEqual(absent["state"], "display-absent")
        self.assertFalse(absent["idle"])

    def test_degraded_activity_source_and_recovery_reset_epoch(self):
        degraded = self.engine.evaluate(self.inputs(pointer="missing"))
        self.assertEqual(degraded["state"], "degraded")
        old_epoch = degraded["epoch_started_monotonic"]
        self.clock.advance(1)
        recovered = self.engine.evaluate(self.inputs())
        self.assertEqual(recovered["state"], "active")
        self.assertGreater(recovered["epoch_started_monotonic"], old_epoch)

    def test_stale_activity_daemon_state_degrades(self):
        inputs = self.inputs()
        inputs["activity"]["updated_monotonic"] = self.clock.value - 10
        result = self.engine.evaluate(inputs)
        self.assertEqual(result["state"], "degraded")
        self.assertIn("activity-state-stale", result["reasons"])

    def test_restart_always_begins_fresh_epoch(self):
        self.engine.evaluate(self.inputs())
        self.clock.advance(8)
        self.engine.evaluate(self.inputs())
        self.clock.advance(1)
        restarted = IdleEngine(self.config, root=self.runtime,
                               monotonic=self.clock)
        result = restarted.evaluate(self.inputs())
        self.assertEqual(result["state"], "active")
        self.assertEqual(result["epoch_started_monotonic"], self.clock.value)

    def test_previous_boot_and_malformed_inputs_rejected(self):
        (self.runtime / "activity-state.json").write_text(json.dumps({
            "schema_version": 1, "boot_id": "old",
            "activity_generation": 9,
        }))
        loaded = load_inputs(self.runtime, "/unused")
        self.assertIsNone(loaded["activity"])
        (self.runtime / "activity-state.json").write_text("{bad")
        loaded = load_inputs(self.runtime, "/unused")
        self.assertIsNone(loaded["activity"])

    def test_unrelated_schedule_state_does_not_reset_epoch(self):
        first = self.engine.evaluate(self.inputs())
        (self.runtime / "screensaver-policy.json").write_text("{}")
        self.clock.advance(1)
        second = self.engine.evaluate(self.inputs())
        self.assertEqual(first["epoch_started_monotonic"],
                         second["epoch_started_monotonic"])

    def test_canonical_state_atomic_mode_and_required_fields(self):
        result = self.engine.evaluate(self.inputs())
        path = self.runtime / "idle-state.json"
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        for field in ("schema_version", "boot_id", "writer_instance_id",
                      "wall_time", "reasons", "inhibit_reasons", "source_health"):
            self.assertIn(field, result)

    def test_provider_contract_and_engine_have_no_action_vocabulary(self):
        provider = select_provider(
            self.inputs()["stable"], self.inputs()["observed"], self.config)
        value = provider.to_dict()
        for forbidden in ("renderer", "schedule", "overlay", "screensaver",
                          "input_profile", "home", "recovery_action"):
            self.assertNotIn(forbidden, value)
        for path in (
            Path(__file__).parents[1] / "lib/tvbox/idle/providers.py",
            Path(__file__).parents[1] / "lib/tvbox/idle/engine.py",
            Path(__file__).parents[1] / "bin/tvbox-idled",
        ):
            source = path.read_text().lower()
            for forbidden in ("tvbox-screensaver", "tvbox-overlay",
                              "request-overlay", "mode-black", "mode-slideshow"):
                self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
