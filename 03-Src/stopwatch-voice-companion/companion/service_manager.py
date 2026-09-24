"""Own-or-reuse lifecycle for the project-local loopback voice service."""
import os
from pathlib import Path
import subprocess
import time
import threading

import httpx


class VoiceServiceManager:
    def __init__(self, config, client=None, popen=None, sleeper=None):
        self.url = config.get("voice_url", "http://127.0.0.1:8765").rstrip("/")
        project = Path(__file__).resolve().parents[3]
        module = project / "03-Src" / "voice-service"
        python = project / "Codex-Temp" / "voice-runtime" / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        self.bundled_config = module / "03-Src" / "config" / "voice.example.toml" if "voice_service_command" not in config else None
        self.command = config.get("voice_service_command", [str(python), str(module / "tools" / "serve_managed.py")])
        self.cwd = config.get("voice_service_cwd", "" if "voice_service_command" in config else str(module))
        self.client = client or httpx.Client(timeout=2, trust_env=False)
        self.popen = popen or subprocess.Popen
        self.sleeper = sleeper or time.sleep
        self.process = None
        self.lock = threading.Lock()
        self.stopping = threading.Event()
        self.mode, self.error = "offline", ""

    def healthy(self):
        try:
            health = self.client.get(self.url + "/v1/health")
            caps = self.client.get(self.url + "/v1/capabilities")
            return (health.status_code == 200 and health.json().get("service") == "zhisuan-voice-service"
                    and caps.status_code == 200 and caps.json().get("protocol_version") == 1)
        except (httpx.HTTPError, ValueError, AttributeError):
            return False

    def ensure(self):
        with self.lock:
            if self.stopping.is_set():
                return self.snapshot()
            try:
                return self._ensure()
            except (ValueError, OSError):
                self.mode, self.error = "offline", "语音服务启动失败，请检查本机启动入口和工作目录"
                self._stop_process()
                return self.snapshot()

    def _ensure(self):
        if self.healthy():
            self.mode, self.error = "owned" if self.process and self.process.poll() is None else "external", ""
            return self.snapshot()
        self._stop_process()
        self.mode, self.error = "offline", ""
        if not self.command:
            self.error = "语音服务离线，且未配置启动入口"
            return self.snapshot()
        if not isinstance(self.command, list) or not self.command or not all(isinstance(x, str) and x for x in self.command):
            raise ValueError("voice_service_command 必须是非空 TOML 字符串数组")
        executable = Path(self.command[0])
        cwd = Path(self.cwd) if self.cwd else executable.parent
        if not executable.is_absolute() or not executable.is_file() or not cwd.is_absolute() or not cwd.is_dir():
            raise ValueError("语音服务入口和工作目录必须是已存在的绝对路径")
        flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        self.mode = "starting"
        environment = os.environ.copy()
        if self.bundled_config is not None:
            environment["VOICE_CONFIG"] = str(self.bundled_config)
        self.process = self.popen(self.command, cwd=str(cwd), stdin=subprocess.PIPE, env=environment,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=flags)
        for _ in range(75):
            if self.stopping.is_set():
                break
            if self.process.poll() is not None:
                self.error = "自有语音服务提前退出"
                break
            if self.healthy():
                self.mode, self.error = "owned", ""
                return self.snapshot()
            self.sleeper(.2)
        if not self.error:
            self.error = "自有语音服务启动超时"
        self._stop_process()
        self.mode = "offline"
        return self.snapshot()

    def snapshot(self):
        mode = self.mode
        if mode == "owned" and self.process and self.process.poll() is not None:
            mode = "offline"
        return {"mode": mode, "configured": bool(self.command), "owned": mode == "owned", "pid": self.process.pid if self.process else None, "error": self.error}

    def _stop_process(self):
        process, self.process = self.process, None
        if process is not None and process.poll() is None:
            # Managed entry gracefully closes its inference worker on pipe EOF.
            if getattr(process, "stdin", None):
                process.stdin.close()
            else:
                process.terminate()
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        if self.mode == "owned":
            self.mode = "offline"

    def close(self):
        self.stopping.set()
        with self.lock:
            self._stop_process()
        self.client.close()
