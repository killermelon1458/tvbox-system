"""Boot-local TVBox runtime paths and atomic JSON."""

import json
import os
from pathlib import Path
import tempfile
import time
import uuid

SCHEMA_VERSION = 1


def runtime_root():
    override = os.environ.get("TVBOX_RUNTIME_ROOT")
    if override:
        root = Path(override)
    else:
        xdg = os.environ.get("XDG_RUNTIME_DIR")
        if not xdg:
            raise RuntimeError("XDG_RUNTIME_DIR is required")
        root = Path(xdg) / "tvbox"
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(root, 0o700)
    return root


def boot_id():
    value = os.environ.get("TVBOX_BOOT_ID")
    if value:
        return value
    try:
        return Path("/proc/sys/kernel/random/boot_id").read_text().strip()
    except OSError:
        return "unknown"


def instance_id():
    return str(uuid.uuid4())


def metadata(writer):
    return {
        "schema_version": SCHEMA_VERSION,
        "boot_id": boot_id(),
        "writer_instance": writer,
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "updated_monotonic": time.monotonic(),
    }


def atomic_json(path, value, mode=0o600):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        os.fchmod(fd, mode)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, sort_keys=True, separators=(",", ":"))
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


def read_json(path, same_boot=True):
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(value, dict) or value.get("schema_version") != SCHEMA_VERSION:
            return None
        if same_boot and value.get("boot_id") != boot_id():
            return None
        return value
    except (OSError, ValueError, TypeError):
        return None


def write_json(path, fields, writer):
    value = {**fields, **metadata(writer)}
    atomic_json(path, value)
    return value
