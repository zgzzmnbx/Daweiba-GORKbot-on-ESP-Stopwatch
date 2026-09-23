"""Foreground service owned by a parent pipe; EOF requests graceful shutdown.

Run with this project's Python. No browser, detached child or global state file.
The owner must keep stdin open and close it when quitting (including a crash).
"""
import os
from pathlib import Path
import sys
import threading
import argparse
import time
from dataclasses import replace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "03-Src"))


def main():
    import uvicorn
    from voice_service.config import load_settings
    from voice_service.app import create_app
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int)
    args = parser.parse_args()
    config = load_settings()
    if args.port is not None:
        if not 1024 <= args.port <= 65535:
            parser.error('port must be 1024..65535')
        config = replace(config, port=args.port)
    # Read only this service's dedicated key, never enumerate user secrets.
    if os.name == "nt" and not os.environ.get(config.cloud_key_env):
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
                value, _ = winreg.QueryValueEx(key, config.cloud_key_env)
            if isinstance(value, str):
                os.environ[config.cloud_key_env] = value
        except FileNotFoundError:
            pass
    server = uvicorn.Server(uvicorn.Config(create_app(config), host=config.host,
                                          port=config.port, access_log=False))
    if os.name == 'nt':
        import ctypes
        from ctypes import wintypes
        import msvcrt
        handle = msvcrt.get_osfhandle(sys.stdin.fileno())
        peek = ctypes.WinDLL('kernel32', use_last_error=True).PeekNamedPipe
        peek.argtypes = [wintypes.HANDLE, wintypes.LPVOID, wintypes.DWORD,
                         wintypes.LPVOID, wintypes.LPVOID, wintypes.LPVOID]
        peek.restype = wintypes.BOOL
    def watch_owner():
        if os.name == 'nt':
            # A blocking CRT stdin read can lock the handle while Windows
            # multiprocessing tries to inherit it. Poll the pipe without reading.
            while not server.should_exit:
                if not peek(handle, None, 0, None, None, None):
                    server.should_exit = True
                    return
                time.sleep(.2)
        else:
            while os.read(sys.stdin.fileno(), 1):
                pass
            server.should_exit = True
    threading.Thread(target=watch_owner, daemon=True).start()
    server.run()


if __name__ == "__main__":
    main()
