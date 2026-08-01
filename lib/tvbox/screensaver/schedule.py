"""Timezone-aware fixed local-time screensaver schedules."""

from dataclasses import dataclass
from datetime import datetime, time, timedelta
from pathlib import Path
import tomllib
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

MODES = {"black", "slideshow"}


class ConfigError(ValueError):
    pass


@dataclass(frozen=True)
class Rule:
    start: time
    end: time
    mode: str
    index: int

    def matches(self, local_time):
        if self.start == self.end:
            return True
        if self.start < self.end:
            return self.start <= local_time < self.end
        return local_time >= self.start or local_time < self.end


@dataclass(frozen=True)
class ScreensaverConfig:
    default_mode: str
    timezone: ZoneInfo
    rules: tuple
    image_directory: str
    recursive: bool
    image_duration: float
    fit_mode: str
    shuffle: bool
    extensions: tuple
    max_files: int
    max_file_bytes: int
    max_decode_dimension: int
    rescan_interval: int
    output: str
    automatic_enabled: bool
    idle_state_stale_seconds: float
    reconcile_interval_seconds: float
    suppress_after_manual_stop: str
    config_path: str | None = None


def parse_clock(value):
    try:
        hour, minute = value.split(":")
        parsed = time(int(hour), int(minute))
    except (AttributeError, ValueError, TypeError):
        raise ConfigError(f"invalid local time: {value!r}") from None
    return parsed


def load_config(path):
    path = Path(path)
    try:
        value = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ConfigError(str(exc)) from exc
    saver = value.get("screensaver", {})
    default = saver.get("default_mode", "slideshow")
    if default not in MODES:
        raise ConfigError("invalid default_mode")
    try:
        timezone = ZoneInfo(saver.get("timezone", "UTC"))
    except ZoneInfoNotFoundError as exc:
        raise ConfigError("unknown timezone") from exc
    rules = []
    for index, raw in enumerate(saver.get("schedule", [])):
        mode = raw.get("mode")
        if mode not in MODES:
            raise ConfigError("invalid schedule mode")
        rules.append(Rule(parse_clock(raw.get("start")),
                          parse_clock(raw.get("end")), mode, index))
    slideshow = value.get("slideshow", {})
    fit = slideshow.get("fit_mode", "contain")
    if fit not in {"contain", "cover"}:
        raise ConfigError("invalid slideshow fit_mode")
    duration = float(slideshow.get("image_duration", 30.0))
    if duration < 1.0:
        raise ConfigError("image_duration must be at least one second")
    max_files = int(slideshow.get("max_files", 5000))
    if not 1 <= max_files <= 50000:
        raise ConfigError("max_files out of range")
    configured_extensions = tuple(
        str(item).lower().lstrip(".")
        for item in slideshow.get("supported_image_types",
                                  ["jpg", "jpeg", "png", "webp", "heic",
                                   "heif", "avif", "gif", "tif", "tiff", "bmp"])
    )
    required_extensions = ("jpg", "jpeg", "png", "webp", "heic", "heif", "avif")
    extensions = tuple(dict.fromkeys(required_extensions + configured_extensions))
    max_file_bytes = int(slideshow.get("max_file_bytes", 268435456))
    if not 1048576 <= max_file_bytes <= 1073741824:
        raise ConfigError("max_file_bytes out of range")
    max_decode_dimension = int(slideshow.get("max_decode_dimension", 8192))
    if not 1024 <= max_decode_dimension <= 16384:
        raise ConfigError("max_decode_dimension out of range")
    rescan_interval = int(slideshow.get("rescan_interval", 30))
    if not 5 <= rescan_interval <= 3600:
        raise ConfigError("rescan_interval out of range")
    if slideshow.get("recursive", True) is not True:
        raise ConfigError("slideshow recursive discovery cannot be disabled")
    automatic = saver.get("automatic", {})
    automatic_enabled = bool(automatic.get("enabled", True))
    idle_stale = float(automatic.get("idle_state_stale_seconds", 5.0))
    reconcile_interval = float(
        automatic.get("reconcile_interval_seconds", 1.0))
    suppression = automatic.get(
        "suppress_after_manual_stop", "until-next-idle-epoch")
    if not 1.0 <= idle_stale <= 60.0:
        raise ConfigError("idle_state_stale_seconds out of range")
    if not 0.25 <= reconcile_interval <= 10.0:
        raise ConfigError("reconcile_interval_seconds out of range")
    if suppression != "until-next-idle-epoch":
        raise ConfigError("invalid automatic suppression policy")
    return ScreensaverConfig(
        default, timezone, tuple(rules),
        str(slideshow.get("image_directory",
                          str(Path.home() / "Pictures" / "Screensaver"))),
        True, duration, fit,
        bool(slideshow.get("shuffle", True)), extensions, max_files,
        max_file_bytes, max_decode_dimension, rescan_interval,
        str(saver.get("output", "")), automatic_enabled, idle_stale,
        reconcile_interval, suppression, str(path),
    )


def scheduled_mode(config, moment):
    local = moment.astimezone(config.timezone)
    # Later entries deterministically win if ranges overlap.
    selected = config.default_mode
    for rule in config.rules:
        if rule.matches(local.timetz().replace(tzinfo=None)):
            selected = rule.mode
    return selected


def next_boundary(config, moment):
    local = moment.astimezone(config.timezone)
    candidates = []
    for day_offset in range(0, 4):
        day = local.date() + timedelta(days=day_offset)
        for rule in config.rules:
            for boundary in (rule.start, rule.end):
                candidate = datetime.combine(day, boundary, config.timezone)
                if candidate > local:
                    candidates.append(candidate)
    if not candidates:
        return None
    # Re-evaluate around DST ambiguity/nonexistence through zone conversion.
    return min(candidates).astimezone(config.timezone)
