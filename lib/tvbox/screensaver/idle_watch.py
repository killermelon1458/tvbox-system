"""Linux directory watch for atomically replaced canonical idle state."""

import ctypes
import os
from pathlib import Path
import struct


IN_CLOSE_WRITE = 0x00000008
IN_MOVED_TO = 0x00000080
IN_CREATE = 0x00000100
IN_DELETE = 0x00000200
WATCH_MASK = IN_CLOSE_WRITE | IN_MOVED_TO | IN_CREATE | IN_DELETE
EVENT = struct.Struct("iIII")


class IdleStateWatcher:
    def __init__(self, directory, filename="idle-state.json"):
        self.directory = Path(directory)
        self.filename = filename
        libc = ctypes.CDLL(None, use_errno=True)
        fd = libc.inotify_init1(os.O_NONBLOCK | os.O_CLOEXEC)
        if fd < 0:
            error = ctypes.get_errno()
            raise OSError(error, os.strerror(error))
        self.fd = fd
        watch = libc.inotify_add_watch(
            fd, os.fsencode(self.directory), WATCH_MASK)
        if watch < 0:
            error = ctypes.get_errno()
            os.close(fd)
            raise OSError(error, os.strerror(error), str(self.directory))

    def fileno(self):
        return self.fd

    def changed(self):
        matched = False
        while True:
            try:
                data = os.read(self.fd, 65536)
            except BlockingIOError:
                break
            if not data:
                break
            offset = 0
            while offset + EVENT.size <= len(data):
                _watch, _mask, _cookie, length = EVENT.unpack_from(data, offset)
                offset += EVENT.size
                raw_name = data[offset:offset + length]
                offset += length
                name = raw_name.split(b"\0", 1)[0].decode(errors="replace")
                if name == self.filename:
                    matched = True
        return matched

    def close(self):
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None
