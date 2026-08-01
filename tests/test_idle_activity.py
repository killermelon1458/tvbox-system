import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).parents[1] / "lib"))

from tvbox.idle.activity import (
    ActivityCollector, ActivityTracker, BTN_MOUSE, DeviceInfo, EV_KEY, EV_REL,
    REL_X, REL_Y, classify_device, discover_devices,
)
from tvbox.idle.config import load_config


CONFIG = """
[global]
stability_delay_seconds = 2
[activity]
pointer_distance_px = 12
pointer_window_ms = 500
device_rescan_seconds = 1
activity_stale_seconds = 5
exclude_virtual_device_names = ["antimicrox Keyboard Emulation"]
exclude_controller_hid = true
[providers.desktop]
enabled = true
timeout_seconds = 5
required_sources = ["keyboard", "pointer"]
"""


class Clock:
    def __init__(self):
        self.value = 10.0

    def __call__(self):
        return self.value


class ActivityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.dev = self.root / "dev/input"
        self.sys = self.root / "sys/class/input"
        (self.dev / "by-id").mkdir(parents=True)
        self.sys.mkdir(parents=True)
        self.config_path = self.root / "idle.toml"
        self.config_path.write_text(CONFIG)
        self.config = load_config(self.config_path)

    def tearDown(self):
        self.tmp.cleanup()

    def device(self, event, name, rel="0", by_id=None):
        node = self.dev / event
        node.touch()
        base = self.sys / event / "device"
        (base / "capabilities").mkdir(parents=True)
        (base / "name").write_text(name)
        (base / "capabilities/rel").write_text(rel)
        if by_id:
            (self.dev / "by-id" / by_id).symlink_to(Path("..") / event)
        return node

    def test_stable_by_id_and_event_number_change(self):
        first = self.device("event4", "USB Keyboard", by_id="usb-test-event-kbd")
        items = discover_devices(self.dev, self.sys,
                                 self.config.exclude_virtual_device_names)
        self.assertEqual(items[0].identity,
                         str(self.dev / "by-id/usb-test-event-kbd"))
        first.unlink()
        (self.sys / "event4/device/name").unlink()
        second = self.device("event9", "USB Keyboard", by_id="usb-new-event-kbd")
        items = discover_devices(self.dev, self.sys,
                                 self.config.exclude_virtual_device_names)
        self.assertEqual(items[-1].node, str(second))

    def test_flirc_keyboard_pointer_and_exclusions(self):
        flirc = self.device("event1", "flirc.tv flirc Keyboard", "1040")
        mouse = self.device("event2", "USB Mouse", "3")
        virtual = self.device("event3", "antimicrox Keyboard Emulation")
        controller = self.device("event4", "8BitDo Controller Mouse", "3")
        raw = self.device("event5", "Generic X-Box pad")
        excluded = tuple(value.lower()
                         for value in self.config.exclude_virtual_device_names)
        self.assertEqual(classify_device(flirc, self.sys, {}, excluded).classes,
                         ("flirc", "keyboard"))
        self.assertEqual(classify_device(mouse, self.sys, {}, excluded).classes,
                         ("pointer",))
        self.assertEqual(classify_device(virtual, self.sys, {}, excluded).excluded_reason,
                         "excluded-virtual")
        self.assertEqual(classify_device(controller, self.sys, {}, excluded).excluded_reason,
                         "excluded-controller-hid")
        self.assertEqual(classify_device(raw, self.sys, {}, excluded).excluded_reason,
                         "unsupported-device-class")

    def test_key_down_and_button_count_release_ignored(self):
        tracker = ActivityTracker()
        self.assertEqual(tracker.feed(EV_KEY, 30, 1), "key-down")
        self.assertIsNone(tracker.feed(EV_KEY, 30, 0))
        self.assertEqual(tracker.feed(EV_KEY, BTN_MOUSE, 1), "pointer-button")
        self.assertIsNone(tracker.feed(EV_KEY, BTN_MOUSE, 0))

    def test_pointer_jitter_ignored_and_accumulated_motion_counts(self):
        clock = Clock()
        tracker = ActivityTracker(12, 500, clock)
        self.assertIsNone(tracker.feed(EV_REL, REL_X, 3))
        self.assertIsNone(tracker.feed(EV_REL, REL_Y, 4))
        self.assertEqual(tracker.feed(EV_REL, REL_X, 9), "pointer-motion")
        clock.value += 1
        self.assertIsNone(tracker.feed(EV_REL, REL_X, 7))
        clock.value += 1
        self.assertIsNone(tracker.feed(EV_REL, REL_X, 7))

    def test_health_source_loss_recovery_and_atomic_state(self):
        env = {"TVBOX_RUNTIME_ROOT": str(self.root / "runtime"),
               "TVBOX_BOOT_ID": "test-boot"}
        with mock.patch.dict(os.environ, env):
            collector = ActivityCollector(self.config, root=self.root / "runtime")
            keyboard = DeviceInfo("/dev/kbd", "/by-id/kbd", "Keyboard",
                                  ("keyboard",))
            pointer = DeviceInfo("/dev/mouse", "/by-id/mouse", "Mouse",
                                 ("pointer",))
            collector.inventory = [keyboard, pointer]
            collector.open_devices = {10: keyboard, 11: pointer}
            healthy = collector.publish()
            self.assertEqual(healthy["source_health"]["keyboard"], "healthy")
            self.assertEqual(healthy["source_health"]["pointer"], "healthy")
            collector.open_devices = {10: keyboard}
            degraded = collector.publish()
            self.assertEqual(degraded["source_health"]["pointer"], "missing")
            collector.open_devices = {10: keyboard, 12: pointer}
            recovered = collector.publish()
            self.assertEqual(recovered["source_health"]["pointer"], "healthy")
            path = self.root / "runtime/activity-state.json"
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertEqual(json.loads(path.read_text())["schema_version"], 1)
            collector.open_devices = {}
            collector.close()


if __name__ == "__main__":
    unittest.main()
