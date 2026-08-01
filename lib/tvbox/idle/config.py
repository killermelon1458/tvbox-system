"""Idle engine TOML configuration."""

from dataclasses import dataclass
from pathlib import Path
import tomllib


class IdleConfigError(ValueError):
    pass


@dataclass(frozen=True)
class ProviderConfig:
    enabled: bool
    timeout_seconds: float
    required_sources: tuple
    observer_stale_seconds: float = 5.0


@dataclass(frozen=True)
class IdleConfig:
    enabled: bool
    stability_delay_seconds: float
    poll_interval_seconds: float
    pointer_distance_px: float
    pointer_window_ms: int
    device_rescan_seconds: float
    activity_stale_seconds: float
    exclude_virtual_device_names: tuple
    exclude_controller_hid: bool
    display_status_path: str
    providers: dict
    path: str


def load_config(path):
    path = Path(path)
    try:
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise IdleConfigError(str(exc)) from exc
    global_config = raw.get("global", {})
    activity = raw.get("activity", {})
    stability = float(global_config.get("stability_delay_seconds", 3.0))
    poll = float(global_config.get("poll_interval_seconds", 0.25))
    rescan = float(activity.get("device_rescan_seconds", 2.0))
    stale = float(activity.get("activity_stale_seconds", 5.0))
    distance = float(activity.get("pointer_distance_px", 12.0))
    window = int(activity.get("pointer_window_ms", 500))
    if not 0 <= stability <= 60:
        raise IdleConfigError("stability_delay_seconds out of range")
    if not 0.05 <= poll <= 10:
        raise IdleConfigError("poll_interval_seconds out of range")
    if not 0.25 <= rescan <= 60:
        raise IdleConfigError("device_rescan_seconds out of range")
    if not 1 <= stale <= 300:
        raise IdleConfigError("activity_stale_seconds out of range")
    if not 1 <= distance <= 1000 or not 50 <= window <= 10000:
        raise IdleConfigError("pointer activity threshold out of range")
    provider_values = {}
    for name in ("desktop", "kodi", "spotify", "youtube", "moonlight",
                 "steamlink", "mariokart64", "unknown"):
        value = raw.get("providers", {}).get(name, {})
        timeout = float(value.get("timeout_seconds", 300.0))
        if not 1 <= timeout <= 86400:
            raise IdleConfigError(f"provider timeout out of range: {name}")
        required = tuple(value.get("required_sources", ["keyboard", "pointer"]))
        if any(source not in {"keyboard", "pointer", "flirc"}
               for source in required):
            raise IdleConfigError(f"invalid required source: {name}")
        observer_stale = float(value.get("observer_stale_seconds", 5.0))
        if not 1 <= observer_stale <= 300:
            raise IdleConfigError(f"observer stale interval out of range: {name}")
        provider_values[name] = ProviderConfig(
            bool(value.get("enabled", name == "desktop")), timeout, required,
            observer_stale)
    return IdleConfig(
        bool(global_config.get("enabled", True)), stability, poll, distance,
        window, rescan, stale,
        tuple(str(value).lower() for value in activity.get(
            "exclude_virtual_device_names", [
                "antimicrox Keyboard Emulation",
                "antimicrox Mouse Emulation",
                "antimicrox Abs Mouse Emulation",
            ])),
        bool(activity.get("exclude_controller_hid", True)),
        str(global_config.get(
            "display_status_path", "/sys/class/drm/card1-HDMI-A-2/status")),
        provider_values, str(path),
    )
