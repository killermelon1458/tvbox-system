"""Persistent manual/schedule screensaver policy service."""

from datetime import datetime
import json
import os
from pathlib import Path
import socket
import threading
import time
import sys

from tvbox.runtime import boot_id, instance_id, read_json, runtime_root, write_json
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
        saved_source = previous.get("activation_source")
        if saved_source not in {"manual", "automatic"}:
            saved_source = "manual" if self.active_requested else "inactive"
        self.activation_source = saved_source
        previous_automatic = previous.get("automatic") or {}
        self.automatic_idle_epoch = previous_automatic.get("idle_epoch")
        self.suppressed_idle_epoch = previous_automatic.get(
            "suppressed_idle_epoch")
        self.idle_input = {}
        self.last_error = previous.get("last_error")
        self.lease_seconds = 120.0
        self.last_renewal = 0.0
        self.retry_not_before = 0.0
        self.overlay_socket = self.root / "overlay.sock"
        self.state_path = self.root / "screensaver-policy.json"
        self.lock = threading.RLock()
        self.reconcile_idle()
        self.publish()

    @staticmethod
    def _epoch(record):
        required = ("boot_id", "writer_instance_id", "provider",
                    "epoch_started_monotonic")
        if not all(record.get(key) is not None for key in required):
            return None
        return {key: record[key] for key in required}

    def read_idle_input(self):
        path = self.root / "idle-state.json"
        result = {
            "path": str(path), "health": "missing", "eligible": False,
            "state": "missing", "idle": False, "provider": None,
            "confidence": None, "epoch": None, "age_seconds": None,
        }
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return result
        except (OSError, ValueError, TypeError):
            result.update(health="malformed", state="unknown")
            return result
        if not isinstance(record, dict):
            result.update(health="malformed", state="unknown")
            return result
        result.update(
            state=record.get("state", "unknown"),
            idle=record.get("idle") is True,
            provider=record.get("provider"),
            confidence=record.get("confidence"),
            epoch=self._epoch(record),
        )
        if record.get("schema_version") != 1:
            result["health"] = "unsupported-schema"
            return result
        if record.get("boot_id") != boot_id():
            result["health"] = "wrong-boot"
            return result
        updated = record.get("updated_monotonic")
        if not isinstance(updated, (int, float)):
            result["health"] = "malformed"
            return result
        age = max(0.0, self.monotonic() - updated)
        result["age_seconds"] = age
        if age > self.config.idle_state_stale_seconds:
            result["health"] = "stale"
            return result
        source_health = record.get("source_health") or {}
        acceptable_health = (
            source_health.get("activity") == "healthy"
            and source_health.get("application_state") == "healthy"
            and source_health.get("provider") == "healthy"
        )
        if record.get("state") != "idle" or record.get("idle") is not True:
            result["health"] = "non-idle"
            return result
        if not acceptable_health:
            result["health"] = "unacceptable-source-health"
            return result
        if result["epoch"] is None:
            result["health"] = "malformed"
            return result
        result["health"] = "healthy"
        result["eligible"] = bool(self.config.automatic_enabled)
        if not self.config.automatic_enabled:
            result["health"] = "automatic-disabled"
        return result

    def reconcile_idle(self):
        """Consume canonical idle only; never derive idle independently."""
        idle_input = self.read_idle_input()
        self.idle_input = idle_input
        epoch = idle_input.get("epoch")
        if epoch and self.suppressed_idle_epoch and (
                epoch != self.suppressed_idle_epoch):
            self.suppressed_idle_epoch = None
        if idle_input.get("health") == "non-idle":
            self.suppressed_idle_epoch = None

        if not idle_input.get("eligible"):
            if self.activation_source == "automatic":
                self._stop(suppress=False)
            return
        if self.suppressed_idle_epoch == epoch:
            return
        if self.activation_source == "manual" and self.active_requested:
            return
        if self.activation_source == "automatic" and self.active_requested:
            self.automatic_idle_epoch = epoch
            return
        try:
            self._start("automatic", epoch)
        except (OSError, RuntimeError, ValueError) as exc:
            self.last_error = str(exc)
            self.retry_not_before = self.monotonic() + 5.0

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

    def _start(self, source, idle_epoch=None):
        with self.lock:
            self.active_requested = True
            self.activation_source = source
            self.automatic_idle_epoch = idle_epoch if source == "automatic" else None
            if source == "manual":
                self.suppressed_idle_epoch = None
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
            self.retry_not_before = 0.0
            self.publish()
            return self.status()

    def start(self):
        return self._start("manual")

    def _stop(self, suppress):
        with self.lock:
            if (suppress and self.activation_source == "automatic"
                    and self.automatic_idle_epoch):
                self.suppressed_idle_epoch = self.automatic_idle_epoch
            self.active_requested = False
            self.activation_source = "inactive"
            self.automatic_idle_epoch = None
            if not self.active_token:
                self.publish()
                return self.status()
            token = self.active_token
            try:
                response = self.overlay(
                    {"command": "release", "request_id": token})
                self.last_error = (
                    None if response.get("ok") else response.get("error"))
            except (OSError, RuntimeError, ValueError) as exc:
                # Relinquish local ownership; the finite exact-token lease is
                # the fail-safe if the manager is temporarily unavailable.
                self.last_error = str(exc)
            self.active_token = None
            self.active_generation = None
            self.active_mode = None
            self.publish()
            return self.status()

    def stop(self):
        return self._stop(suppress=True)

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
            self.reconcile_idle()
            effective = self.schedule_facts()[2]
            if self.active_token:
                self.replace_if_needed(effective)
            self.publish()
            return self.status()

    def tick(self):
        with self.lock:
            self.reconcile_idle()
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
                if candidate and candidate.get("state") == "failed":
                    self.last_error = candidate.get(
                        "failure_reason", "overlay request failed")
                    self.retry_not_before = self.monotonic() + 5.0
            if (self.active_requested and not self.active_token
                    and self.monotonic() >= self.retry_not_before):
                print("tvbox-screensaverd: reissuing requested overlay",
                      file=sys.stderr, flush=True)
                try:
                    self._start(self.activation_source,
                                self.automatic_idle_epoch)
                except (OSError, RuntimeError, ValueError) as exc:
                    self.last_error = str(exc)
                    self.retry_not_before = self.monotonic() + 5.0
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
            "activation_source": self.activation_source,
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
            "automatic": {
                "enabled": self.config.automatic_enabled,
                "eligible": bool(self.idle_input.get("eligible")),
                "idle_epoch": self.automatic_idle_epoch,
                "suppressed_idle_epoch": self.suppressed_idle_epoch,
                "reconcile_interval_seconds":
                    self.config.reconcile_interval_seconds,
            },
            "idle_input": self.idle_input,
            "overlay_active": active,
            "evaluated_at": moment.isoformat(),
        }

    def publish(self):
        write_json(self.state_path, self.status(), self.instance_id)
