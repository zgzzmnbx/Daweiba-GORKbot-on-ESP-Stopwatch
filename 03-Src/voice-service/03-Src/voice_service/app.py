import asyncio
import json
import secrets
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Literal

from fastapi import FastAPI, File, Form, Header, Request, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, StrictBool
from starlette.formparsers import MultiPartParser

from . import __version__
from .audio import AudioError, decode_wav
from .broker import Broker, ServiceError
from .config import load_settings
from .voices import CLOUD_VOICES, CLOUD_VOICE_IDS

STATIC = Path(__file__).parent / "static"
SessionHeader = Annotated[str | None, Header(alias="X-Voice-Session")]
RequestId = Annotated[str, Field(pattern=r"^[a-zA-Z0-9_-]{1,80}$")]


class StrictBody(BaseModel):
    model_config = ConfigDict(extra="forbid")


class NewSession(StrictBody):
    replace: bool = False


class CancelBody(StrictBody):
    turn_id: int = Field(ge=1)


class RoutingBody(StrictBody):
    asr: Literal['local','cloud']
    tts: Literal['local','cloud']
    allow_audio_upload: StrictBool
    allow_text_upload: StrictBool


class Synthesis(StrictBody):
    request_id: RequestId
    turn_id: int = Field(ge=1)
    text: str = Field(min_length=1, max_length=300)
    speaker_id: int = Field(default=3, ge=3, le=102)
    speed: float = Field(default=1.0, ge=0.75, le=1.5)
    sample_rate: Literal[16000, 24000] = 24000
    cloud_voice: str | None = Field(default=None, max_length=40)


class LocalBoundary:
    """Bound request bodies before multipart parsing; reject foreign browser origins."""
    def __init__(self, app, config):
        self.app, self.config = app, config

    async def __call__(self, scope, receive, send):
        if scope["type"] not in ("http", "websocket"):
            return await self.app(scope, receive, send)
        headers = dict(scope["headers"])
        host = headers.get(b"host", b"").decode("latin1")
        origin = headers.get(b"origin", b"").decode("latin1")
        hosts = {f"127.0.0.1:{self.config.port}", f"localhost:{self.config.port}"}
        valid = host in hosts and (not origin or origin in {f"http://127.0.0.1:{self.config.port}", f"http://localhost:{self.config.port}"})
        if not valid:
            if scope["type"] == "websocket":
                return await send({"type": "websocket.close", "code": 1008})
            return await JSONResponse({"error": {"code": "ORIGIN_DENIED", "message": "仅允许本机同源访问"}}, status_code=403)(scope, receive, send)
        if scope["type"] == "http" and scope["method"] in ("POST", "PATCH", "PUT"):
            limit = self.config.max_upload + 65536 if scope["path"] == "/v1/asr/transcribe" else 16384
            body = bytearray()
            while True:
                message = await receive()
                if message["type"] == "http.disconnect":
                    return
                body.extend(message.get("body", b""))
                if len(body) > limit:
                    return await JSONResponse({"error": {"code": "TOO_LARGE", "message": "请求超过大小限制"}}, status_code=413)(scope, receive, send)
                if not message.get("more_body"):
                    break
            used = False
            async def bounded_receive():
                nonlocal used
                if not used:
                    used = True
                    return {"type": "http.request", "body": bytes(body), "more_body": False}
                return await receive()
            await self.app(scope, bounded_receive, send)
        else:
            await self.app(scope, receive, send)


