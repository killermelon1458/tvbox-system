"""Observation-only canonical idle state machine."""

from datetime import datetime, timezone
from pathlib import Path
import os
import time

from tvbox.idle.providers import select_provider
from tvbox.runtime import instance_id, read_json, runtime_root, write_json


CONTROLLED_APPS = {
    "kodi", "moonlight", "steamlink", "youtube", "mariokart64", "spotify"
}


def read_display(path):
    try:
        return Path(path).read_text(encoding="utf-8").strip().lower()
    except OSError:
        return "unknown"


def load_inputs(root, display_status_path):
    root = Path(root)
    observed = read_json(root / "observed-state.json")
    if observed:
        observed = dict(observed)
        observed["current_processes"] = [
            process for process in observed.get("processes", [])
            if _process_identity_current(process)
        ]
    return {
        "stable": read_json(root / "stable-state.json"),
        "observed": observed,
        "transition": read_json(root / "transition-state.json"),
        "activity": read_json(root / "activity-state.json"),
        "kodi_state": read_json(root / "kodi-state.json"),
        "display": read_display(display_status_path),
    }


def _process_identity_current(claim):
    try:
        pid = int(claim["pid"])
        fields = Path(f"/proc/{pid}/stat").read_text(
            encoding="utf-8").rsplit(")", 1)[1].split()
        return (int(fields[19]) == claim.get("start_time_ticks")
                and os.readlink(f"/proc/{pid}/exe") == claim.get("executable"))
    except (OSError, ValueError, KeyError, IndexError, TypeError):
        return False


