"""Privacy-preserving current-session Kodi playback observations."""

from pathlib import Path
import os
import time

from tvbox.runtime import instance_id, runtime_root, write_json


EVENT_STATES = {
    "Player.OnPlay": "starting",
    "Player.OnAVStart": "playing",
    "Player.OnResume": "playing",
    "Player.OnPause": "paused",
    "Player.OnStop": "stopped",
    "Player.OnEnd": "stopped",
}


def process_identity(pid=None):
    pid = int(pid if pid is not None else os.getpid())
    try:
        fields = Path(f"/proc/{pid}/stat").read_text(
            encoding="utf-8").rsplit(")", 1)[1].split()
        start_ticks = int(fields[19])
        executable = os.readlink(f"/proc/{pid}/exe")
    except (OSError, ValueError, IndexError):
        return None
    return {"pid": pid, "start_time_ticks": start_ticks,
            "executable": executable}


class KodiObservationWriter:
    """Normalize callbacks and publish only allowlisted non-media facts."""

    def __init__(self, root=None, identity=None, monotonic=time.monotonic,
                 writer=None):
        self.root = Path(root) if root else runtime_root()
        self.identity = identity
        self.monotonic = monotonic
        self.writer = writer or instance_id()
        self.playback = "unknown"
        self.health = "starting"
        self.confidence = "unknown"
        self.reasons = ["current-state-not-established"]
        self.event_generation = 0
        self.last_event = None
        self.last_event_monotonic = None

    def establish_current_state(self, is_playing):
        self.playback = "playing" if bool(is_playing) else "stopped"
        self.health = "healthy"
        self.confidence = "high"
        self.reasons = ["kodi-current-player-api"]
        self.event_generation += 1
        self.last_event = "CurrentState"
        self.last_event_monotonic = self.monotonic()

    def apply_event(self, event, event_monotonic=None):
        event_monotonic = (self.monotonic() if event_monotonic is None
                           else float(event_monotonic))
        if event not in EVENT_STATES:
            self.playback = "unknown"
            self.health = "degraded"
            self.confidence = "unknown"
            self.reasons = ["unrecognized-player-event"]
            return False
        if (self.last_event_monotonic is not None
                and event_monotonic < self.last_event_monotonic):
            self.playback = "unknown"
            self.health = "degraded"
            self.confidence = "unknown"
            self.reasons = ["out-of-order-player-event"]
            return False
        self.playback = EVENT_STATES[event]
        self.health = "healthy"
        self.confidence = "high"
        self.reasons = ["native-player-callback"]
        self.event_generation += 1
        self.last_event = event
        self.last_event_monotonic = event_monotonic
        return True

    def mark_unhealthy(self, reason):
        self.playback = "unknown"
        self.health = "unhealthy"
        self.confidence = "unknown"
        self.reasons = [str(reason)]

    def record(self, window_id=None):
        # Never accept or publish arbitrary callback payloads, media paths,
        # labels, titles, URLs, tokens, or credentials.
        return {
            "writer_instance_id": self.writer,
            "kodi_session": self.identity,
            "playback": self.playback,
            "view": {"window_id": window_id, "classification": "unknown"},
            "health": self.health,
            "confidence": self.confidence,
            "reasons": list(self.reasons),
            "event_generation": self.event_generation,
            "last_event": self.last_event,
            "last_event_monotonic": self.last_event_monotonic,
        }

    def publish(self, window_id=None):
        return write_json(self.root / "kodi-state.json",
                          self.record(window_id), self.writer)
