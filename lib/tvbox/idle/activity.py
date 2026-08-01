"""Passive evdev activity collection without grabs."""

from dataclasses import dataclass
from datetime import datetime
import math
import os
from pathlib import Path
import selectors
import struct
import time

from tvbox.runtime import instance_id, read_json, runtime_root, write_json


EV_KEY = 0x01
EV_REL = 0x02
REL_X = 0x00
REL_Y = 0x01
BTN_MOUSE = 0x110
INPUT_EVENT = struct.Struct("llHHi")


@dataclass(frozen=True)
class DeviceInfo:
    node: str
    identity: str
    name: str
    classes: tuple
    excluded_reason: str | None = None


def _capability(path):
    try:
        return int(Path(path).read_text().replace(" ", "").strip() or "0", 16)
    except (OSError, ValueError):
        return 0


def _by_id_map(root=Path("/dev/input/by-id")):
    result = {}
    try:
        entries = list(root.iterdir())
    except OSError:
        return result
    for entry in entries:
        try:
            target = str(entry.resolve(strict=True))
        except OSError:
            continue
        result.setdefault(target, []).append(str(entry))
    return result


def classify_device(node, sys_root=Path("/sys/class/input"), by_id=None,
                    excluded_names=(), exclude_controller_hid=True):
    node = Path(node)
    event = node.name
    base = Path(sys_root) / event / "device"
    try:
        name = (base / "name").read_text(encoding="utf-8").strip()
    except OSError:
        return DeviceInfo(str(node), str(node), "unknown", (), "missing-name")
    lowered = name.lower()
    identities = (by_id or {}).get(str(node), [])
    identity = sorted(identities)[0] if identities else str(node)
    if any(value in lowered for value in excluded_names):
        return DeviceInfo(str(node), identity, name, (), "excluded-virtual")
    if "antimicro" in lowered:
        return DeviceInfo(str(node), identity, name, (), "excluded-antimicrox")
    if exclude_controller_hid and (
            "controller keyboard" in lowered or "controller mouse" in lowered):
        return DeviceInfo(str(node), identity, name, (), "excluded-controller-hid")
    if any(value in lowered for value in (
            "x-box", "gamepad", "joystick", "system control",
            "consumer control", "power button", "pwr_button", "hdmi")):
        return DeviceInfo(str(node), identity, name, (), "unsupported-device-class")
    rel = _capability(base / "capabilities" / "rel")
    classes = []
    is_flirc = "flirc" in lowered
    by_id_keyboard = any(value.endswith("-event-kbd") for value in identities)
    by_id_pointer = any(value.endswith("-event-mouse") for value in identities)
    if is_flirc or by_id_keyboard or (not identities and any(
            value in lowered for value in ("keyboard", " k360"))):
        classes.append("keyboard")
    if is_flirc:
        classes.append("flirc")
    if by_id_pointer or (not identities and (
            ((rel & (1 << REL_X)) and (rel & (1 << REL_Y))) or any(
                value in lowered for value in ("mouse", "trackball", "touchpad")))):
        if not is_flirc:
            classes.append("pointer")
    if not classes:
        return DeviceInfo(str(node), identity, name, (), "unsupported-device-class")
    return DeviceInfo(str(node), identity, name, tuple(sorted(set(classes))))


def discover_devices(dev_root=Path("/dev/input"), sys_root=Path("/sys/class/input"),
                     excluded_names=(), exclude_controller_hid=True):
    by_id = _by_id_map(Path(dev_root) / "by-id")
    try:
        nodes = sorted(Path(dev_root).glob("event*"))
    except OSError:
        nodes = []
    return [classify_device(
        node, sys_root, by_id, excluded_names, exclude_controller_hid)
        for node in nodes]


class ActivityTracker:
    def __init__(self, pointer_distance_px=12, pointer_window_ms=500,
                 monotonic=time.monotonic):
        self.pointer_distance_px = pointer_distance_px
        self.pointer_window = pointer_window_ms / 1000
        self.monotonic = monotonic
        self.motion_x = self.motion_y = 0
        self.motion_started = None

    def feed(self, event_type, code, value):
        now = self.monotonic()
        if event_type == EV_KEY:
            if value == 1:
                return "pointer-button" if code >= BTN_MOUSE else "key-down"
            return None
        if event_type != EV_REL or code not in {REL_X, REL_Y} or value == 0:
            return None
        if self.motion_started is None or now - self.motion_started > self.pointer_window:
            self.motion_started = now
            self.motion_x = self.motion_y = 0
        if code == REL_X:
            self.motion_x += value
        else:
            self.motion_y += value
        if math.hypot(self.motion_x, self.motion_y) >= self.pointer_distance_px:
            self.motion_started = None
            self.motion_x = self.motion_y = 0
            return "pointer-motion"
        return None


