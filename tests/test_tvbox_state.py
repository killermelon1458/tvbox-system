import importlib.util
from importlib.machinery import SourceFileLoader
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock


SOURCE = Path(__file__).parents[1] / "bin/tvbox-state"
SPEC = importlib.util.spec_from_loader(
    "tvbox_state", SourceFileLoader("tvbox_state", str(SOURCE)),
)
assert SPEC and SPEC.loader
state = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(state)


class StateTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.env = mock.patch.dict(os.environ, {
            "TVBOX_RUNTIME_ROOT": str(self.root / "runtime"),
            "TVBOX_BOOT_ID": "boot-test",
            "TVBOX_TRANSITION_LOG": str(self.root / "transition.log"),
            "TVBOX_INPUT_PROFILE_FILE": str(self.root / "profile"),
        }, clear=False)
        self.env.start()
        (self.root / "profile").write_text("passthrough\n")

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def observed(self, app, process=False, top=False, profile="passthrough"):
        return {
            "application": app, "process_observed": process,
            "toplevel_observed": top, "input_profile": profile,
        }

    def test_request_does_not_commit_stable_steamlink(self):
        state.commit_stable("kodi", "application", "high")
        state.request("steamlink")
        self.assertEqual(state.read_state("stable-state.json")["application"], "kodi")
        self.assertEqual(state.active_context_path().read_text(), "kodi\n")

    def test_wrapper_ensure_request_reuses_lifecycle_request(self):
        original = state.request("mariokart64")
        ensured = state.ensure_request("mariokart64")
        self.assertEqual(ensured["request_id"], original["request_id"])

    def test_steamlink_process_and_toplevel_accept_menu(self):
        state.request("steamlink")
        with mock.patch.object(state, "observe",
                               return_value=self.observed("steamlink", True, True)), \
             mock.patch.object(state, "STABILITY_SECONDS", {"steamlink": 0.0}):
            self.assertEqual(state.reconcile("steamlink", wait=0.1, interval=0.001), 0)
        self.assertEqual(state.read_state("stable-state.json")["application"], "steamlink")
        self.assertIsNone(state.read_state("transition-state.json"))

    def test_steamlink_early_exit_fails_without_stale_context(self):
        state.commit_stable("kodi", "application", "high")
        state.request("steamlink", deadline=0.01)
        with mock.patch.object(state, "observe",
                               return_value=self.observed("steamlink", False, False)):
            self.assertEqual(state.reconcile("steamlink", wait=0.02, interval=0.001), 1)
        self.assertEqual(state.active_context_path().read_text(), "kodi\n")
        self.assertEqual(state.read_state("transition-state.json")["state"], "failed")
        self.assertEqual(state.read_state("failure-state.json")["application"],
                         "steamlink")

    def test_youtube_return_does_not_commit_kodi_without_toplevel(self):
        state.commit_stable("youtube", "browser-window", "medium")
        state.request("kodi", deadline=0.01)
        state.set_phase("returning")
        with mock.patch.object(state, "observe",
                               return_value=self.observed("kodi", True, False)):
            state.reconcile("kodi", wait=0.02, interval=0.001, returning=True)
        self.assertEqual(state.active_context_path().read_text(), "youtube\n")
        self.assertEqual(state.read_state("transition-state.json")["state"], "failed")

    def test_failed_return_is_available_for_bounded_recovery(self):
        state.request("kodi", deadline=0.01)
        state.set_phase("returning")
        with mock.patch.object(state, "observe",
                               return_value=self.observed("kodi", False, False)):
            self.assertEqual(state.reconcile("kodi", wait=0.02, interval=0.001,
                                             returning=True), 1)
        self.assertEqual(state.read_state("transition-state.json")["failure_reason"],
                         "required-process-exited-before-acceptance")

    def test_moonlight_can_replace_previous_kodi(self):
        state.commit_stable("kodi", "application", "high")
        state.request("moonlight")
        with mock.patch.object(state, "observe",
                               return_value=self.observed("moonlight", True, True)), \
             mock.patch.object(state, "STABILITY_SECONDS", {"moonlight": 0.0}):
            self.assertEqual(state.reconcile("moonlight", wait=0.1, interval=0.001), 0)
        self.assertEqual(state.active_context_path().read_text(), "moonlight\n")

    def test_focus_recovery_cannot_commit_kodi_over_observed_moonlight(self):
        state.commit_stable("moonlight", "menu", "high")
        with mock.patch.object(state, "exact_processes",
                               side_effect=lambda app: [{}] if app == "moonlight" else []), \
             mock.patch.object(state, "toplevel_lines", return_value=["Moonlight: Computers"]):
            state.reconcile_startup()
        self.assertEqual(state.active_context_path().read_text(), "moonlight\n")

    def test_mariokart_process_and_splash_are_not_ready(self):
        state.request("mariokart64", deadline=0.01)
        with mock.patch.object(state, "observe",
                               return_value=self.observed("mariokart64", True, True)):
            self.assertEqual(state.reconcile("mariokart64", wait=0.02,
                                             interval=0.001), 2)
        self.assertIsNone(state.read_state("stable-state.json"))
        self.assertEqual(state.read_state("transition-state.json")["phase"],
                         "content-loading")

    def test_mariokart_early_exit_clears_false_game_state(self):
        state.commit_stable("kodi", "application", "high")
        state.request("mariokart64", deadline=0.01)
        with mock.patch.object(state, "observe",
                               return_value=self.observed("mariokart64", False, False)):
            state.reconcile("mariokart64", wait=0.02, interval=0.001)
        self.assertEqual(state.active_context_path().read_text(), "kodi\n")
        self.assertEqual(state.read_state("transition-state.json")["state"], "failed")

    def test_kodi_process_without_toplevel_is_not_ready(self):
        accepted, phase, _, _ = state.acceptance(
            "kodi", self.observed("kodi", True, False), 10)
        self.assertFalse(accepted)
        self.assertEqual(phase, "ready")

    def test_reconcile_without_request_creates_matching_request(self):
        with mock.patch.object(state, "observe",
                               return_value=self.observed("kodi", True, True)):
            self.assertEqual(state.reconcile("kodi", wait=0.01,
                                             interval=0.001), 0)
        self.assertEqual(state.read_state("stable-state.json")["request_id"],
                         state.read_state("lifecycle-request.json")["request_id"])

    def test_previous_boot_transition_is_rejected(self):
        path = state.runtime_root() / "transition-state.json"
        path.write_text(json.dumps({"schema_version": 1, "boot_id": "old"}))
        self.assertIsNone(state.read_state("transition-state.json"))

    def test_malformed_runtime_json_is_ignored(self):
        (state.runtime_root() / "stable-state.json").write_text("{bad")
        self.assertIsNone(state.read_state("stable-state.json"))

    def test_atomic_replacement_is_used(self):
        with mock.patch.object(state.os, "replace", wraps=os.replace) as replace:
            state.write_state("observed-state.json", {"application": "kodi"})
        replace.assert_called_once()
        self.assertEqual(
            (state.runtime_root() / "observed-state.json").stat().st_mode & 0o777,
            0o600,
        )

    def test_profile_is_observed_without_policy(self):
        state.request("steamlink")
        before = (self.root / "profile").read_text()
        result = state.profile_observation()
        self.assertEqual(result["input_profile"], "passthrough")
        self.assertEqual((self.root / "profile").read_text(), before)

    def test_home_returning_then_kodi_commit(self):
        state.commit_stable("youtube", "browser-window", "medium")
        state.request("kodi")
        state.set_phase("returning")
        self.assertEqual(state.read_state("transition-state.json")["phase"], "returning")
        with mock.patch.object(state, "observe",
                               return_value=self.observed("kodi", True, True)):
            self.assertEqual(state.reconcile("kodi", wait=0.01,
                                             interval=0.001, returning=True), 0)
        self.assertEqual(state.active_context_path().read_text(), "kodi\n")
        self.assertIsNone(state.read_state("transition-state.json"))

    def test_client_exit_does_not_corrupt_newer_kodi_return(self):
        state.commit_stable("moonlight", "menu", "high")
        state.request("kodi")
        state.set_phase("returning")
        self.assertIsNone(state.client_exit("moonlight", 0))
        self.assertEqual(state.read_state("transition-state.json")["application"],
                         "kodi")
        self.assertIsNone(state.read_state("failure-state.json"))

    def test_prior_stable_monitor_yields_to_new_app_transition(self):
        state.commit_stable("kodi", "application", "high")
        state.request("youtube")
        with mock.patch.object(state, "observe",
                               return_value=self.observed("kodi", False, False)):
            self.assertEqual(state.main(["monitor", "kodi"]), 0)
        self.assertEqual(state.read_state("transition-state.json")["application"],
                         "youtube")


if __name__ == "__main__":
    unittest.main()
