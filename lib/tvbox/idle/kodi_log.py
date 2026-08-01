"""Incremental, privacy-preserving Kodi player-event follower."""

from pathlib import Path
import os
import re

from tvbox.idle.kodi_observer import KodiObservationWriter, process_identity


EVENT_RE = re.compile(
    rb"Notification:\s+xbmc\s+(Player\.(?:OnPlay|OnAVStart|OnPause|OnResume|OnStop|OnEnd))(?:\s|$)")


def find_kodi_process(proc_root=Path("/proc")):
    try:
        entries = list(Path(proc_root).iterdir())
    except OSError:
        return None
    for entry in entries:
        if not entry.name.isdigit():
            continue
        identity = process_identity(int(entry.name))
        if identity and Path(identity["executable"]).name in {"kodi", "kodi.bin"}:
            return identity
    return None


class KodiLogFollower:
    def __init__(self, path, writer, identity_getter=find_kodi_process):
        self.path = Path(path)
        self.writer = writer
        self.identity_getter = identity_getter
        self.identity = None
        self.file_identity = None
        self.offset = 0
        self.partial = b""

    def _reset(self, identity, reason):
        self.identity = identity
        self.writer.identity = identity
        self.writer.playback = "unknown"
        self.writer.health = "healthy" if identity else "unhealthy"
        self.writer.confidence = "unknown"
        self.writer.reasons = [reason]
        self.writer.last_event = None
        self.writer.last_event_monotonic = None
        self.file_identity = None
        self.offset = 0
        self.partial = b""

    @staticmethod
    def _same_session(left, right):
        return bool(left and right and all(
            left.get(key) == right.get(key)
            for key in ("pid", "start_time_ticks", "executable")))

    def poll(self):
        identity = self.identity_getter()
        if not self._same_session(identity, self.identity):
            self._reset(identity, "kodi-session-changed" if identity
                        else "kodi-process-unavailable")
            # A new session starts at the current EOF. Old lines, including
            # prior-session events, are never authority.
            if identity:
                try:
                    stat_result = self.path.stat()
                    self.file_identity = (stat_result.st_dev, stat_result.st_ino)
                    self.offset = stat_result.st_size
                except OSError:
                    pass
            return self.writer.publish()
        if not identity:
            return self.writer.publish()
        try:
            stat_result = self.path.stat()
            current_file = (stat_result.st_dev, stat_result.st_ino)
            if self.file_identity is None:
                self.file_identity = current_file
                self.offset = stat_result.st_size
                return self.writer.publish()
            if current_file != self.file_identity:
                self.writer.playback = "unknown"
                self.writer.health = "degraded"
                self.writer.confidence = "unknown"
                self.writer.reasons = ["kodi-log-rotated"]
                self.file_identity = current_file
                self.offset = 0
                self.partial = b""
            elif stat_result.st_size < self.offset:
                self.writer.playback = "unknown"
                self.writer.health = "degraded"
                self.writer.confidence = "unknown"
                self.writer.reasons = ["kodi-log-truncated"]
                self.offset = 0
                self.partial = b""
            with self.path.open("rb") as stream:
                stream.seek(self.offset)
                data = stream.read()
                self.offset = stream.tell()
        except OSError:
            self.writer.playback = "unknown"
            self.writer.health = "unhealthy"
            self.writer.confidence = "unknown"
            self.writer.reasons = ["kodi-log-unavailable"]
            return self.writer.publish()
        if data:
            chunks = (self.partial + data).split(b"\n")
            self.partial = chunks.pop()
            for line in chunks:
                match = EVENT_RE.search(line)
                if match:
                    self.writer.apply_event(match.group(1).decode("ascii"))
        return self.writer.publish()