class ActivityCollector:
    def __init__(self, config, root=None, monotonic=time.monotonic,
                 wall_time=time.time, dev_root=Path("/dev/input"),
                 sys_root=Path("/sys/class/input"), opener=os.open):
        self.config = config
        self.root = Path(root) if root else runtime_root()
        self.monotonic = monotonic
        self.wall_time = wall_time
        self.dev_root, self.sys_root, self.opener = Path(dev_root), Path(sys_root), opener
        self.writer = instance_id()
        previous = read_json(self.root / "activity-state.json") or {}
        self.last_activity_monotonic = previous.get("last_activity_monotonic")
        self.last_activity_wall_time = previous.get("last_activity_wall_time")
        self.last_activity_class = previous.get("last_activity_class")
        self.last_activity_source = previous.get("last_activity_source")
        self.activity_generation = int(previous.get("activity_generation", 0))
        self.selector = selectors.DefaultSelector()
        self.open_devices = {}
        self.inventory = []
        self.errors = {}
        self.trackers = {}

    def close(self):
        for fd in list(self.open_devices):
            self._close_fd(fd)
        self.selector.close()

    def _close_fd(self, fd):
        try:
            self.selector.unregister(fd)
        except Exception:
            pass
        try:
            os.close(fd)
        except OSError:
            pass
        self.open_devices.pop(fd, None)

    def rescan(self):
        inventory = discover_devices(
            self.dev_root, self.sys_root, self.config.exclude_virtual_device_names,
            self.config.exclude_controller_hid)
        wanted = {item.node: item for item in inventory if item.classes}
        self.errors = {node: error for node, error in self.errors.items()
                       if node in wanted}
        existing = {item.node: fd for fd, item in self.open_devices.items()}
        for node, fd in existing.items():
            if node not in wanted:
                self._close_fd(fd)
        for node, item in wanted.items():
            if node in existing:
                continue
            try:
                fd = self.opener(node, os.O_RDONLY | os.O_NONBLOCK)
                self.selector.register(fd, selectors.EVENT_READ)
                self.open_devices[fd] = item
                self.trackers[item.identity] = ActivityTracker(
                    self.config.pointer_distance_px, self.config.pointer_window_ms,
                    self.monotonic)
                self.errors.pop(node, None)
            except OSError as exc:
                self.errors[node] = f"{exc.__class__.__name__}:{exc.errno}"
        self.inventory = inventory
        self.publish()

    def record(self, item, activity_class):
        now = self.monotonic()
        self.last_activity_monotonic = now
        wall = self.wall_time()
        self.last_activity_wall_time = datetime.fromtimestamp(
            wall).astimezone().isoformat()
        self.last_activity_class = activity_class
        self.last_activity_source = item.identity
        self.activity_generation += 1
        self.publish()

    def process_bytes(self, item, data):
        tracker = self.trackers.setdefault(item.identity, ActivityTracker(
            self.config.pointer_distance_px, self.config.pointer_window_ms,
            self.monotonic))
        for offset in range(0, len(data) - INPUT_EVENT.size + 1, INPUT_EVENT.size):
            _sec, _usec, event_type, code, value = INPUT_EVENT.unpack_from(data, offset)
            activity_class = tracker.feed(event_type, code, value)
            if activity_class:
                self.record(item, activity_class)

    def poll(self, timeout):
        for key, _mask in self.selector.select(timeout):
            fd = key.fd
            item = self.open_devices.get(fd)
            if not item:
                continue
            try:
                data = os.read(fd, INPUT_EVENT.size * 64)
                if not data:
                    self.errors[item.node] = "device-closed"
                    self._close_fd(fd)
                else:
                    self.process_bytes(item, data)
            except BlockingIOError:
                continue
            except OSError as exc:
                self.errors[item.node] = f"{exc.__class__.__name__}:{exc.errno}"
                self._close_fd(fd)
        self.publish()

    def snapshot(self):
        approved = [item for item in self.inventory if item.classes]
        open_nodes = {item.node for item in self.open_devices.values()}
        available = sorted({activity_class for item in approved
                            if item.node in open_nodes for activity_class in item.classes})
        source_health = {
            source: ("healthy" if source in available else "missing")
            for source in ("keyboard", "pointer", "flirc")
        }
        return {
            "writer_instance_id": self.writer,
            "health": "healthy" if available and not self.errors else "degraded",
            "available_sources": available,
            "source_health": source_health,
            "source_errors": dict(sorted(self.errors.items())),
            "devices": [{
                "node": item.node, "identity": item.identity, "name": item.name,
                "classes": list(item.classes), "open": item.node in open_nodes,
                "excluded_reason": item.excluded_reason,
            } for item in self.inventory],
            "last_activity_monotonic": self.last_activity_monotonic,
            "last_activity_wall_time": self.last_activity_wall_time,
            "last_activity_class": self.last_activity_class,
            "last_activity_source": self.last_activity_source,
            "activity_generation": self.activity_generation,
        }

    def publish(self):
        return write_json(self.root / "activity-state.json", self.snapshot(), self.writer)
