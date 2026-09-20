"""Own-process launcher. No process killing, credentials or voice-engine imports."""
import argparse
import os
from pathlib import Path
import socket
import threading
import time
import tomllib
import webbrowser

import httpx
import uvicorn

from companion.app import create_app, INSTANCE

ROOT = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=ROOT / "config.local.toml")
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    config = tomllib.loads(args.config.read_text(encoding="utf-8-sig")) if args.config.exists() else {}
    port = config.get("port", 8766)
    if not isinstance(port, int) or not 1024 <= port <= 65535:
        raise SystemExit("port must be 1024..65535")
    app = create_app(config)
    url = f"http://127.0.0.1:{port}"
    # Own the listening socket before launch. Never stop an unknown listener.
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    if os.name == "nt":
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
    try:
        listener.bind(("127.0.0.1", port))
    except OSError:
        listener.close()
        try:
            health = httpx.get(url + "/api/health", timeout=5, trust_env=False).json()
        except (httpx.HTTPError, ValueError):
            health = {}
        if (health.get("app") == "stopwatch-voice-companion" and health.get("instance") == INSTANCE
                and isinstance(health.get("pid"), int) and health["pid"] > 0):
            print(f"Existing companion PID {health['pid']}: {url}")
            if not args.no_browser:
                webbrowser.open(url)
            return
        raise SystemExit(f"Port {port} belongs to another service. Nothing was stopped. Change config.local.toml.")
    listener.listen(128)

    def open_own_page():
        for _ in range(30):
            try:
                result = httpx.get(url + "/api/health", timeout=2, trust_env=False).json()
                if result.get("pid") == os.getpid() and result.get("instance") == INSTANCE:
                    webbrowser.open(url)
                    return
            except (httpx.HTTPError, ValueError):
                pass
            time.sleep(.3)

    print(f"StopWatch companion v0.6.0 | PID {os.getpid()} | {url}", flush=True)
    print("Ctrl+C closes this companion only. Start the independent voice service separately.", flush=True)
    if not args.no_browser:
        threading.Thread(target=open_own_page, daemon=True).start()
    try:
        uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, access_log=False)).run(sockets=[listener])
    finally:
        listener.close()


if __name__ == "__main__":
    main()
