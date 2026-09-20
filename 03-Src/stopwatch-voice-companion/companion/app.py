"""Loopback-only browser facade. The voice session token never leaves Python."""
from contextlib import asynccontextmanager
import os
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit
import uuid

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from . import __version__
from .control import Controller
from .robot import Robot, BleConsoleError
from .voice import VoiceClient, VoiceError

ROOT = Path(__file__).resolve().parents[1]
INSTANCE = str(uuid.uuid5(uuid.NAMESPACE_URL, str(ROOT.resolve()).lower()))


class Payload(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Connect(Payload):
    replace: bool = False


class Generation(Payload):
    generation: int = Field(ge=1, le=2**31-1)


class Begin(Generation):
    reuse_turn: bool = False


class Routing(Payload):
    asr: Literal["local", "cloud"]
    tts: Literal["local", "cloud"]
    allow_audio_upload: bool
    allow_text_upload: bool


class Settings(Generation):
    routing: Routing


class Text(Generation):
    text: str = Field(min_length=1, max_length=300)


class State(Generation):
    state: Literal["idle", "listening", "speaking", "error"]


class Device(Payload):
    address: str = Field(min_length=1, max_length=100)


def owner(request):
    value = request.headers.get("x-companion-client", "")
    try:
        uuid.UUID(value)
    except ValueError as exc:
        raise VoiceError(401, "CLIENT_REQUIRED", "请从工作台连接会话") from exc
    return value


def create_app(config=None, controller=None):
    config = config or {}
    port = int(config.get("port", 8766))
    url = config.get("voice_url", "http://127.0.0.1:8765")
    parsed = urlsplit(url)
    if (parsed.scheme != "http" or parsed.hostname not in ("127.0.0.1", "localhost")
            or parsed.username or parsed.password or parsed.path not in ("", "/")
            or parsed.query or parsed.fragment):
        raise ValueError("语音服务地址必须是本机 http://127.0.0.1:端口")
    control = controller or Controller(VoiceClient(url, config.get("request_timeout", 60)), Robot())

    @asynccontextmanager
    async def lifespan(app):
        control.robot.start()
        try:
            yield
        finally:
            await control.close()

    app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    app.state.control = control
    allowed = {f"127.0.0.1:{port}", f"localhost:{port}"}

    @app.middleware("http")
    async def local_only(request, call_next):
        host, origin = request.headers.get("host", ""), request.headers.get("origin")
        if host not in allowed or (origin and origin not in {f"http://{x}" for x in allowed}):
            return JSONResponse({"error": {"code": "LOCAL_ONLY", "message": "仅允许本机工作台访问"}}, status_code=403)
        size = request.headers.get("content-length", "0")
        if not size.isdecimal() or int(size) > 2097152:
            return Response(status_code=413)
        # No cookie authentication / permissive CORS: each tab owns an in-memory UUID.
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; media-src 'self' blob:; worker-src 'self'; frame-ancestors 'none'"
        return response

    @app.exception_handler(VoiceError)
    async def voice_error(request, exc):
        return JSONResponse({"error": {"code": exc.code, "message": exc.message}}, status_code=exc.status)

    @app.exception_handler(BleConsoleError)
    async def ble_error(request, exc):
        return JSONResponse({"error": {"code": "BLE_ERROR", "message": str(exc)}}, status_code=503)

    @app.get("/")
    async def index():
        return FileResponse(ROOT / "static/index.html")

    @app.get("/api/health")
    async def health():
        result = {"app": "stopwatch-voice-companion", "version": __version__, "instance": INSTANCE,
            "pid": os.getpid(), "device_address": config.get("device_address", ""),
            "voice_url": url, "robot": control.robot.snapshot()}
        try:
            result["voice"] = await control.voice.health()
            result["capabilities"] = await control.voice.capabilities()
        except VoiceError as exc:
            result["voice_error"] = {"code": exc.code, "message": exc.message}
        return result

    @app.post("/api/session")
    async def connect(payload: Connect, request: Request):
        return await control.connect(owner(request), payload.replace)

    @app.get("/api/session")
    async def heartbeat(request: Request):
        return await control.heartbeat(owner(request))

    @app.delete("/api/session")
    async def release(request: Request):
        await control.release(owner(request))
        return {"released": True}

    @app.patch("/api/settings")
    async def settings(payload: Settings, request: Request):
        routing = payload.routing.model_dump()
        if (routing["asr"] == "cloud" and not routing["allow_audio_upload"]
                or routing["tts"] == "cloud" and not routing["allow_text_upload"]):
            raise VoiceError(403, "UPLOAD_DENIED", "云端路径需单独勾选对应上传许可")
        return await control.settings(owner(request), payload.generation, routing)

    @app.post("/api/begin")
    async def begin(payload: Begin, request: Request):
        return await control.begin(owner(request), payload.generation, payload.reuse_turn)

    @app.post("/api/stop")
    async def stop(payload: Generation, request: Request):
        return await control.stop(owner(request), payload.generation)

    @app.post("/api/state")
    async def state(payload: State, request: Request):
        await control.state(owner(request), payload.generation, payload.state)
        return {"ok": True}

    @app.post("/api/asr")
    async def asr(request: Request):
        tab = owner(request)
        try:
            generation = int(request.headers.get("x-generation", ""))
        except ValueError as exc:
            raise VoiceError(422, "GENERATION_REQUIRED", "缺少当前操作代号") from exc
        control.check(tab, generation)
        chunks, length = [], 0
        async for chunk in request.stream():
            length += len(chunk)
            if length > 2097152:
                raise VoiceError(413, "AUDIO_TOO_LARGE", "录音超过 2 MiB")
            chunks.append(chunk)
        return {"text": await control.perform(tab, generation, "asr", b"".join(chunks))}

    @app.post("/api/tts")
    async def tts(payload: Text, request: Request):
        if not payload.text.strip():
            raise VoiceError(422, "TEXT_EMPTY", "请输入要回读的文字")
        data = await control.perform(owner(request), payload.generation, "tts", payload.text)
        return Response(data, media_type="audio/wav")

    @app.get("/api/devices")
    async def devices(request: Request):
        control.authorize(owner(request))
        return {"devices": await control.robot.scan()}

    @app.post("/api/device")
    async def device(payload: Device, request: Request):
        tab = owner(request)
        control.authorize(tab)
        await control.robot.connect(payload.address)
        # A takeover while Windows was pairing must not leave the old tab active.
        control.authorize(tab)
        return control.robot.snapshot()

    @app.delete("/api/device")
    async def disconnect_device(request: Request):
        control.authorize(owner(request))
        await control.robot.disconnect()
        return control.robot.snapshot()

    app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")
    return app
