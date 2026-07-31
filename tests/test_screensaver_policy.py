from datetime import datetime
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).parents[1] / "lib"))

from tvbox.screensaver.policy import ScreensaverPolicy


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
        super().__init__(*args, **kwargs)

    def overlay(self, message):
        command = message["command"]
        if command == "request":
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


if __name__ == "__main__":
    unittest.main()
