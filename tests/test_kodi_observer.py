import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).parents[1] / "lib"))

from tvbox.idle.kodi_observer import KodiObservationWriter
from tvbox.idle.kodi_log import KodiLogFollower


class Clock:
    value = 50.0

    def __call__(self):
        return self.value


class KodiObserverTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.clock = Clock()
        self.identity = {"pid": 100, "start_time_ticks": 200,
                         "executable": "/usr/lib/kodi/kodi.bin"}
        self.env = mock.patch.dict(os.environ, {"TVBOX_BOOT_ID": "test-boot"})
        self.env.start()
        self.writer = KodiObservationWriter(
            self.root, self.identity, self.clock, "writer-1")

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def test_fresh_session_begins_unknown_then_direct_state_establishes(self):
        first = self.writer.publish(10000)
        self.assertEqual(first["playback"], "unknown")
        self.writer.establish_current_state(False)
        self.assertEqual(self.writer.publish()["playback"], "stopped")
        restarted = KodiObservationWriter(
            self.root, self.identity, self.clock, "writer-2")
        self.assertEqual(restarted.publish()["playback"], "unknown")

    def test_allowlisted_callback_normalization(self):
        sequence = [
            ("Player.OnPlay", "starting"),
            ("Player.OnAVStart", "playing"),
            ("Player.OnPause", "paused"),
            ("Player.OnResume", "playing"),
            ("Player.OnStop", "stopped"),
            ("Player.OnEnd", "stopped"),
        ]
        for index, (event, expected) in enumerate(sequence):
            self.clock.value += 1
            with self.subTest(event=event):
                self.assertTrue(self.writer.apply_event(event))
                self.assertEqual(self.writer.playback, expected)
                self.assertEqual(self.writer.last_event, event)

    def test_out_of_order_and_malformed_events_fail_safe(self):
        self.assertTrue(self.writer.apply_event("Player.OnAVStart", 60))
        self.assertFalse(self.writer.apply_event("Player.OnStop", 59))
        self.assertEqual(self.writer.playback, "unknown")
        self.assertEqual(self.writer.health, "degraded")
        self.assertFalse(self.writer.apply_event("Player.Title=private", 61))
        self.assertEqual(self.writer.playback, "unknown")

    def test_atomic_json_mode_schema_boot_and_identity(self):
        result = self.writer.publish(12005)
        path = self.root / "kodi-state.json"
        self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
        self.assertEqual(result["schema_version"], 1)
        self.assertEqual(result["boot_id"], "test-boot")
        self.assertEqual(result["kodi_session"], self.identity)
        self.assertFalse(any(path.name.startswith(".kodi-state.json.")
                             for path in self.root.iterdir()))

    def test_record_has_no_callback_payload_or_private_media_fields(self):
        record = json.dumps(self.writer.record()).lower()
        for forbidden in ("title", "url", "token", "credential", "media_path",
                          "log_body", "filename"):
            self.assertNotIn(forbidden, record)

    def test_addon_and_provider_preserve_architectural_boundaries(self):
        root = Path(__file__).parents[1]
        paths = [
            root / "bin/tvbox-kodi-observerd",
            root / "lib/tvbox/idle/kodi_observer.py",
            root / "lib/tvbox/idle/kodi_log.py",
            root / "lib/tvbox/idle/providers.py",
        ]
        for path in paths:
            source = path.read_text(encoding="utf-8").lower()
            for forbidden in ("tvbox-overlay", "tvbox-screensaver",
                              "tvbox-inputctl", "active-context", "tvbox-home"):
                self.assertNotIn(forbidden, source)



class KodiLogFollowerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.log = self.root / "kodi.log"
        self.log.write_bytes(b"old Player.OnStop\n")
        self.clock = Clock()
        self.identity = {"pid": 100, "start_time_ticks": 200,
                         "executable": "/usr/lib/kodi/kodi.bin"}
        self.current = self.identity
        self.env = mock.patch.dict(os.environ, {"TVBOX_BOOT_ID": "test-boot"})
        self.env.start()
        self.writer = KodiObservationWriter(
            self.root, None, self.clock, "writer-1")
        self.follower = KodiLogFollower(
            self.log, self.writer, lambda: self.current)

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def append(self, value):
        with self.log.open("ab") as stream:
            stream.write(value)

    def test_new_session_ignores_old_log_and_partial_lines(self):
        self.follower.poll()
        self.assertEqual(self.writer.playback, "unknown")
        self.append(b"x Notification: xbmc Player.OnPlay")
        self.follower.poll()
        self.assertEqual(self.writer.playback, "unknown")
        self.append(b"\n")
        self.follower.poll()
        self.assertEqual(self.writer.playback, "starting")

    def test_multiple_allowlisted_events_in_one_read(self):
        self.follower.poll()
        self.append(b"Notification: xbmc Player.OnPlay\n"
                    b"Notification: xbmc Player.OnAVStart speed=1\n")
        self.follower.poll()
        self.assertEqual(self.writer.playback, "playing")
        self.assertEqual(self.writer.event_generation, 2)

    def test_rotation_and_truncation_reset_unknown_then_recover(self):
        self.follower.poll()
        self.append(b"Notification: xbmc Player.OnStop\n")
        self.follower.poll()
        self.assertEqual(self.writer.playback, "stopped")
        rotated = self.root / "kodi.log.old"
        self.log.rename(rotated)
        self.log.write_bytes(b"")
        self.follower.poll()
        self.assertEqual(self.writer.playback, "unknown")
        self.append(b"Notification: xbmc Player.OnStop\n")
        self.follower.poll()
        self.assertEqual(self.writer.playback, "stopped")
        self.log.write_bytes(b"")
        self.follower.poll()
        self.assertEqual(self.writer.playback, "unknown")

    def test_pid_or_start_ticks_change_invalidates_old_event(self):
        self.follower.poll()
        self.append(b"Notification: xbmc Player.OnStop\n")
        self.follower.poll()
        self.assertEqual(self.writer.playback, "stopped")
        self.current = dict(self.identity, start_time_ticks=201)
        self.follower.poll()
        self.assertEqual(self.writer.playback, "unknown")
        self.assertEqual(self.writer.identity["start_time_ticks"], 201)

    def test_malformed_and_private_lines_are_never_published(self):
        self.follower.poll()
        self.append(b"private title=https://secret token=secret\n"
                    b"Notification: xbmc Player.BadEvent\n")
        value = self.follower.poll()
        serialized = json.dumps(value).lower()
        self.assertEqual(self.writer.playback, "unknown")
        for private in ("https://secret", "token=secret", "private title"):
            self.assertNotIn(private, serialized)


if __name__ == "__main__":
    unittest.main()
