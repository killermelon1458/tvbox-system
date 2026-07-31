"""Token-safe overlay renderer manager."""

from dataclasses import dataclass, field
import json
import os
from pathlib import Path
import selectors
import signal
import socket
import subprocess
import threading
import time
import uuid

from tvbox.runtime import atomic_json, boot_id, instance_id, metadata, runtime_root
from tvbox.overlay.protocol import ProtocolError, validate_request


@dataclass
class ManagedRequest:
    request_id: str
    generation: int
    spec: object
    state: str = "starting"
    created_monotonic: float = field(default_factory=time.monotonic)
    lease_expires_monotonic: float = 0.0
    process: object = None
    process_group: int | None = None
    ready: bool = False
    degradation: str | None = None
    failure_reason: str | None = None
    exit_status: int | None = None


class OverlayManager:
    def __init__(self, root=None, renderer_commands=None, startup_timeout=8.0,
                 stop_timeout=2.0, clock=time.monotonic):
        self.root = Path(root) if root else runtime_root()
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(self.root, 0o700)
        self.manager_instance_id = instance_id()
        self.generation = 0
        self.requests = {}
        self.active_token = None
        self.lock = threading.RLock()
        self.clock = clock
        self.startup_timeout = startup_timeout
        self.stop_timeout = stop_timeout
        self.cache_path = self.root / "overlay-state.json"
        self.renderer_commands = renderer_commands or {
            "black": ["/usr/local/bin/tvbox-render-black"],
            "slideshow": ["/usr/local/bin/tvbox-render-slideshow"],
        }
        self._stopping = threading.Event()
        # Cached PIDs are never adopted or signalled.
        self.publish()

    def snapshot(self):
        with self.lock:
            active = self.requests.get(self.active_token)
            return {
                **metadata(self.manager_instance_id),
                "manager_instance_id": self.manager_instance_id,
                "active_request": self.describe(active) if active else None,
                "requests": [self.describe(item) for item in self.requests.values()],
            }

    @staticmethod
    def describe(item):
        if not item:
            return None
        return {
            "request_id": item.request_id,
            "generation": item.generation,
            "owner_service": item.spec.owner_service,
            "owner_instance_id": item.spec.owner_instance_id,
            "owner_pid": item.spec.owner_pid,
            "overlay_type": item.spec.overlay_type,
            "renderer": item.spec.renderer,
            "arguments": item.spec.arguments,
            "priority": item.spec.priority,
            "lease_seconds": item.spec.lease_seconds,
            "lease_expires_monotonic": item.lease_expires_monotonic,
            "state": item.state,
            "ready": item.ready,
            "degradation": item.degradation,
            "failure_reason": item.failure_reason,
            "exit_status": item.exit_status,
            "process_pid": item.process.pid if item.process and item.process.poll() is None else None,
            "process_group": item.process_group,
        }

    def publish(self):
        atomic_json(self.cache_path, self.snapshot())

    def accept(self, message):
        spec = validate_request(message)
        with self.lock:
            current = self.requests.get(self.active_token)
            if current and spec.replace_token != current.request_id:
                if spec.priority < current.spec.priority:
                    raise ProtocolError("request blocked by higher priority overlay")
                if spec.priority == current.spec.priority and spec.preemption_policy == "retain":
                    raise ProtocolError("equal-priority overlay retained")
            if spec.replace_token and (
                    not current or current.request_id != spec.replace_token):
                raise ProtocolError("replace token is not active")
            self.generation += 1
            item = ManagedRequest(
                uuid.uuid4().hex, self.generation, spec,
                lease_expires_monotonic=self.clock() + spec.lease_seconds,
            )
            self.requests[item.request_id] = item
            self.publish()
        threading.Thread(target=self._start, args=(item,), daemon=True).start()
        return {
            "ok": True, "request_id": item.request_id,
            "generation": item.generation,
            "manager_instance_id": self.manager_instance_id,
            "state": "starting",
        }

    def renderer_command(self, item):
        command = list(self.renderer_commands[item.spec.renderer])
        for key, value in sorted(item.spec.arguments.items()):
            flag = "--" + key.replace("_", "-")
            if isinstance(value, bool):
                command.extend([flag, "true" if value else "false"])
            elif isinstance(value, list):
                command.extend([flag, ",".join(str(part) for part in value)])
            else:
                command.extend([flag, str(value)])
        return command

    def _start(self, item):
        read_fd, write_fd = os.pipe()
        os.set_inheritable(write_fd, True)
        env = os.environ.copy()
        env.update({
            "TVBOX_OVERLAY_READY_FD": str(write_fd),
            "TVBOX_OVERLAY_REQUEST_ID": item.request_id,
            "TVBOX_OVERLAY_GENERATION": str(item.generation),
        })
        try:
            process = subprocess.Popen(
                self.renderer_command(item), env=env, pass_fds=(write_fd,),
                start_new_session=True, close_fds=True,
            )
            os.close(write_fd)
            with self.lock:
                if item.request_id not in self.requests:
                    self._terminate_process(process, process.pid)
                    return
                item.process = process
                item.process_group = process.pid
                self.publish()
            ready = self._await_ready(read_fd, item, process)
            if ready is None:
                self._fail_start(item, "renderer-readiness-timeout")
                return
            with self.lock:
                current = self.requests.get(item.request_id)
                if current is not item or item.generation != ready.get("generation"):
                    self._terminate(item)
                    return
                old = self.requests.get(self.active_token)
                if item.spec.replace_token and (
                        not old or old.request_id != item.spec.replace_token):
                    self._fail_start(item, "replacement-token-became-stale")
                    return
                item.ready = True
                item.state = "active"
                item.degradation = ready.get("degradation")
                self.active_token = item.request_id
                self.publish()
            if old and old is not item:
                self._remove(old, "replaced")
            threading.Thread(target=self._watch_exit, args=(item,), daemon=True).start()
        except (OSError, ValueError) as exc:
            try:
                os.close(write_fd)
            except OSError:
                pass
            self._fail_start(item, f"renderer-start-error:{exc.__class__.__name__}")
        finally:
            try:
                os.close(read_fd)
            except OSError:
                pass

    def _await_ready(self, fd, item, process):
        selector = selectors.DefaultSelector()
        selector.register(fd, selectors.EVENT_READ)
        deadline = self.clock() + self.startup_timeout
        data = b""
        while self.clock() < deadline and process.poll() is None:
            events = selector.select(max(0.0, min(0.1, deadline - self.clock())))
            if not events:
                continue
            chunk = os.read(fd, 65536)
            if not chunk:
                break
            data += chunk
            if b"\n" in data:
                try:
                    value = json.loads(data.split(b"\n", 1)[0])
                except (ValueError, UnicodeDecodeError):
                    return None
                if (value.get("request_id") == item.request_id
                        and value.get("generation") == item.generation
                        and value.get("event") == "first-frame-ready"):
                    return value
                return None
        return None

    def _fail_start(self, item, reason):
        self._terminate(item)
        with self.lock:
            if self.requests.get(item.request_id) is not item:
                return
            item.state = "failed"
            item.failure_reason = reason
            item.exit_status = item.process.poll() if item.process else None
            self.publish()

    def _watch_exit(self, item):
        status = item.process.wait()
        with self.lock:
            if self.requests.get(item.request_id) is not item:
                return
            item.exit_status = status
            if self.active_token == item.request_id:
                self.active_token = None
                item.state = "failed"
                item.failure_reason = f"renderer-exit:{status}"
            self.publish()

    def _terminate_process(self, process, group):
        if process.poll() is not None:
            return
        try:
            os.killpg(group, signal.SIGTERM)
        except ProcessLookupError:
            return
        try:
            process.wait(timeout=self.stop_timeout)
            return
        except subprocess.TimeoutExpired:
            pass
        try:
            os.killpg(group, signal.SIGKILL)
        except ProcessLookupError:
            pass
        try:
            process.wait(timeout=self.stop_timeout)
        except subprocess.TimeoutExpired:
            pass

    def _terminate(self, item):
        if item.process and item.process_group:
            self._terminate_process(item.process, item.process_group)

    def _remove(self, item, reason):
        self._terminate(item)
        with self.lock:
            if self.requests.get(item.request_id) is not item:
                return
            item.state = reason
            if self.active_token == item.request_id:
                self.active_token = None
            del self.requests[item.request_id]
            self.publish()

    def release(self, token):
        with self.lock:
            item = self.requests.get(token)
        if not item:
            raise ProtocolError("unknown or stale request token")
        self._remove(item, "released")
        return {"ok": True, "released": token}

    def renew(self, token, seconds=None):
        with self.lock:
            item = self.requests.get(token)
            if not item:
                raise ProtocolError("unknown or stale request token")
            lease = item.spec.lease_seconds if seconds is None else float(seconds)
            if lease < 2.0 or lease > 86400.0:
                raise ProtocolError("invalid renewal lease")
            item.lease_expires_monotonic = self.clock() + lease
            self.publish()
            return {"ok": True, "request_id": token,
                    "lease_expires_monotonic": item.lease_expires_monotonic}

    def expire(self):
        with self.lock:
            expired = [
                item for item in self.requests.values()
                if item.lease_expires_monotonic <= self.clock()
            ]
        for item in expired:
            self._remove(item, "expired")
        return len(expired)

    def shutdown(self):
        self._stopping.set()
        with self.lock:
            items = list(self.requests.values())
        for item in items:
            self._remove(item, "manager-shutdown")
        self.publish()


