"""Overlay request validation and protocol constants."""

from dataclasses import dataclass

SCHEMA_VERSION = 1
RENDERERS = {"black", "slideshow"}
OVERLAY_TYPES = {"screensaver", "manual_blank", "notification", "loading", "recovery"}
PRIORITIES = {
    "notification": 10,
    "screensaver": 20,
    "manual_blank": 30,
    "loading": 40,
    "recovery": 50,
}
LEASE_MIN = 2.0
LEASE_MAX = 86400.0


class ProtocolError(ValueError):
    pass


@dataclass(frozen=True)
class RequestSpec:
    owner_service: str
    owner_instance_id: str
    owner_pid: int
    overlay_type: str
    renderer: str
    arguments: dict
    priority: int
    lease_seconds: float
    preemption_policy: str
    replace_token: str | None


def _identifier(value, name):
    if not isinstance(value, str) or not value or len(value) > 128:
        raise ProtocolError(f"invalid {name}")
    return value


def validate_request(message):
    if message.get("schema_version") != SCHEMA_VERSION:
        raise ProtocolError("unsupported schema_version")
    overlay_type = _identifier(message.get("overlay_type"), "overlay_type")
    renderer = _identifier(message.get("renderer"), "renderer")
    if overlay_type not in OVERLAY_TYPES:
        raise ProtocolError("unsupported overlay_type")
    if renderer not in RENDERERS:
        raise ProtocolError("unsupported renderer")
    arguments = message.get("arguments", {})
    if not isinstance(arguments, dict):
        raise ProtocolError("arguments must be an object")
    allowed = {
        "black": {"output"},
        "slideshow": {
            "output", "image_directory", "recursive", "image_duration",
            "fit_mode", "shuffle", "extensions", "max_files",
            "max_file_bytes", "max_decode_dimension", "rescan_interval",
        },
    }[renderer]
    if set(arguments) - allowed:
        raise ProtocolError("unsupported renderer argument")
    if len(str(arguments.get("output", ""))) > 128:
        raise ProtocolError("invalid output")
    if arguments.get("fit_mode", "contain") not in {"contain", "cover"}:
        raise ProtocolError("invalid fit_mode")
    if renderer == "slideshow":
        if len(str(arguments.get("image_directory", ""))) > 4096:
            raise ProtocolError("invalid image_directory")
        duration = float(arguments.get("image_duration", 30.0))
        if not 1.0 <= duration <= 86400.0:
            raise ProtocolError("invalid image_duration")
        maximum = int(arguments.get("max_files", 5000))
        if not 1 <= maximum <= 50000:
            raise ProtocolError("invalid max_files")
        extensions = arguments.get("extensions", [])
        if not isinstance(extensions, list) or len(extensions) > 32:
            raise ProtocolError("invalid extensions")
        file_bytes = int(arguments.get("max_file_bytes", 268435456))
        if not 1048576 <= file_bytes <= 1073741824:
            raise ProtocolError("invalid max_file_bytes")
        dimension = int(arguments.get("max_decode_dimension", 8192))
        if not 1024 <= dimension <= 16384:
            raise ProtocolError("invalid max_decode_dimension")
        interval = int(arguments.get("rescan_interval", 30))
        if not 5 <= interval <= 3600:
            raise ProtocolError("invalid rescan_interval")
    lease = float(message.get("lease_seconds", 300.0))
    if not LEASE_MIN <= lease <= LEASE_MAX:
        raise ProtocolError("invalid lease_seconds")
    policy = message.get("preemption_policy", "cancel")
    if policy not in {"cancel", "retain"}:
        raise ProtocolError("invalid preemption_policy")
    expected_priority = PRIORITIES[overlay_type]
    priority = int(message.get("priority", expected_priority))
    if priority != expected_priority:
        raise ProtocolError("priority must match overlay type")
    token = message.get("replace_token")
    if token is not None and (not isinstance(token, str) or len(token) != 32):
        raise ProtocolError("invalid replace_token")
    return RequestSpec(
        _identifier(message.get("owner_service"), "owner_service"),
        _identifier(message.get("owner_instance_id"), "owner_instance_id"),
        int(message.get("owner_pid", 0)),
        overlay_type, renderer, dict(arguments), priority, lease, policy, token,
    )
