"""Persistent manual/schedule screensaver policy service."""

from datetime import datetime
import json
import os
from pathlib import Path
import socket
import threading
import time
import sys

from tvbox.runtime import instance_id, read_json, runtime_root, write_json
from tvbox.screensaver.schedule import load_config, next_boundary, scheduled_mode


def socket_request(path, message, timeout=10.0):
    client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    client.settimeout(timeout)
    client.connect(str(path))
    client.sendall(json.dumps(message).encode() + b"\n")
    data = b""
    while b"\n" not in data:
        chunk = client.recv(65536)
        if not chunk:
            break
        data += chunk
    client.close()
    return json.loads(data.split(b"\n", 1)[0])


class ScreensaverPolicy:
    def __init__(self, config_path, root=None, now=None, monotonic=time.monotonic):
        self.root = Path(root) if root else runtime_root()
        self.config_path = Path(config_path)
        self.config = load_config(self.config_path)
        self.instance_id = instance_id()
        self.now = now or (lambda: datetime.now(self.config.timezone))
        self.monotonic = monotonic
        previous = read_json(self.root / "screensaver-policy.json") or {}
        saved_override = previous.get("manual_override")
        self.manual_override = (
            saved_override if saved_override in {"black", "slideshow"} else None)
        self.active_requested = bool(previous.get("active_requested", False))
        self.active_token = previous.get("active_request_id")
        self.active_generation = previous.get("active_generation")
        self.active_mode = previous.get("active_mode")
        self.last_error = previous.get("last_error")
        self.lease_seconds = 120.0
        self.last_renewal = 0.0
        self.overlay_socket = self.root / "overlay.sock"
        self.state_path = self.root / "screensaver-policy.json"
        self.lock = threading.RLock()
        self.publish()

    def schedule_facts(self):
        moment = self.now()
        scheduled = scheduled_mode(self.config, moment)
        effective = self.manual_override or scheduled or self.config.default_mode
        boundary = next_boundary(self.config, moment)
        return moment, scheduled, effective, boundary

    def renderer_arguments(self, mode):
        arguments = {"output": self.config.output}
        if mode == "slideshow":
            arguments.update({
                "image_directory": self.config.image_directory,
                "recursive": self.config.recursive,
                "image_duration": self.config.image_duration,
                "fit_mode": self.config.fit_mode,
                "shuffle": self.config.shuffle,
                "extensions": list(self.config.extensions),
                "max_files": self.config.max_files,
                "max_file_bytes": self.config.max_file_bytes,
                "max_decode_dimension": self.config.max_decode_dimension,
                "rescan_interval": self.config.rescan_interval,
            })
        return arguments

    def overlay(self, message):
        return socket_request(self.overlay_socket, message)

    def start(self):
        with self.lock:
            self.active_requested = True
            _, scheduled, effective, _ = self.schedule_facts()
            if self.active_token:
                return self.replace_if_needed(effective)
            response = self.overlay({
                "schema_version": 1, "command": "request",
                "owner_service": "tvbox-screensaver-policy",
                "owner_instance_id": self.instance_id,
                "owner_pid": os.getpid(), "overlay_type": "screensaver",
                "renderer": effective,
                "arguments": self.renderer_arguments(effective),
                "priority": 20, "lease_seconds": self.lease_seconds,
                "preemption_policy": "cancel",
            })
            if not response.get("ok"):
                raise RuntimeError(response.get("error", "overlay request failed"))
            self.active_token = response["request_id"]
            self.active_generation = response["generation"]
            self.active_mode = effective
            self.last_error = None
            self.last_renewal = self.monotonic()
            self.publish()
            return self.status()

    def stop(self):
        with self.lock:
            self.active_requested = False
            if not self.active_token:
                return self.status()
            token = self.active_token
            response = self.overlay({"command": "release", "request_id": token})
            if response.get("ok") or response.get("error"):
                self.active_token = None
                self.active_generation = None
                self.active_mode = None
                self.last_error = None
            self.publish()
            return self.status()

    def shutdown(self):
        """Release this instance's token without clearing persisted intent."""
        with self.lock:
            token = self.active_token
            if token:
                try:
                    self.overlay({"command": "release", "request_id": token})
                except (OSError, RuntimeError, ValueError):
                    pass
            self.active_token = None
            self.active_generation = None
            self.active_mode = None
            self.publish()

    def invalidate(self, token=None):
        with self.lock:
            if not self.active_token:
                return self.status()
            if token is not None and token != self.active_token:
                raise RuntimeError("stale screensaver token")
            return self.stop()

    def set_mode(self, mode):
        if mode not in {"black", "slideshow", "scheduled"}:
            raise ValueError("unsupported mode")
        with self.lock:
            self.manual_override = None if mode == "scheduled" else mode
            effective = self.schedule_facts()[2]
            if self.active_token:
                self.replace_if_needed(effective)
            self.publish()
            return self.status()

    def replace_if_needed(self, effective):
        if not self.active_token or self.active_mode == effective:
            return self.status()
        old_token = self.active_token
        response = self.overlay({
            "schema_version": 1, "command": "request",
            "owner_service": "tvbox-screensaver-policy",
            "owner_instance_id": self.instance_id,
            "owner_pid": os.getpid(), "overlay_type": "screensaver",
            "renderer": effective,
            "arguments": self.renderer_arguments(effective),
            "priority": 20, "lease_seconds": self.lease_seconds,
            "preemption_policy": "cancel", "replace_token": old_token,
        })
        if not response.get("ok"):
            raise RuntimeError(response.get("error", "replacement failed"))
        # Manager retains old until the new first frame is promoted. Keep the
        # old token locally until status proves promotion.
        new_token = response["request_id"]
        deadline = self.monotonic() + 10.0
        while self.monotonic() < deadline:
            overlay_status = self.overlay({"command": "status"})
            active = overlay_status.get("status", {}).get("active_request")
            if active and active.get("request_id") == new_token:
                self.active_token = new_token
                self.active_generation = response["generation"]
                self.active_mode = effective
                self.last_error = None
                self.last_renewal = self.monotonic()
                self.publish()
                return self.status()
            requests = overlay_status.get("status", {}).get("requests", [])
            candidate = next((x for x in requests if x.get("request_id") == new_token), None)
            if candidate and candidate.get("state") == "failed":
                raise RuntimeError(candidate.get("failure_reason", "replacement failed"))
            time.sleep(0.05)
        raise RuntimeError("replacement readiness timeout")

    def reload(self):
        with self.lock:
            self.config = load_config(self.config_path)
            effective = self.schedule_facts()[2]
            if self.active_token:
                self.replace_if_needed(effective)
            self.publish()
            return self.status()

    def tick(self):
        with self.lock:
            effective = self.schedule_facts()[2]
            try:
                manager_status = self.overlay({"command": "status"})
                manager_active = manager_status.get("status", {}).get("active_request")
                manager_requests = manager_status.get("status", {}).get("requests", [])
            except (OSError, ValueError):
                manager_active = None
                manager_requests = []
            candidate = next((
                item for item in manager_requests
                if item.get("request_id") == self.active_token
            ), None)
            token_is_live = bool(
                candidate and candidate.get("state") in {"starting", "active"})
            if self.active_token and not token_is_live and (
                    not manager_active
                    or manager_active.get("request_id") != self.active_token):
                print(
                    "tvbox-screensaverd: manager lost token "
                    f"{self.active_token}; active="
                    f"{(manager_active or {}).get('request_id')} "
                    f"candidate_state={(candidate or {}).get('state')}",
                    file=sys.stderr, flush=True,
                )
                self.active_token = None
                self.active_generation = None
                self.active_mode = None
            if self.active_requested and not self.active_token:
                print("tvbox-screensaverd: reissuing requested overlay",
                      file=sys.stderr, flush=True)
                try:
                    self.start()
                except (OSError, RuntimeError, ValueError) as exc:
                    self.last_error = str(exc)
                    self.publish()
                return
            if self.active_token:
                try:
                    self.replace_if_needed(effective)
                except (OSError, RuntimeError, ValueError) as exc:
                    # The manager retains the old opaque renderer on failed
                    # replacement. Keep the exact old token and retry later.
                    self.last_error = str(exc)
                if self.monotonic() - self.last_renewal >= 30.0:
                    response = self.overlay({
                        "command": "renew", "request_id": self.active_token,
                        "lease_seconds": self.lease_seconds,
                    })
                    if response.get("ok"):
                        self.last_renewal = self.monotonic()
                    else:
                        self.active_token = None
                        self.active_generation = None
                        self.active_mode = None
            self.publish()

    def status(self):
        moment, scheduled, effective, boundary = self.schedule_facts()
        try:
            overlay = self.overlay({"command": "status"}).get("status")
        except (OSError, ValueError):
            overlay = None
        active = (overlay or {}).get("active_request")
        return {
            "manual_override": self.manual_override,
            "active_requested": self.active_requested,
            "scheduled_mode": scheduled,
            "effective_mode": effective,
            "next_boundary": boundary.isoformat() if boundary else None,
            "configuration": str(self.config_path),
            "policy_instance_id": self.instance_id,
            "active_request_id": self.active_token,
            "active_generation": self.active_generation,
            "active_mode": self.active_mode,
            "last_error": self.last_error,
            "overlay_active": active,
            "evaluated_at": moment.isoformat(),
        }

    def publish(self):
        write_json(self.state_path, self.status(), self.instance_id)
