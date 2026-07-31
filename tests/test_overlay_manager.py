import json
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).parents[1] / "lib"))

from tvbox.overlay.manager import OverlayManager
from tvbox.overlay.protocol import ProtocolError


READY_CODE = r"""
import json, os, signal, time
fd=int(os.environ["TVBOX_OVERLAY_READY_FD"])
os.write(fd, (json.dumps({
 "event":"first-frame-ready",
 "request_id":os.environ["TVBOX_OVERLAY_REQUEST_ID"],
 "generation":int(os.environ["TVBOX_OVERLAY_GENERATION"])
})+"\n").encode())
os.close(fd)
signal.signal(signal.SIGTERM, lambda *_: exit(0))
while True: time.sleep(.05)
"""
FAIL_CODE = "import sys; sys.exit(3)"
TIMEOUT_CODE = "import time; time.sleep(10)"


def message(renderer="black", **changes):
    value = {
        "schema_version": 1, "owner_service": "test-policy",
        "owner_instance_id": "owner-1", "owner_pid": os.getpid(),
        "overlay_type": "screensaver", "renderer": renderer,
        "arguments": {"output": "0"}, "priority": 20,
        "lease_seconds": 30, "preemption_policy": "cancel",
    }
    value.update(changes)
    return value


class ManagerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        commands = {
            "black": [sys.executable, "-c", READY_CODE],
            "slideshow": [sys.executable, "-c", READY_CODE],
        }
        self.manager = OverlayManager(
            root=self.root, renderer_commands=commands,
            startup_timeout=.3, stop_timeout=.2,
        )

    def tearDown(self):
        self.manager.shutdown()
        self.tmp.cleanup()

    def wait_state(self, token, expected, timeout=2):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            item = self.manager.requests.get(token)
            if item and item.state == expected:
                return item
            time.sleep(.01)
        self.fail(f"{token} did not reach {expected}")

    def test_token_creation_and_exact_release(self):
        response = self.manager.accept(message())
        self.assertEqual(len(response["request_id"]), 32)
        self.wait_state(response["request_id"], "active")
        with self.assertRaises(ProtocolError):
            self.manager.release("0" * 32)
        self.manager.release(response["request_id"])
        self.assertIsNone(self.manager.active_token)

    def test_old_token_cannot_release_new_request(self):
        first = self.manager.accept(message())
        self.wait_state(first["request_id"], "active")
        second = self.manager.accept(message(
            renderer="slideshow", replace_token=first["request_id"]))
        self.wait_state(second["request_id"], "active")
        deadline = time.monotonic() + 1
        while first["request_id"] in self.manager.requests and time.monotonic() < deadline:
            time.sleep(.01)
        with self.assertRaises(ProtocolError):
            self.manager.release(first["request_id"])
        self.assertEqual(self.manager.active_token, second["request_id"])

    def test_renew_and_expire(self):
        response = self.manager.accept(message(lease_seconds=2))
        self.wait_state(response["request_id"], "active")
        before = self.manager.requests[response["request_id"]].lease_expires_monotonic
        renewed = self.manager.renew(response["request_id"], 20)
        self.assertGreater(renewed["lease_expires_monotonic"], before)
        self.manager.requests[response["request_id"]].lease_expires_monotonic = 0
        self.assertEqual(self.manager.expire(), 1)
        self.assertIsNone(self.manager.active_token)

    def test_startup_timeout_does_not_claim_active(self):
        self.manager.renderer_commands["black"] = [
            sys.executable, "-c", TIMEOUT_CODE]
        response = self.manager.accept(message())
        failed = self.wait_state(response["request_id"], "failed")
        self.assertEqual(failed.failure_reason, "renderer-readiness-timeout")
        self.assertIsNone(self.manager.active_token)

    def test_crash_cleanup(self):
        response = self.manager.accept(message())
        item = self.wait_state(response["request_id"], "active")
        os.killpg(item.process_group, 9)
        self.wait_state(response["request_id"], "failed")
        self.assertIsNone(self.manager.active_token)

    def test_replacement_promotes_before_old_stops(self):
        first = self.manager.accept(message())
        old = self.wait_state(first["request_id"], "active")
        second = self.manager.accept(message(
            renderer="slideshow", replace_token=first["request_id"]))
        new = self.wait_state(second["request_id"], "active")
        self.assertTrue(new.ready)
        self.assertEqual(self.manager.active_token, second["request_id"])
        deadline = time.monotonic() + 1
        while first["request_id"] in self.manager.requests and time.monotonic() < deadline:
            time.sleep(.01)
        self.assertNotIn(first["request_id"], self.manager.requests)
        self.assertIsNotNone(old.exit_status)

    def test_failed_replacement_preserves_old(self):
        first = self.manager.accept(message())
        self.wait_state(first["request_id"], "active")
        self.manager.renderer_commands["slideshow"] = [
            sys.executable, "-c", FAIL_CODE]
        second = self.manager.accept(message(
            renderer="slideshow", replace_token=first["request_id"]))
        self.wait_state(second["request_id"], "failed")
        self.assertEqual(self.manager.active_token, first["request_id"])
        self.assertEqual(self.manager.requests[first["request_id"]].state, "active")

    def test_late_old_exit_does_not_clear_new_generation(self):
        first = self.manager.accept(message())
        old = self.wait_state(first["request_id"], "active")
        second = self.manager.accept(message(
            renderer="slideshow", replace_token=first["request_id"]))
        self.wait_state(second["request_id"], "active")
        self.manager._watch_exit(old)
        self.assertEqual(self.manager.active_token, second["request_id"])

    def test_restart_ignores_stale_cache_and_unrelated_pid(self):
        self.manager.shutdown()
        stale = {
            "schema_version": 1, "boot_id": "same",
            "active_request": {"process_pid": os.getpid(), "process_group": os.getpid()},
        }
        (self.root / "overlay-state.json").write_text(json.dumps(stale))
        with mock.patch("os.killpg") as kill:
            replacement = OverlayManager(root=self.root)
        try:
            kill.assert_not_called()
            self.assertIsNone(replacement.snapshot()["active_request"])
        finally:
            replacement.shutdown()


if __name__ == "__main__":
    unittest.main()
