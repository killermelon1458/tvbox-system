import importlib.util
from importlib.machinery import SourceFileLoader
from pathlib import Path
import tempfile
import unittest
from unittest import mock


SOURCE = Path(__file__).parents[1] / "bin/tvbox-focusd"
SPEC = importlib.util.spec_from_loader(
    "tvbox_focusd", SourceFileLoader("tvbox_focusd", str(SOURCE)),
)
assert SPEC and SPEC.loader
focusd = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(focusd)


class FocusGateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.state = root / "state"
        self.state.mkdir()
        self.connector = root / "status"
        self.connector.write_text("connected\n")
        self.context = self.state / "active-context"
        self.context.write_text("kodi\n")
        self.old_state = focusd.STATE_DIR
        self.old_connector = focusd.CONNECTOR
        focusd.STATE_DIR = self.state
        focusd.CONNECTOR = self.connector

    def tearDown(self):
        focusd.STATE_DIR = self.old_state
        focusd.CONNECTOR = self.old_connector
        self.tmp.cleanup()

    @mock.patch.object(focusd, "kodi_toplevel", return_value=True)
    def test_healthy_kodi_is_allowed(self, _toplevel):
        allowed, reason = focusd.recovery_gate(["kodi.bin /usr/lib/kodi/kodi.bin"])
        self.assertTrue(allowed)
        self.assertEqual(reason, "ready")

    @mock.patch.object(focusd, "kodi_toplevel", return_value=True)
    def test_wrong_context_is_blocked(self, _toplevel):
        self.context.write_text("desktop\n")
        self.assertEqual(
            focusd.recovery_gate(["kodi.bin /usr/lib/kodi/kodi.bin"]),
            (False, "context:desktop"),
        )

    @mock.patch.object(focusd, "kodi_toplevel", return_value=True)
    def test_disconnected_output_is_blocked(self, _toplevel):
        self.connector.write_text("disconnected\n")
        self.assertEqual(
            focusd.recovery_gate(["kodi.bin /usr/lib/kodi/kodi.bin"]),
            (False, "connector_not_connected"),
        )

    @mock.patch.object(focusd, "kodi_toplevel", return_value=True)
    def test_external_app_is_blocked_even_with_stale_kodi_context(self, _toplevel):
        rows = [
            "kodi.bin /usr/lib/kodi/kodi.bin",
            "moonlight /usr/bin/moonlight stream host",
        ]
        self.assertEqual(
            focusd.recovery_gate(rows),
            (False, "external_app:moonlight"),
        )

    @mock.patch.object(focusd, "kodi_toplevel", return_value=False)
    def test_missing_toplevel_is_retryable(self, _toplevel):
        self.assertEqual(
            focusd.recovery_gate(["kodi.bin /usr/lib/kodi/kodi.bin"]),
            (False, "kodi_toplevel_not_ready"),
        )

    @mock.patch.object(focusd, "kodi_toplevel", return_value=True)
    def test_missing_kodi_process_is_blocked(self, _toplevel):
        self.assertEqual(
            focusd.recovery_gate(["pcmanfm pcmanfm --desktop"]),
            (False, "kodi_not_running"),
        )


class ProcessClassificationTests(unittest.TestCase):
    def test_exact_kodi_process_forms(self):
        self.assertTrue(focusd.kodi_running(["kodi.bin /usr/lib/kodi/kodi.bin"]))
        self.assertTrue(focusd.kodi_running(["sh /usr/bin/kodi -fs"]))
        self.assertFalse(focusd.kodi_running(["rg kodi.bin"]))

    def test_known_external_processes(self):
        self.assertEqual(
            focusd.external_app(["steamlink /usr/bin/steamlink"]),
            "steamlink",
        )
        self.assertIsNone(focusd.external_app(["pcmanfm pcmanfm --desktop"]))


if __name__ == "__main__":
    unittest.main()
