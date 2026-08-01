from datetime import datetime
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest import mock
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).parents[1] / "lib"))

from tvbox.screensaver.policy import ScreensaverPolicy
from tvbox.screensaver.idle_watch import IdleStateWatcher


CONFIG = """
[screensaver]
default_mode = "slideshow"
timezone = "America/Chicago"
output = "0"

[[screensaver.schedule]]
start = "00:00"
end = "08:00"
mode = "black"

[slideshow]
image_directory = "/tmp/pictures"
recursive = true
image_duration = 5
fit_mode = "contain"
shuffle = false
"""


class FakePolicy(ScreensaverPolicy):
    def __init__(self, *args, **kwargs):
        self.fake_requests = {}
        self.fake_active = None
        self.next_generation = 0
        self.request_messages = []
        self.release_messages = []
        super().__init__(*args, **kwargs)

    def overlay(self, message):
        command = message["command"]
        if command == "request":
            self.request_messages.append(message.copy())
            self.next_generation += 1
            token = f"{self.next_generation:032x}"
            item = {
                "request_id": token, "generation": self.next_generation,
                "renderer": message["renderer"], "state": "active",
                "ready": True, "degradation": None,
            }
            old = message.get("replace_token")
            self.fake_requests[token] = item
            self.fake_active = item
            if old:
                self.fake_requests.pop(old, None)
            return {"ok": True, "request_id": token,
                    "generation": self.next_generation, "state": "starting"}
        if command == "status":
            return {"ok": True, "status": {
                "active_request": self.fake_active,
                "requests": list(self.fake_requests.values()),
            }}
        if command == "release":
            self.release_messages.append(message.copy())
            if message["request_id"] not in self.fake_requests:
                return {"ok": False, "error": "stale"}
            self.fake_requests.pop(message["request_id"])
            self.fake_active = None
            return {"ok": True}
        if command == "renew":
            return {"ok": message["request_id"] in self.fake_requests}
        raise AssertionError(command)


class PolicyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.config = self.root / "screensaver.toml"
        self.config.write_text(CONFIG)
        self.zone = ZoneInfo("America/Chicago")
        self.current = datetime(2026, 7, 15, 12, 0, tzinfo=self.zone)
        self.env = mock.patch.dict(os.environ, {
            "TVBOX_RUNTIME_ROOT": str(self.root),
            "TVBOX_BOOT_ID": "test-boot",
        })
        self.env.start()
        self.policy = FakePolicy(
            self.config, root=self.root, now=lambda: self.current)

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def write_idle(self, state="idle", idle=True, epoch=10.0,
                   boot="test-boot", schema=1, age=0.0,
                   health=None, writer="idle-writer"):
        value = {
            "schema_version": schema, "boot_id": boot,
            "writer_instance_id": writer, "provider": "desktop",
            "epoch_started_monotonic": epoch,
            "updated_monotonic": time.monotonic() - age,
            "state": state, "idle": idle, "confidence": "high",
            "source_health": health or {
                "activity": "healthy", "application_state": "healthy",
                "provider": "healthy",
            },
        }
        (self.root / "idle-state.json").write_text(
            __import__("json").dumps(value))
        return value

    def test_manual_start_and_exact_stop(self):
        status = self.policy.start()
        self.assertEqual(status["active_mode"], "slideshow")
        token = status["active_request_id"]
        self.assertEqual(self.policy.fake_active["request_id"], token)
        self.policy.stop()
        self.assertIsNone(self.policy.active_token)

    def test_daemon_shutdown_releases_token_but_preserves_intent(self):
        self.policy.start()
        self.policy.shutdown()
        self.assertTrue(self.policy.active_requested)
        self.assertIsNone(self.policy.active_token)
        restored = FakePolicy(
            self.config, root=self.root, now=lambda: self.current)
        self.assertTrue(restored.active_requested)

    def test_manual_black_slideshow_and_scheduled(self):
        self.policy.start()
        self.policy.set_mode("black")
        self.assertEqual(self.policy.active_mode, "black")
        self.policy.set_mode("slideshow")
        self.assertEqual(self.policy.active_mode, "slideshow")
        self.current = datetime(2026, 7, 16, 1, 0, tzinfo=self.zone)
        self.policy.set_mode("scheduled")
        self.assertEqual(self.policy.active_mode, "black")
        self.assertIsNone(self.policy.manual_override)

    def test_active_schedule_boundary_replaces_without_inactive_state(self):
        self.policy.start()
        old = self.policy.active_token
        self.current = datetime(2026, 7, 16, 0, 0, tzinfo=self.zone)
        self.policy.tick()
        self.assertEqual(self.policy.active_mode, "black")
        self.assertNotEqual(self.policy.active_token, old)
        self.assertIsNotNone(self.policy.fake_active)

    def test_reload_changes_effective_mode(self):
        self.policy.start()
        self.config.write_text(CONFIG.replace(
            'default_mode = "slideshow"', 'default_mode = "black"'))
        self.policy.reload()
        self.assertEqual(self.policy.active_mode, "black")

    def test_stale_invalidation_cannot_stop_current(self):
        self.policy.start()
        with self.assertRaises(RuntimeError):
            self.policy.invalidate("f" * 32)
        self.assertIsNotNone(self.policy.active_token)

    def test_manager_restart_reissues_requested_overlay(self):
        self.policy.start()
        old = self.policy.active_token
        self.policy.fake_requests.clear()
        self.policy.fake_active = None
        self.policy.tick()
        self.assertTrue(self.policy.active_requested)
        self.assertNotEqual(self.policy.active_token, old)

    def test_starting_request_is_not_reissued(self):
        self.policy.start()
        token = self.policy.active_token
        self.policy.fake_active = None
        self.policy.fake_requests[token]["state"] = "starting"
        self.policy.tick()
        self.assertEqual(self.policy.active_token, token)
        self.assertEqual(self.policy.next_generation, 1)

    def test_policy_restart_restores_manual_intent(self):
        self.policy.set_mode("black")
        self.policy.start()
        restarted = FakePolicy(
            self.config, root=self.root, now=lambda: self.current)
        self.assertTrue(restarted.active_requested)
        self.assertEqual(restarted.manual_override, "black")

    def test_policy_does_not_mutate_application_or_idle_state(self):
        source = (Path(__file__).parents[1] /
                  "lib/tvbox/screensaver/policy.py").read_text()
        for forbidden in ("active-context", "idle-reset", "tvboxctl",
                          "tvbox-inputctl"):
            self.assertNotIn(forbidden, source)

    def test_tick_retains_old_token_when_replacement_fails(self):
        self.policy.start()
        old = self.policy.active_token
        self.current = datetime(2026, 7, 16, 1, 0, tzinfo=self.zone)
        with mock.patch.object(
                self.policy, "replace_if_needed",
                side_effect=RuntimeError("replacement failed")):
            self.policy.tick()
        self.assertEqual(self.policy.active_token, old)
        self.assertEqual(self.policy.last_error, "replacement failed")

    def test_valid_idle_starts_exactly_one_automatic_request(self):
        self.write_idle()
        self.policy.tick()
        token = self.policy.active_token
        self.assertEqual(self.policy.activation_source, "automatic")
        self.assertEqual(len(self.policy.request_messages), 1)
        self.policy.tick()
        self.assertEqual(self.policy.active_token, token)
        self.assertEqual(len(self.policy.request_messages), 1)

    def test_nonidle_and_fail_safe_states_never_activate(self):
        cases = (
            ("active", False), ("idle-pending", False),
            ("inhibited", False), ("degraded", False),
            ("unknown", False), ("display-absent", False),
            ("recovering", False),
        )
        for state, idle in cases:
            with self.subTest(state=state):
                self.write_idle(state=state, idle=idle)
                self.policy.tick()
                self.assertIsNone(self.policy.active_token)
        self.assertEqual(len(self.policy.request_messages), 0)

    def test_invalid_idle_records_fail_safe_and_release_automatic(self):
        self.write_idle()
        self.policy.tick()
        token = self.policy.active_token
        invalid_writers = (
            lambda: (self.root / "idle-state.json").unlink(),
            lambda: (self.root / "idle-state.json").write_text("{"),
            lambda: self.write_idle(schema=99),
            lambda: self.write_idle(boot="old-boot"),
            lambda: self.write_idle(age=10),
            lambda: self.write_idle(health={
                "activity": "degraded", "application_state": "healthy",
                "provider": "healthy"}),
        )
        for index, make_invalid in enumerate(invalid_writers):
            with self.subTest(index=index):
                if not self.policy.active_token:
                    self.write_idle(epoch=20.0 + index)
                    self.policy.tick()
                make_invalid()
                released = self.policy.active_token
                self.policy.tick()
                self.assertIsNone(self.policy.active_token)
                self.assertIn(released, [item["request_id"]
                                         for item in self.policy.release_messages])
        self.assertIsNotNone(token)

    def test_manual_stop_suppresses_same_epoch_then_new_epoch_activates(self):
        self.write_idle(epoch=10)
        self.policy.tick()
        self.policy.stop()
        self.assertIsNone(self.policy.active_token)
        self.policy.tick()
        self.assertIsNone(self.policy.active_token)
        self.assertEqual(self.policy.suppressed_idle_epoch["epoch_started_monotonic"], 10)
        self.write_idle(state="active", idle=False, epoch=10)
        self.policy.tick()
        self.assertIsNone(self.policy.suppressed_idle_epoch)
        self.write_idle(epoch=11)
        self.policy.tick()
        self.assertEqual(self.policy.activation_source, "automatic")
        self.assertIsNotNone(self.policy.active_token)

    def test_suppression_survives_restart_and_manual_start_overrides(self):
        self.write_idle(epoch=30)
        self.policy.tick()
        self.policy.stop()
        restarted = FakePolicy(
            self.config, root=self.root, now=lambda: self.current)
        self.assertIsNone(restarted.active_token)
        self.assertEqual(restarted.activation_source, "inactive")
        restarted.start()
        self.assertEqual(restarted.activation_source, "manual")
        self.assertIsNone(restarted.suppressed_idle_epoch)

    def test_manual_request_is_independent_of_canonical_idle(self):
        self.policy.start()
        token = self.policy.active_token
        self.write_idle(state="active", idle=False)
        self.policy.tick()
        self.assertEqual(self.policy.active_token, token)
        self.assertEqual(self.policy.activation_source, "manual")

    def test_automatic_schedule_switch_preserves_idle_epoch(self):
        self.write_idle(epoch=40)
        self.policy.tick()
        epoch = self.policy.automatic_idle_epoch.copy()
        old = self.policy.active_token
        self.current = datetime(2026, 7, 16, 0, 0, tzinfo=self.zone)
        self.policy.tick()
        self.assertEqual(self.policy.active_mode, "black")
        self.assertNotEqual(self.policy.active_token, old)
        self.assertEqual(self.policy.automatic_idle_epoch, epoch)
        self.assertEqual(len(self.policy.request_messages), 2)

    def test_lost_automatic_request_is_recreated_while_idle(self):
        self.write_idle(epoch=50)
        self.policy.tick()
        old = self.policy.active_token
        self.policy.fake_requests.clear()
        self.policy.fake_active = None
        self.policy.tick()
        self.assertNotEqual(self.policy.active_token, old)
        self.assertEqual(self.policy.activation_source, "automatic")

    def test_failed_renderer_retry_is_bounded(self):
        self.write_idle(epoch=55)
        self.policy.tick()
        token = self.policy.active_token
        self.policy.fake_requests[token]["state"] = "failed"
        self.policy.fake_requests[token]["failure_reason"] = "startup-failed"
        self.policy.fake_active = None
        self.policy.tick()
        self.assertIsNone(self.policy.active_token)
        self.assertEqual(len(self.policy.request_messages), 1)
        self.policy.tick()
        self.assertEqual(len(self.policy.request_messages), 1)
        self.assertEqual(self.policy.last_error, "startup-failed")

    def test_status_separates_idle_policy_and_overlay(self):
        self.write_idle(epoch=60)
        self.policy.tick()
        status = self.policy.status()
        self.assertEqual(status["idle_input"]["health"], "healthy")
        self.assertTrue(status["automatic"]["eligible"])
        self.assertEqual(status["activation_source"], "automatic")
        self.assertEqual(status["overlay_active"]["renderer"], "slideshow")

    def test_directory_watcher_observes_atomic_idle_replacement(self):
        watcher = IdleStateWatcher(self.root)
        try:
            temporary = self.root / ".idle-state.json.tmp"
            temporary.write_text("{}")
            temporary.replace(self.root / "idle-state.json")
            deadline = time.monotonic() + 1
            matched = False
            while time.monotonic() < deadline and not matched:
                matched = watcher.changed()
                time.sleep(0.01)
            self.assertTrue(matched)
        finally:
            watcher.close()

    def test_architectural_boundaries_remain_observation_action_split(self):
        root = Path(__file__).parents[1]
        idled = (root / "bin/tvbox-idled").read_text()
        engine = (root / "lib/tvbox/idle/engine.py").read_text()
        policy = (root / "lib/tvbox/screensaver/policy.py").read_text()
        for forbidden in ("tvbox-overlay", "tvbox-screensaver",
                          '"command": "request"'):
            self.assertNotIn(forbidden, idled + engine)
        self.assertNotIn("tvbox.idle.providers", policy)
        for forbidden in ("tvbox-inputctl", "active-context",
                          "stable-state.json", "activity-state.json"):
            self.assertNotIn(forbidden, policy)


if __name__ == "__main__":
    unittest.main()
