import importlib.machinery
import importlib.util
import json
from pathlib import Path
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "bin/tvbox-diag"
loader = importlib.machinery.SourceFileLoader("tvbox_diag", str(SCRIPT))
spec = importlib.util.spec_from_loader(loader.name, loader)
diag = importlib.util.module_from_spec(spec)
loader.exec_module(diag)


def base():
    return {
        "active_context": "kodi",
        "input_profile": "kodi_native_minimal",
        "processes": [{"pid": 1, "comm": "kodi.bin", "cmdline": "kodi.bin"}],
        "wayland": {
            "connected": True,
            "toplevels": [{"app_id": "Kodi", "title": "Kodi", "activated": None}],
            "focus": {"state": "unknown"},
        },
        "locks": {"transition": {"held": False}},
        "input_devices": [],
        "antimicrox": {"running": False, "controller_target": "all"},
        "kodi_open_input_nodes": {"nodes": []},
        "recent_logs": {"kodi": []},
    }


class AnomalyTests(unittest.TestCase):
    def test_healthy_kodi_has_no_error(self):
        kinds = {x["event_type"] for x in diag.anomalies(base())}
        self.assertNotIn("context_process_mismatch", kinds)
        self.assertNotIn("kodi_toplevel_missing", kinds)
        self.assertNotIn("focus_mismatch_confirmed", kinds)

    def test_missing_process(self):
        sample = base()
        sample["processes"] = []
        kinds = {x["event_type"] for x in diag.anomalies(sample)}
        self.assertIn("context_process_mismatch", kinds)

    def test_wrong_profile(self):
        sample = base()
        sample["input_profile"] = "passthrough"
        kinds = {x["event_type"] for x in diag.anomalies(sample)}
        self.assertIn("input_profile_mismatch", kinds)

    def test_node_change_alone_is_not_reacquisition_failure(self):
        sample = base()
        sample["input_devices"] = [{
            "manufacturer": "8BitDo", "identity": "active", "stable_id": "usb:x",
            "nodes": [{"node": "/dev/input/js2", "kind": "joystick"}],
        }]
        kinds = {x["event_type"] for x in diag.anomalies(sample)}
        self.assertNotIn("kodi_controller_reacquisition_failed", kinds)

    def test_reacquisition_requires_combined_evidence(self):
        sample = base()
        sample["input_devices"] = [{
            "manufacturer": "8BitDo", "identity": "active", "stable_id": "usb:x",
            "nodes": [{"node": "/dev/input/js1", "kind": "joystick"}],
        }]
        sample["recent_logs"]["kodi"] = ["ScanForJoysticks: can't open /dev/input/js1 (errno=13)"]
        kinds = {x["event_type"] for x in diag.anomalies(sample)}
        self.assertIn("kodi_controller_reacquisition_failed", kinds)

    def test_record_schema(self):
        item = diag.record("test", "event", "info", {})
        for key in ("timestamp", "monotonic_timestamp", "source", "event_type",
                    "severity", "active_context", "input_profile", "details"):
            self.assertIn(key, item)
        json.dumps(item)

    def test_focus_unknown_never_becomes_confirmed(self):
        sample = base()
        sample["wayland"]["toplevels"].append(
            {"app_id": "foot", "title": "Terminal", "activated": None}
        )
        kinds = {x["event_type"] for x in diag.anomalies(sample)}
        self.assertIn("focus_mismatch_suspected", kinds)
        self.assertNotIn("focus_mismatch_confirmed", kinds)

    def test_display_change_is_correlated(self):
        old = {
            "drm": [{"name": "HDMI-A-2", "status": "connected"}],
            "display_state": {"state": "unknown"},
            "wayland_connected": True, "toplevels": [], "input_devices": [],
            "processes": [],
        }
        new = {
            **old,
            "drm": [{"name": "HDMI-A-2", "status": "disconnected"}],
            "display_state": {"state": "unavailable"},
        }
        kinds = {x[0] for x in diag.classify_changes(old, new)}
        self.assertIn("display_state_changed", kinds)
        self.assertIn("display_model_transition", kinds)

    def test_controller_lifecycle_uses_stable_id(self):
        old = {
            "drm": [], "display_state": {"state": "unknown"},
            "wayland_connected": False, "toplevels": [], "processes": [],
            "input_devices": [],
        }
        new = {
            **old,
            "input_devices": [{
                "stable_id": "usb:SERIAL:1-1.3:2dc8:310a",
                "usb_path": "1-1.3", "manufacturer": "8BitDo",
                "identity": "active", "nodes": [],
            }],
        }
        kinds = {x[0] for x in diag.classify_changes(old, new)}
        self.assertIn("controller_usb_added", kinds)


if __name__ == "__main__":
    unittest.main()