class OverlayServer:
    def __init__(self, manager, socket_path=None):
        self.manager = manager
        self.socket_path = Path(socket_path or manager.root / "overlay.sock")
        self.socket = None
        self.stop_event = threading.Event()

    def dispatch(self, message):
        command = message.get("command")
        if command == "request":
            return self.manager.accept(message)
        if command == "release":
            return self.manager.release(message.get("request_id", ""))
        if command == "renew":
            return self.manager.renew(message.get("request_id", ""),
                                      message.get("lease_seconds"))
        if command == "status":
            return {"ok": True, "status": self.manager.snapshot()}
        raise ProtocolError("unsupported command")

    def serve(self):
        try:
            self.socket_path.unlink()
        except FileNotFoundError:
            pass
        server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server.bind(str(self.socket_path))
        os.chmod(self.socket_path, 0o600)
        server.listen(16)
        server.settimeout(0.25)
        self.socket = server
        try:
            while not self.stop_event.is_set():
                self.manager.expire()
                try:
                    connection, _ = server.accept()
                except socket.timeout:
                    continue
                with connection:
                    try:
                        data = b""
                        while b"\n" not in data and len(data) <= 1024 * 1024:
                            chunk = connection.recv(65536)
                            if not chunk:
                                break
                            data += chunk
                        message = json.loads(data.split(b"\n", 1)[0])
                        response = self.dispatch(message)
                    except (ValueError, TypeError, ProtocolError) as exc:
                        response = {"ok": False, "error": str(exc)}
                    connection.sendall(json.dumps(response).encode() + b"\n")
        finally:
            server.close()
            try:
                self.socket_path.unlink()
            except FileNotFoundError:
                pass
            self.manager.shutdown()

    def stop(self):
        self.stop_event.set()
