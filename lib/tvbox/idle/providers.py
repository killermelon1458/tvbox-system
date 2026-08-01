"""Pure application-specific idle eligibility providers."""

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class ProviderResult:
    schema_version: int
    provider: str
    provider_context: str
    applies: bool
    eligible: bool
    timeout_seconds: float | None
    required_activity_sources: tuple
    confidence: str
    inhibit: bool
    reasons: tuple

    def to_dict(self):
        value = asdict(self)
        value["required_activity_sources"] = list(self.required_activity_sources)
        value["reasons"] = list(self.reasons)
        return value


def _inhibited(name, context, reason, confidence="high"):
    return ProviderResult(
        1, name, context, True, False, None, (), confidence, True, (reason,))


def _kodi_session_matches(observed, kodi_state):
    session = (kodi_state or {}).get("kodi_session") or {}
    processes = (observed or {}).get("current_processes") or []
    for process in processes:
        if (process.get("pid") == session.get("pid")
                and process.get("start_time_ticks")
                == session.get("start_time_ticks")
                and process.get("executable") == session.get("executable")):
            return True
    return False


def select_provider(stable, observed, config, kodi_state=None,
                    now_monotonic=None):
    application = (stable or {}).get("application", "unknown")
    provider_config = config.providers.get(
        application, config.providers["unknown"])
    if application == "desktop":
        if not provider_config.enabled:
            return _inhibited("desktop", "stable-desktop", "provider-disabled")
        return ProviderResult(
            1, "desktop", "stable-desktop", True, True,
            provider_config.timeout_seconds, provider_config.required_sources,
            "high", False, ("stable-desktop",))
    if application == "kodi":
        if not provider_config.enabled:
            return _inhibited("kodi", "kodi-unknown", "provider-disabled")
        if not (observed or {}).get("process_observed"):
            return _inhibited("kodi", "kodi-not-stable", "kodi-process-missing")
        if not (observed or {}).get("toplevel_observed"):
            return _inhibited("kodi", "kodi-not-stable", "kodi-toplevel-missing")
        if not kodi_state:
            return _inhibited("kodi", "kodi-observer-unknown",
                              "kodi-observer-unavailable", "unknown")
        if kodi_state.get("health") != "healthy":
            return _inhibited("kodi", "kodi-observer-unhealthy",
                              "kodi-observer-unhealthy", "unknown")
        updated = kodi_state.get("updated_monotonic")
        if (now_monotonic is None or not isinstance(updated, (int, float))
                or now_monotonic - updated > provider_config.observer_stale_seconds
                or updated > now_monotonic + 1):
            return _inhibited("kodi", "kodi-observer-stale",
                              "kodi-observer-stale", "unknown")
        if not _kodi_session_matches(observed, kodi_state):
            return _inhibited("kodi", "kodi-session-mismatch",
                              "kodi-session-mismatch", "unknown")
        playback = kodi_state.get("playback", "unknown")
        if playback == "stopped":
            return ProviderResult(
                1, "kodi", "stopped-anywhere", True, True,
                provider_config.timeout_seconds,
                provider_config.required_sources, "high", False,
                ("stable-kodi", "kodi-playback-stopped"))
        if playback not in {"starting", "playing", "paused", "unknown"}:
            playback = "unknown"
        return _inhibited("kodi", f"playback-{playback}",
                          f"kodi-playback-{playback}")
    if application in config.providers:
        return _inhibited(application, f"stable-{application}",
                          "provider-disabled-v1")
    return _inhibited("unknown", "unknown-context", "unsupported-context",
                      "low")
