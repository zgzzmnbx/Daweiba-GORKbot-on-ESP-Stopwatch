"""Low-frequency Windows history snapshots, separate from Clash accounting."""
import json
import os
from pathlib import Path
import subprocess


def read_system_usage():
    if os.name != "nt":
        return {"available": False, "error": "WindowsOnly", "rows": []}
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-File", str(Path(__file__).with_name("windows_usage.ps1"))],
        capture_output=True, timeout=30, creationflags=subprocess.CREATE_NO_WINDOW)
    if result.returncode:
        return {"available": False, "error": "WindowsQueryFailed", "rows": []}
    return json.loads(result.stdout.decode("utf-8-sig"))
