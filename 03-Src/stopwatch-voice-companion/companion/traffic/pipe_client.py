"""Read-only Mihomo HTTP client over a Windows named pipe (Python stdlib only)."""
import ctypes
from ctypes import wintypes
import http.client
import io
import json
import os
from pathlib import Path
import re
import time


class PipeStream(io.RawIOBase):
    def __init__(self, path, timeout=3.0):
        super().__init__()
        self.readers = 0
        self.close_requested = False
        if os.name != "nt":
            raise OSError("This connector requires Windows.")
        self.deadline = time.monotonic() + timeout
        self.k = ctypes.WinDLL("kernel32", use_last_error=True)
        class Overlapped(ctypes.Structure):
            _fields_ = [("Internal", ctypes.c_size_t), ("InternalHigh", ctypes.c_size_t),
                        ("Offset", wintypes.DWORD), ("OffsetHigh", wintypes.DWORD),
                        ("hEvent", wintypes.HANDLE)]
        self.Overlapped = Overlapped
        signatures = {
            "CreateFileW": ([wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                              ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD,
                              wintypes.HANDLE], wintypes.HANDLE),
            "CreateEventW": ([ctypes.c_void_p, wintypes.BOOL, wintypes.BOOL,
                               wintypes.LPCWSTR], wintypes.HANDLE),
            "ReadFile": ([wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD,
                           ctypes.POINTER(wintypes.DWORD), ctypes.POINTER(Overlapped)], wintypes.BOOL),
            "WriteFile": ([wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD,
                            ctypes.POINTER(wintypes.DWORD), ctypes.POINTER(Overlapped)], wintypes.BOOL),
            "GetOverlappedResult": ([wintypes.HANDLE, ctypes.POINTER(Overlapped),
                                      ctypes.POINTER(wintypes.DWORD), wintypes.BOOL], wintypes.BOOL),
            "WaitForSingleObject": ([wintypes.HANDLE, wintypes.DWORD], wintypes.DWORD),
            "CancelIoEx": ([wintypes.HANDLE, ctypes.POINTER(Overlapped)], wintypes.BOOL),
            "CloseHandle": ([wintypes.HANDLE], wintypes.BOOL),
        }
        for name, (args, result) in signatures.items():
            f = getattr(self.k, name)
            f.argtypes, f.restype = args, result
        self.handle = self.k.CreateFileW(path, 0xC0000000, 0, None, 3, 0x40000000, None)
        if self.handle == ctypes.c_void_p(-1).value:
            self.handle = None
            raise ctypes.WinError(ctypes.get_last_error())

    def readable(self):
        return True

    def _io(self, buffer, size, write=False):
        remaining = int((self.deadline - time.monotonic()) * 1000)
        if remaining <= 0:
            raise TimeoutError("Mihomo local pipe timed out.")
        event = self.k.CreateEventW(None, True, False, None)
        if not event:
            raise ctypes.WinError(ctypes.get_last_error())
        ov = self.Overlapped()
        ov.hEvent = event
        count = wintypes.DWORD()
        try:
            ok = (self.k.WriteFile if write else self.k.ReadFile)(
                self.handle, buffer, size, ctypes.byref(count), ctypes.byref(ov))
            if not ok:
                error = ctypes.get_last_error()
                if error in (109, 232) and not write:
                    return 0
                if error != 997:
                    raise ctypes.WinError(error)
                if self.k.WaitForSingleObject(event, remaining) != 0:
                    self.k.CancelIoEx(self.handle, ctypes.byref(ov))
                    self.k.GetOverlappedResult(self.handle, ctypes.byref(ov), ctypes.byref(count), True)
                    raise TimeoutError("Mihomo local pipe timed out.")
                if not self.k.GetOverlappedResult(self.handle, ctypes.byref(ov), ctypes.byref(count), False):
                    error = ctypes.get_last_error()
                    if error in (109, 232) and not write:
                        return 0
                    raise ctypes.WinError(error)
            return count.value
        finally:
            self.k.CloseHandle(event)

    def readinto(self, target):
        buffer = (ctypes.c_char * len(target)).from_buffer(target)
        return self._io(buffer, len(target))

    def sendall(self, data):
        offset = 0
        while offset < len(data):
            buffer = ctypes.create_string_buffer(data[offset:])
            count = self._io(buffer, len(data) - offset, write=True)
            if not count:
                raise OSError("Mihomo pipe closed while writing.")
            offset += count

    def makefile(self, mode, *args, **kwargs):
        self.readers += 1
        owner = self
        class Reader(io.RawIOBase):
            def readable(self):
                return True
            def readinto(self, target):
                return owner.readinto(target)
            def close(self):
                if not self.closed:
                    owner.readers -= 1
                    if owner.close_requested:
                        owner.close()
                super().close()
        return io.BufferedReader(Reader())

    def close(self):
        # Like socket.makefile(), the response reader owns a reference even when
        # HTTPConnection releases its socket on a Connection: close response.
        self.close_requested = True
        if self.readers:
            return
        if getattr(self, "handle", None):
            self.k.CloseHandle(self.handle)
            self.handle = None
        super().close()


def decode_scalar(value):
    value = value.strip()
    if value.startswith('"'):
        return json.loads(value)
    if value.startswith("'") and value.endswith("'"):
        return value[1:-1].replace("''", "'")
    return value.split(" #", 1)[0].strip()


class MihomoClient:
    def __init__(self, config_path=None, pipe=None):
        self.config_path = Path(config_path) if config_path else (
            Path(os.environ.get("APPDATA", "")) /
            "io.github.clash-verge-rev.clash-verge-rev" / "clash-verge.yaml")
        self.pipe_override = pipe

    def get(self, endpoint="/connections"):
        if endpoint not in ("/connections", "/version", "/rules"):
            raise ValueError("Only read-only monitoring endpoints are supported.")
        fields = {}
        if self.config_path.is_file():
            for line in self.config_path.read_text(encoding="utf-8-sig").splitlines():
                m = re.match(r"^(external-controller-pipe|secret):\s*(.*)$", line)
                if m:
                    fields[m[1]] = decode_scalar(m[2])
        pipe = self.pipe_override or fields.get("external-controller-pipe") or r"\\.\pipe\verge-mihomo"
        stream = PipeStream(pipe)
        connection = http.client.HTTPConnection("localhost", timeout=3)
        connection.sock = stream
        try:
            headers = {"Connection": "close", "Accept": "application/json"}
            if fields.get("secret"):
                headers["Authorization"] = "Bearer " + fields["secret"]
            connection.request("GET", endpoint, headers=headers)
            response = connection.getresponse()
            if response.status != 200:
                raise OSError(f"Mihomo API returned HTTP {response.status}.")
            # HTTPResponse handles both Content-Length and chunked responses.
            try:
                payload = response.read(16 * 1024 * 1024 + 1)
                if len(payload) > 16 * 1024 * 1024:
                    raise OSError("Mihomo snapshot too large")
                return json.loads(payload)
            finally:
                response.close()
        finally:
            connection.close()