def create_app(config=None, broker=None):
    config = config or load_settings()
    broker = broker or Broker(config)
    # The outer body cap bounds memory. Do not let UploadFile spool raw recordings to disk.
    MultiPartParser.spool_max_size = config.max_upload + 65536

    @asynccontextmanager
    async def lifespan(app):
        await broker.start()
        yield
        await broker.close()

    app = FastAPI(title="智算语音桥", version=__version__, lifespan=lifespan, docs_url=None, redoc_url=None)
    app.state.broker = broker
    app.state.config = config
    app.add_middleware(LocalBoundary, config=config)

    @app.middleware("http")
    async def response_headers(request, call_next):
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        if request.url.path != "/docs":
            response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; media-src 'self' blob:; worker-src 'self'; frame-ancestors 'none'"
        return response

    @app.exception_handler(ServiceError)
    async def service_error(request, exc):
        return JSONResponse({"error": {"code": exc.code, "message": exc.message, "retryable": exc.status in (429, 503, 504)}}, status_code=exc.status)

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request, exc):
        # Pydantic errors include input; do not echo submitted text/audio/secrets.
        return JSONResponse({"error": {"code": "INVALID_INPUT", "message": "参数无效，请检查文本长度、音色和轮次"}}, status_code=400)

    @app.get("/")
    async def index():
        return FileResponse(STATIC / "index.html")

    @app.get("/v1/health")
    async def health():
        ready = all(e["state"] == "ready" for e in broker.engines.values())
        return {"service": "zhisuan-voice-service", "version": __version__, "alive": True, "ready": ready,
            "engines": broker.engines, "cloud":broker.cloud_status(), "queue_depth": broker.queue.qsize(), "active": broker.active_id is not None}

    @app.get("/v1/capabilities")
    async def capabilities():
        return {"protocol_version": 1, "asr": {"provider": "sherpa_sensevoice", "format": "wav-pcm16-mono-16000", "streaming": False, **broker.engines["asr"]},
            "tts": {"provider": "sherpa_kokoro", "native_sample_rate": 24000, "output_sample_rates": [16000, 24000], "streaming": False,
                "speakers": [{"id": i, "label": f"中文{'女声' if i < 58 else '男声'} · {i}"} for i in range(3, 103)], **broker.engines["tts"]},
            "cloud": {'implemented':True,'asr_model':config.cloud_asr_model,'tts_model':config.cloud_tts_model,
                      'voices':CLOUD_VOICES, 'default_voice':config.cloud_voice,
                      'request_voice':True, 'speeds':[1.0], 'streaming':False, **broker.cloud_status()}, "business": False, "device_audio": False,
            "limits": {"recording_seconds": config.max_seconds, "upload_bytes": config.max_upload, "text_characters": config.max_text}}

    @app.get("/v1/settings")
    async def settings():
        return {"asr": {"mode": broker.routing['asr'], "threads": config.asr_threads}, "tts": {"mode": broker.routing['tts'], "threads": config.tts_threads, "speaker_id": config.speaker},
            "routing":dict(broker.routing),
            "cloud": {"implemented": True, **broker.cloud_status(), "allow_audio_upload": broker.routing['allow_audio_upload'], "allow_text_upload": broker.routing['allow_text_upload']},
            "privacy": {"retain_raw_audio": False, "log_transcripts": False}, "business": False, "device": False}

    @app.patch('/v1/settings')
    async def update_settings(body: RoutingBody, token: SessionHeader = None):
        broker.set_routing(token,body.model_dump())
        return await settings()

    @app.post("/v1/sessions")
    async def new_session(body: NewSession):
        return broker.new_session(body.replace)

    @app.post("/v1/sessions/{session_id}/turns")
    async def next_turn(session_id: str, token: SessionHeader = None):
        broker.authorize(token)
        if not secrets.compare_digest(session_id, token):
            raise ServiceError(403, "SESSION_MISMATCH", "会话不匹配")
        return broker.next_turn(token)

    @app.delete("/v1/sessions/{session_id}")
    async def end_session(session_id: str, token: SessionHeader = None):
        broker.authorize(token)
        if not secrets.compare_digest(session_id, token):
            raise ServiceError(403, "SESSION_MISMATCH", "会话不匹配")
        broker.end_session(token)
        return {"status": "closed"}

    @app.get("/v1/session")
    async def session(token: SessionHeader = None):
        broker.authorize(token)
        return {"turn_id": broker.turn, "protocol_version": 1, 'routing':dict(broker.routing)}

    async def await_job(job):
        await job.done.wait()
        if job.error:
            raise ServiceError(job.error["http_status"], job.error["code"], job.error["message"])
        return job

    @app.post("/v1/asr/transcribe")
    async def transcribe(request_id: Annotated[str, Form(pattern=r"^[a-zA-Z0-9_-]{1,80}$")], turn_id: Annotated[int, Form(ge=1)],
                         audio: Annotated[UploadFile, File()], token: SessionHeader = None):
        broker.authorize(token)
        raw = await audio.read(config.max_upload + 1)
        await audio.close()
        if len(raw) > config.max_upload:
            raise ServiceError(413, "AUDIO_TOO_LARGE", "录音文件过大")
        try:
            decode_wav(raw, config.max_seconds, config.max_upload)
        except AudioError as exc:
            raise ServiceError(415, "AUDIO_INVALID", str(exc)) from exc
        job = await await_job(broker.submit(token, turn_id, request_id, "asr", {"audio": raw}))
        return job.public()

    @app.post("/v1/tts/synthesize")
    async def synthesize(body: Synthesis, token: SessionHeader = None):
        text = body.text.strip()
        if not text or len(text) > config.max_text or any(ord(c) < 32 and c not in "\n\t" for c in text):
            raise ServiceError(400, "TEXT_INVALID", "请输入有效的播报文字")
        broker.authorize(token)
        if broker.turn_routing['tts']=='cloud' and body.speed!=1.0:
            raise ServiceError(400,'CLOUD_SPEED','当前云端音色仅支持自然语速 1.0×')
        if body.cloud_voice is not None and body.cloud_voice not in CLOUD_VOICE_IDS:
            raise ServiceError(400, 'VOICE_INVALID', '请选择服务提供的云端音色')
        payload = {"text": text, "speaker_id": body.speaker_id, "speed": body.speed, "sample_rate": body.sample_rate}
        payload['cloud_voice'] = body.cloud_voice or config.cloud_voice
        job = await await_job(broker.submit(token, body.turn_id, body.request_id, "tts", payload))
        return Response(job.value["result"]["audio"], media_type="audio/wav", headers={
            "X-Request-Id": job.request_id, "X-Provider":job.public()['provider'],
            "X-Provider-Elapsed-Ms":str(job.metrics.get('provider_elapsed_ms',job.metrics.get('inference_ms',0))),
            **({'X-Inference-Ms':str(job.metrics['inference_ms'])} if 'inference_ms' in job.metrics else {}),
            "X-Server-Total-Ms": str(job.metrics["server_total_ms"]), "X-Audio-Sample-Rate": str(body.sample_rate),
            "Content-Disposition": 'inline; filename="voice.wav"'})

    @app.get("/v1/requests/{request_id}")
    async def request_status(request_id: str, token: SessionHeader = None):
        return broker.get(token, request_id).public()

    @app.post("/v1/requests/{request_id}/cancel")
    async def cancel(request_id: RequestId, body: CancelBody, token: SessionHeader = None):
        return broker.cancel(token, request_id, body.turn_id)

    @app.websocket("/v1/events")
    async def events(socket: WebSocket):
        await socket.accept()
        try:
            # Session secret stays out of URLs/access logs.
            hello = await asyncio.wait_for(socket.receive_json(), timeout=5)
            if not isinstance(hello, dict) or not isinstance(hello.get("session_id"), str):
                raise ValueError("Invalid session greeting")
            token = hello.get("session_id")
            broker.authorize(token)
            sequence = broker.event_sequence
            while True:
                broker.authorize(token)
                for event in list(broker.events):
                    if event["sequence"] > sequence and event["session_id"] == token:
                        await socket.send_json({k: v for k, v in event.items() if k != "session_id"})
                        sequence = event["sequence"]
                await socket.send_json({"type": "health", "engines": broker.engines})
                try:
                    message = await asyncio.wait_for(socket.receive_text(), timeout=1)
                    if message == "close":
                        return
                except asyncio.TimeoutError:
                    pass
        except (WebSocketDisconnect, ServiceError, asyncio.TimeoutError, ValueError, TypeError):
            try:
                await socket.close(code=1008)
            except RuntimeError:
                pass

    app.mount("/static", StaticFiles(directory=STATIC), name="static")
    return app
