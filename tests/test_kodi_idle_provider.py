import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).parents[1] / "lib"))

from tvbox.idle.config import load_config
from tvbox.idle.engine import IdleEngine
from tvbox.idle.providers import select_provider


CONFIG = """
[global]
enabled = true
stability_delay_seconds = 1
poll_interval_seconds = 0.1
display_status_path = "/unused"
[activity]
activity_stale_seconds = 5
[providers.kodi]
enabled = true
timeout_seconds = 10
required_sources = ["flirc", "keyboard", "pointer"]
observer_stale_seconds = 5
[providers.unknown]
enabled = false
timeout_seconds = 10
"""


class Clock:
    value = 100.0

    def __call__(self):
        return self.value


class KodiProviderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        path = Path(self.tmp.name) / "idle.toml"
        path.write_text(CONFIG, encoding="utf-8")
        self.config = load_config(path)
        self.clock = Clock()
        self.stable = {"application": "kodi", "request_id": "stable"}
        self.process = {"pid": 12, "start_time_ticks": 34,
                        "executable": "/usr/lib/kodi/kodi.bin"}
        self.observed = {
            "application": "kodi", "process_observed": True,
            "toplevel_observed": True, "conflicting_toplevels": [],
            "current_processes": [self.process],
        }

    def tearDown(self):
        self.tmp.cleanup()

    def kodi(self, playback="stopped", **changes):
        value = {
            "writer_instance_id": "observer-1",
            "updated_monotonic": self.clock.value,
            "kodi_session": dict(self.process),
            "playback": playback,
            "health": "healthy",
        }
        value.update(changes)
        return value

    def result(self, playback="stopped", observed=None, **changes):
        return select_provider(
            self.stable, observed if observed is not None else self.observed,
            self.config, self.kodi(playback, **changes), self.clock.value)

    def test_stable_stopped_is_eligible(self):
        result = self.result()
        self.assertTrue(result.eligible)
        self.assertEqual(result.provider_context, "stopped-anywhere")
        self.assertEqual(result.required_activity_sources,
                         ("flirc", "keyboard", "pointer"))

    def test_non_stopped_states_inhibit(self):
        for state in ("starting", "playing", "paused", "unknown", "bogus"):
            with self.subTest(state=state):
                result = self.result(state)
                self.assertTrue(result.inhibit)
                expected = state if state != "bogus" else "unknown"
                self.assertIn(f"kodi-playback-{expected}", result.reasons)

    def test_stale_unhealthy_and_session_mismatch_inhibit(self):
        self.assertIn("kodi-observer-stale", self.result(
            updated_monotonic=90).reasons)
        self.assertIn("kodi-observer-unhealthy", self.result(
            health="unhealthy").reasons)
        session = dict(self.process)
        session["start_time_ticks"] += 1
        self.assertIn("kodi-session-mismatch", self.result(
            kodi_session=session).reasons)

    def test_process_and_toplevel_are_required(self):
        for key, reason in (("process_observed", "kodi-process-missing"),
                            ("toplevel_observed", "kodi-toplevel-missing")):
            observed = dict(self.observed)
            observed[key] = False
            self.assertIn(reason, self.result(observed=observed).reasons)

    def test_missing_observer_and_disabled_provider_inhibit(self):
        result = select_provider(self.stable, self.observed, self.config,
                                 None, self.clock.value)
        self.assertIn("kodi-observer-unavailable", result.reasons)
        disabled_text = CONFIG.replace("enabled = true\ntimeout_seconds = 10",
                                       "enabled = false\ntimeout_seconds = 10", 1)
        path = Path(self.tmp.name) / "disabled.toml"
        path.write_text(disabled_text, encoding="utf-8")
        disabled = select_provider(self.stable, self.observed,
                                   load_config(path), self.kodi(), 100)
        self.assertIn("provider-disabled", disabled.reasons)

    def engine_inputs(self, playback):
        return {
            "stable": self.stable, "observed": self.observed,
            "transition": None, "display": "connected",
            "kodi_state": self.kodi(playback),
            "activity": {
                "activity_generation": 1,
                "last_activity_monotonic": None,
                "updated_monotonic": self.clock.value,
                "source_health": {"flirc": "healthy", "keyboard": "healthy",
                                  "pointer": "healthy"},
            },
        }

    def test_playback_stop_and_observer_change_start_fresh_epochs(self):
        engine = IdleEngine(self.config, root=Path(self.tmp.name),
                            monotonic=self.clock)
        engine.evaluate(self.engine_inputs("playing"))
        self.clock.value += 20
        stopped = engine.evaluate(self.engine_inputs("stopped"))
        self.assertEqual(stopped["state"], "active")
        self.assertEqual(stopped["epoch_started_monotonic"], self.clock.value)
        same = engine.evaluate(self.engine_inputs("stopped"))
        self.assertEqual(same["epoch_started_monotonic"], self.clock.value)
        self.clock.value += 1
        recovered = self.engine_inputs("stopped")
        recovered["kodi_state"]["writer_instance_id"] = "observer-2"
        result = engine.evaluate(recovered)
        self.assertEqual(result["epoch_started_monotonic"], self.clock.value)

    def test_transition_recovery_conflict_and_sources_fail_safe(self):
        engine = IdleEngine(self.config, root=Path(self.tmp.name),
                            monotonic=self.clock)
        transition = self.engine_inputs("stopped")
        transition["transition"] = {"phase": "client-starting", "request_id": "t"}
        self.assertEqual(engine.evaluate(transition)["state"], "inhibited")
        recovery = self.engine_inputs("stopped")
        recovery["transition"] = {"phase": "returning", "request_id": "t"}
        self.assertEqual(engine.evaluate(recovery)["state"], "recovering")
        conflict = self.engine_inputs("stopped")
        conflict["observed"] = dict(self.observed,
                                    conflicting_toplevels=["moonlight"])
        self.assertEqual(engine.evaluate(conflict)["state"], "degraded")
        degraded = self.engine_inputs("stopped")
        degraded["activity"]["source_health"]["flirc"] = "missing"
        self.assertEqual(engine.evaluate(degraded)["state"], "degraded")

    def test_screensaver_and_schedule_state_do_not_enter_signature(self):
        engine = IdleEngine(self.config, root=Path(self.tmp.name),
                            monotonic=self.clock)
        first = engine.evaluate(self.engine_inputs("stopped"))
        self.clock.value += 1
        second = engine.evaluate(self.engine_inputs("stopped"))
        self.assertEqual(first["epoch_started_monotonic"],
                         second["epoch_started_monotonic"])


if __name__ == "__main__":
    unittest.main()