class IdleEngine:
    def __init__(self, config, root=None, monotonic=time.monotonic,
                 wall_now=None):
        self.config = config
        self.root = Path(root) if root else runtime_root()
        self.monotonic = monotonic
        self.wall_now = wall_now or (lambda: datetime.now(timezone.utc).astimezone())
        self.writer = instance_id()
        now = self.monotonic()
        self.epoch_started = now
        self.pending_started = None
        self.signature = None
        self.epoch_number = 1
        self.last_state = None

    def reload(self, config):
        self.config = config
        self._new_epoch(self.monotonic())

    def _new_epoch(self, now):
        self.epoch_started = now
        self.pending_started = None
        self.epoch_number += 1

    @staticmethod
    def _disagreement(stable, observed):
        if not stable or not observed:
            return False
        conflicts = observed.get("conflicting_toplevels") or []
        if conflicts:
            return True
        observed_app = observed.get("application")
        stable_app = stable.get("application")
        observed_present = bool(
            observed.get("process_observed") or observed.get("toplevel_observed"))
        return bool(observed_present and observed_app in CONTROLLED_APPS
                    and observed_app != stable_app)

    def _signature(self, inputs, provider, required_health, activity_stale):
        stable = inputs.get("stable") or {}
        transition = inputs.get("transition") or {}
        activity = inputs.get("activity") or {}
        return (
            stable.get("application"), stable.get("request_id"),
            transition.get("request_id"), transition.get("phase"),
            provider.provider, provider.provider_context, provider.eligible,
            (inputs.get("kodi_state") or {}).get("writer_instance_id"),
            ((inputs.get("kodi_state") or {}).get("kodi_session") or {}).get(
                "pid"),
            ((inputs.get("kodi_state") or {}).get("kodi_session") or {}).get(
                "start_time_ticks"),
            (inputs.get("kodi_state") or {}).get("playback"),
            (inputs.get("kodi_state") or {}).get("health"),
            tuple(sorted(required_health.items())), inputs.get("display"),
            self._disagreement(inputs.get("stable"), inputs.get("observed")),
            activity_stale,
            activity.get("activity_generation"),
            self.config.enabled, self.config.stability_delay_seconds,
            provider.timeout_seconds,
        )

    def evaluate(self, inputs=None):
        now = self.monotonic()
        inputs = inputs or load_inputs(self.root, self.config.display_status_path)
        stable = inputs.get("stable")
        observed = inputs.get("observed")
        transition = inputs.get("transition")
        activity = inputs.get("activity")
        display = inputs.get("display", "unknown")
        provider = select_provider(stable, observed, self.config,
                                   inputs.get("kodi_state"), now)
        source_health = (activity or {}).get("source_health", {})
        activity_updated = (activity or {}).get("updated_monotonic")
        activity_stale = bool(
            activity and (activity_updated is None
                          or now - activity_updated
                          > self.config.activity_stale_seconds))
        required_health = {
            source: source_health.get(source, "missing")
            for source in provider.required_activity_sources
        }
        signature = self._signature(
            inputs, provider, required_health, activity_stale)
        if self.signature is None:
            self.signature = signature
        elif signature != self.signature:
            self.signature = signature
            self._new_epoch(now)

        state = "unknown"
        idle = False
        reasons = []
        inhibit_reasons = []
        idle_since = None
        application_health = "healthy"
        activity_health = "healthy"
        provider_health = "healthy"

        if not self.config.enabled:
            state, inhibit_reasons = "inhibited", ["idle-engine-disabled"]
        elif display not in {"connected", "on"}:
            state = "display-absent" if display == "disconnected" else "degraded"
            reasons.append(f"display-{display}")
            application_health = "degraded"
        elif transition:
            phase = transition.get("phase", "unknown")
            if phase == "returning":
                state, inhibit_reasons = "recovering", ["application-returning"]
            else:
                state, inhibit_reasons = "inhibited", [f"transition-{phase}"]
            application_health = "transitioning"
        elif not stable:
            state, reasons = "unknown", ["stable-state-unavailable"]
            application_health = "unknown"
        elif self._disagreement(stable, observed):
            state, reasons = "degraded", ["application-state-disagreement"]
            application_health = "degraded"
        elif not activity:
            state, reasons = "degraded", ["activity-state-unavailable"]
            activity_health = "unknown"
        elif activity_stale:
            state, reasons = "degraded", ["activity-state-stale"]
            activity_health = "degraded"
        elif provider.inhibit or not provider.eligible:
            state, inhibit_reasons = "inhibited", list(provider.reasons)
            provider_health = "inhibited"
        elif any(value != "healthy" for value in required_health.values()):
            state = "degraded"
            reasons = [f"activity-source-{name}-{health}"
                       for name, health in required_health.items()
                       if health != "healthy"]
            activity_health = "degraded"
        else:
            last_activity = activity.get("last_activity_monotonic")
            basis = max(self.epoch_started, last_activity or self.epoch_started)
            elapsed = max(0.0, now - basis)
            reasons = list(provider.reasons)
            if elapsed < provider.timeout_seconds:
                state = "active"
                self.pending_started = None
                reasons.append("idle-timeout-not-reached")
            elif self.pending_started is None:
                state = "idle-pending"
                self.pending_started = now
                reasons.append("stability-delay-started")
            elif now - self.pending_started < self.config.stability_delay_seconds:
                state = "idle-pending"
                reasons.append("stability-delay-running")
            else:
                state, idle = "idle", True
                idle_since = self.pending_started
                reasons.append("no-meaningful-input-for-timeout")
                reasons.append("stability-delay-passed")

        if state != "idle-pending" and not idle:
            self.pending_started = None
        result = {
            "writer_instance_id": self.writer,
            "wall_time": self.wall_now().isoformat(),
            "state": state,
            "idle": idle,
            "provider": provider.provider,
            "provider_context": provider.provider_context,
            "confidence": provider.confidence,
            "epoch_number": self.epoch_number,
            "epoch_started_monotonic": self.epoch_started,
            "idle_since_monotonic": idle_since,
            "timeout_seconds": provider.timeout_seconds,
            "last_activity_monotonic": (activity or {}).get(
                "last_activity_monotonic"),
            "activity_generation": (activity or {}).get("activity_generation"),
            "reasons": reasons,
            "inhibit_reasons": inhibit_reasons,
            "required_activity_sources": list(
                provider.required_activity_sources),
            "source_health": {
                "application_state": application_health,
                "activity": activity_health,
                "provider": provider_health,
                "required_activity_sources": required_health,
            },
        }
        self.last_state = write_json(
            self.root / "idle-state.json", result, self.writer)
        return self.last_state
