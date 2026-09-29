"""Loopback-only browser facade. The voice session token never leaves Python."""
from contextlib import asynccontextmanager
import asyncio
import json
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
from .answer import AnswerClient
from .cost import CostClient, MONITOR_TASK_ID
from .task_monitor import TaskMonitor
from .codex_monitor import CodexMonitor
from .codex_source import JsonlSource, HookSpool, QuotaRPC
from . import sentinel_voice_library as voice_library
from .robot import Robot, BleConsoleError
from .voice import VoiceClient, VoiceError

ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = ROOT.parents[1]
INSTANCE = str(uuid.uuid5(uuid.NAMESPACE_URL, str(ROOT.resolve()).lower()))
SOUND_FILES = {
    1: "01-ready.wav", 2: "02-confirm.wav", 3: "03-thinking.wav",
    4: "04-success.wav", 5: "05-error.wav", 6: "06-goodbye.wav",
}


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
    allow_answer_upload: bool = False
    speech: "Speech | None" = None


class Speech(Payload):
    speaker_id: int = Field(default=3, ge=3, le=102)
    cloud_voice: str = Field(default="Cherry", min_length=1, max_length=40)
    speed: float = Field(default=1.0, ge=0.75, le=1.5)


class Text(Generation):
    text: str = Field(min_length=1, max_length=300)
    watch_speech: bool = False


class CostQuery(Generation):
    question: str = Field(min_length=1, max_length=1000)
    allow_ai: bool = False


class MonitorSettings(Payload):
    enabled: bool
    mode: Literal['auto', 'specific'] = 'auto'
    task_id: str = Field(default='', max_length=28)
    target: Literal['desktop', 'watch', 'both'] = 'desktop'
    sound: bool = False
    sound_kind: Literal['speech', 'beep'] = 'speech'
    sound_target: Literal['pc', 'watch'] = 'pc'


class CodexSettings(Payload):
    enabled: bool = False
    mode: Literal['auto', 'specific'] = 'auto'
    thread_id: str = Field(default='', max_length=100, pattern=r'^[A-Za-z0-9_-]*$')
    target: Literal['desktop', 'watch', 'both'] = 'desktop'
    sound: bool = False
    sound_target: Literal['pc', 'watch'] = 'pc'
    threshold: int = Field(default=20, ge=1, le=99)
    bucket_id: str = Field(default='', max_length=80)
    ring_mode: Literal['hidden', 'visible', 'hover'] = 'hidden'


class VoiceLibraryGenerate(Payload):
    item_id: str = Field(default='', max_length=40)
    force: bool = False


class State(Generation):
    state: Literal["idle", "listening", "speaking", "error"]


class Device(Payload):
    address: str = Field(min_length=1, max_length=100)


class Character(Payload):
    expression: str = Field(min_length=2, max_length=20, pattern=r"^[a-z-]+$")
    mode: Literal["once", "loop"] = "once"
    target: Literal["desktop", "watch", "both"]


class CharacterBubble(Payload):
    text: str = Field(min_length=1, max_length=300)
    target: Literal["desktop", "watch", "both"]


class CharacterTarget(Payload):
    target: Literal["desktop", "watch", "both"]


class SoundRequest(Payload):
    sound_id: int = Field(ge=1, le=6)


class SoundVolume(Payload):
    volume: int = Field(ge=0, le=100)


class AudioRecord(Payload):
    echo: bool = False


SENTINEL_DEFAULTS = {'enabled': True, 'mode': 'auto', 'task_id': '',
                     'target': 'desktop', 'sound': False, 'sound_kind': 'speech', 'sound_target': 'pc'}


def _sentinel_preferences(path):
    try:
        value = json.loads(path.read_text(encoding='utf-8'))
        return MonitorSettings.model_validate(value).model_dump()
    except FileNotFoundError:
        return dict(SENTINEL_DEFAULTS)
    except (OSError, ValueError):
        # An unreadable saved "off" preference must not silently enable polling.
        return {**SENTINEL_DEFAULTS, 'enabled': False}


def _save_sentinel_preferences(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temporary.replace(path)


def _codex_preferences(path):
    try:
        saved = json.loads(path.read_text(encoding='utf-8'))
        if isinstance(saved, dict):
            # The old checkbox defaulted to on, so it cannot represent a user's
            # explicit choice under the new three-way, default-hidden setting.
            saved.pop('show_ring', None)
        values = CodexSettings.model_validate(saved).model_dump()
    except (FileNotFoundError, OSError, ValueError):
        values = CodexSettings().model_dump()
    values['enabled'] = False  # startup always requires a fresh, explicit opt-in
    return values


def owner(request):
    value = request.headers.get("x-companion-client", "")
    try:
        uuid.UUID(value)
    except ValueError as exc:
        raise VoiceError(401, "CLIENT_REQUIRED", "请从工作台连接会话") from exc
    return value


def create_app(config=None, controller=None, cost_client=None):
    config = config or {}
    auto_connect_device = config.get("auto_connect_device", True)
    if not isinstance(auto_connect_device, bool):
        raise ValueError("auto_connect_device 必须是布尔值")
    auto_connect_voice = config.get("auto_connect_voice", True)
    if not isinstance(auto_connect_voice, bool):
        raise ValueError("auto_connect_voice 必须是布尔值")
    if not isinstance(config.get("device_address", ""), str):
        raise ValueError("device_address 必须是字符串")
    manager = config.get("_voice_service_manager")
    service_task = None
    cost = cost_client or CostClient(config.get('cost_url', 'http://127.0.0.1:8000'))

    def start_service():
        nonlocal service_task
        if manager and (service_task is None or service_task.done()):
            service_task = asyncio.create_task(asyncio.to_thread(manager.ensure))
    port = int(config.get("port", 8766))
    url = config.get("voice_url", "http://127.0.0.1:8765")
    parsed = urlsplit(url)
    if (parsed.scheme != "http" or parsed.hostname not in ("127.0.0.1", "localhost")
            or parsed.username or parsed.password or parsed.path not in ("", "/")
            or parsed.query or parsed.fragment):
        raise ValueError("语音服务地址必须是本机 http://127.0.0.1:端口")
    control = controller or Controller(VoiceClient(url, config.get("request_timeout", 60)), Robot(),
        AnswerClient(config.get("answer_base_url", ""), config.get("answer_model", ""),
            config.get("answer_api_key_env", "GORK_ANSWER_API_KEY"), config.get("request_timeout", 60)),
        config.get("answer_history_turns", 4))
    monitor = TaskMonitor(cost, control)
    codex = CodexMonitor(control,
        jsonl=JsonlSource(config.get('codex_jsonl_root')),
        hooks=HookSpool(config.get('codex_hook_queue', control.codex_spool)),
        rpc=QuotaRPC(config.get('codex_executable', 'codex')))
    voice_library_lock = asyncio.Lock()
    control.task_monitor = monitor
    control.codex_monitor = codex
    sentinel_path = Path(config.get('sentinel_state_path', ROOT / 'sentinel.local.json'))
    sentinel_initial = _sentinel_preferences(sentinel_path)
    codex_path = Path(config.get('codex_state_path', ROOT / 'codex-sentinel.local.json'))
    codex_initial = _codex_preferences(codex_path)

    @asynccontextmanager
    async def lifespan(app):
        control.robot.start()
        if controller is None and auto_connect_device:
            control.robot.start_auto_connect(config.get("device_address", ""))
        start_service()
        await monitor.configure(**sentinel_initial)
        await codex.configure(codex_initial)
        try:
            yield
        finally:
            await monitor.stop()
            await codex.stop()
            await control.close()
            await cost.close()
            if manager:
                await asyncio.to_thread(manager.close)
            if service_task:
                await service_task

    app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    app.state.control = control
    app.state.cost = cost
    app.state.task_monitor = monitor
    app.state.codex_monitor = codex
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

    @app.get("/favicon.ico")
    async def favicon():
        return Response(status_code=204)

    @app.get("/api/sounds/{sound_id}/preview")
    async def sound_preview(sound_id: int):
        filename = SOUND_FILES.get(sound_id)
        if not filename:
            return JSONResponse({"error": {"code": "SOUND_NOT_FOUND", "message": "内置声音不存在"}}, status_code=404)
        return FileResponse(PROJECT_ROOT / "01-assets/audio/source" / filename, media_type="audio/wav")

    @app.get("/api/health")
    async def health():
        result = {"app": "stopwatch-voice-companion", "version": __version__, "instance": INSTANCE,
            "pid": os.getpid(), "launch": os.environ.get("GORK_LAUNCH_TOKEN", ""),
            "device_address": config.get("device_address", ""),
            "voice_url": url, "auto_connect_voice": auto_connect_voice,
            "watch_speech_sync": True,
            "robot": control.robot.snapshot()}
        result["answer"] = control.answer_capability()
        result["voice_service"] = manager.snapshot() if manager else {"mode": "unknown", "owned": False}
        if service_task and not service_task.done():
            result["voice_service"]["mode"] = "starting"
        try:
            result["voice"] = await control.voice.health()
            result["capabilities"] = await control.voice.capabilities()
        except VoiceError as exc:
            result["voice_error"] = {"code": exc.code, "message": exc.message}
        return result

    @app.post("/api/voice-service/start")
    async def retry_service(request: Request):
        owner(request)
        if not manager:
            raise VoiceError(503, "SERVICE_NOT_CONFIGURED", "请配置语音服务启动入口后重开控制台")
        start_service()
        return {"mode": "starting"}

    @app.get("/api/desktop/state")
    async def desktop_state():
        return control.desktop_state()

    @app.post("/api/desktop/stop")
    async def desktop_stop():
        return await control.desktop_stop()

    @app.post("/api/workspace")
    async def acquire_workspace(payload: Connect, request: Request):
        return await control.acquire_workspace(owner(request), payload.replace)

    @app.get('/api/cost/health')
    async def cost_health():
        return await cost.health()

    @app.get('/api/cost/sentinel')
    async def sentinel_state():
        return monitor.state()

    @app.get('/api/codex/sentinel')
    async def codex_sentinel_state():
        return codex.state()

    @app.put('/api/codex/sentinel')
    async def codex_sentinel_settings(payload: CodexSettings, request: Request):
        control.renew_workspace(owner(request))
        if payload.mode == 'specific' and payload.enabled and not payload.thread_id:
            raise VoiceError(422, 'CODEX_THREAD_REQUIRED', '请指定 Codex 任务')
        values = payload.model_dump()
        try:
            await asyncio.to_thread(_save_sentinel_preferences, codex_path, values)
        except OSError as exc:
            raise VoiceError(503, 'CODEX_PREFERENCES', 'Codex 哨兵设置无法保存') from exc
        return await codex.configure(values)

    @app.post('/api/codex/quota/refresh')
    async def codex_quota_refresh(request: Request):
        control.renew_workspace(owner(request))
        return await codex.refresh_quota()

    @app.get('/api/character/voice-library')
    async def sentinel_voice_library():
        return await asyncio.to_thread(voice_library.catalogue)

    @app.get('/api/character/voice-library/{item_id}/preview')
    async def sentinel_voice_preview(item_id: str):
        item = voice_library.BY_ID.get(item_id)
        if not item:
            raise VoiceError(404, 'VOICE_LIBRARY_ITEM', '播报短句不存在')
        try:
            path = await asyncio.to_thread(voice_library.cached_path, item[2])
        except (FileNotFoundError, ValueError) as exc:
            raise VoiceError(404, 'VOICE_LIBRARY_MISSING', '该短句尚无可用的本地语音，请先生成') from exc
        return FileResponse(path, media_type='audio/wav')

    @app.post('/api/character/voice-library/generate')
    async def sentinel_voice_generate(payload: VoiceLibraryGenerate, request: Request):
        who = owner(request)
        control.require_voice(who)
        if control.routing.get('tts') != 'cloud' or not control.routing.get('allow_text_upload'):
            raise VoiceError(403, 'VOICE_LIBRARY_CLOUD', '请先在设置页启用云端 TTS 并允许发送文字')
        if not control.turn or control.pending or control.phase in ('listening', 'processing', 'speaking'):
            raise VoiceError(409, 'VOICE_LIBRARY_BUSY', '请等待当前语音任务结束后再生成')
        if voice_library_lock.locked():
            raise VoiceError(409, 'VOICE_LIBRARY_BUSY', '语音库正在生成，请稍候')
        if payload.item_id and payload.item_id not in voice_library.BY_ID:
            raise VoiceError(404, 'VOICE_LIBRARY_ITEM', '播报短句不存在')
        async with voice_library_lock:
            original_session, original_turn, original_generation = control.voice.session, control.turn, control.generation
            entries = ([voice_library.BY_ID[payload.item_id]] if payload.item_id else voice_library.PHRASES)
            generated = []
            for item_id, _, phrase in entries:
                if not payload.force:
                    try:
                        await asyncio.to_thread(voice_library.cached_path, phrase)
                        continue
                    except (FileNotFoundError, ValueError):
                        pass
                control.require_voice(who)
                if (control.voice.session != original_session or control.turn != original_turn
                        or control.generation != original_generation or control.routing.get('tts') != 'cloud'
                        or not control.routing.get('allow_text_upload')):
                    raise VoiceError(409, 'VOICE_LIBRARY_CHANGED', '语音会话或上传许可已变化，已停止生成')
                request_id = control.voice.request_id('tts')
                control.pending[request_id] = (original_turn, original_session, original_generation)
                try:
                    data = await control.voice.synthesize(phrase, original_turn, request_id,
                                                           {'cloud_voice': voice_library.VOICE, 'request_voice': True})
                finally:
                    control.pending.pop(request_id, None)
                if control.generation != original_generation or control.voice.session != original_session:
                    raise VoiceError(409, 'VOICE_LIBRARY_CHANGED', '语音操作已停止，未保存迟到结果')
                try:
                    await asyncio.to_thread(voice_library.save, phrase, data)
                except (OSError, ValueError) as exc:
                    raise VoiceError(502, 'VOICE_LIBRARY_AUDIO', f'短句音频无法保存或不适合 Watch：{phrase}') from exc
                generated.append(item_id)
            return {'generated': generated, 'library': await asyncio.to_thread(voice_library.catalogue)}

    @app.put('/api/cost/sentinel')
    async def sentinel_settings(payload: MonitorSettings, request: Request):
        control.renew_workspace(owner(request))
        if payload.enabled and payload.mode == 'specific' and not MONITOR_TASK_ID.fullmatch(payload.task_id):
            raise VoiceError(422, 'COST_TASK_ID', '请选择有效的智算任务')
        settings = payload.model_dump()
        try:
            await asyncio.to_thread(_save_sentinel_preferences, sentinel_path, settings)
        except OSError as exc:
            raise VoiceError(503, 'MONITOR_PREFERENCES', '任务哨兵设置无法保存，请检查本机目录权限') from exc
        return await monitor.configure(**settings)

    @app.get('/api/cost/projects')
    async def cost_projects(request: Request, page: int = 1):
        who = owner(request)
        control.renew_workspace(who)
        if not 1 <= page <= 10000:
            raise VoiceError(422, 'COST_PAGE', '无效页码')
        result = await cost.projects(page)
        control.authorize(who)
        return result

    @app.get('/api/cost/projects/{project_id}')
    async def cost_project(project_id: str, request: Request):
        who = owner(request)
        control.renew_workspace(who)
        result = await cost.project(project_id)
        control.authorize(who)
        return result

    @app.post('/api/cost/query')
    async def cost_query(payload: CostQuery, request: Request):
        who = owner(request)
        control.renew_workspace(who)
        if payload.generation <= control.generation:
            raise VoiceError(409, 'STALE', '查询已过期')
        control.invalidate(payload.generation)
        task = asyncio.current_task()
        control.answer_tasks.add(task)
        try:
            result = await cost.query(payload.question, payload.allow_ai)
            control.authorize(who)
            if control.generation != payload.generation:
                raise VoiceError(409, 'STALE', '查询已取消')
            return result
        except asyncio.CancelledError:
            raise VoiceError(409, 'STALE', '查询已停止；上游模型可能仍在执行') from None
        finally:
            control.answer_tasks.discard(task)

    @app.get("/api/workspace")
    async def workspace_heartbeat(request: Request):
        control.renew_workspace(owner(request))
        return control.desktop_state()

    @app.delete("/api/workspace")
    async def release_workspace(request: Request):
        await control.release_workspace(owner(request))
        return {"released": True}

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

    @app.delete("/api/voice/session")
    async def release_voice(request: Request):
        await control.release_voice(owner(request))
        return {"released": True}

    @app.patch("/api/settings")
    async def settings(payload: Settings, request: Request):
        routing = payload.routing.model_dump()
        if (routing["asr"] == "cloud" and not routing["allow_audio_upload"]
                or routing["tts"] == "cloud" and not routing["allow_text_upload"]):
            raise VoiceError(403, "UPLOAD_DENIED", "云端路径需单独勾选对应上传许可")
        return await control.settings(owner(request), payload.generation, routing, payload.allow_answer_upload,
                                      payload.speech.model_dump() if payload.speech else None)

    @app.post("/api/answer")
    async def answer(payload: Text, request: Request):
        if not payload.text.strip():
            raise VoiceError(422, "TEXT_EMPTY", "请输入要发送的文字")
        return {"text": await control.ask(owner(request), payload.generation, payload.text, payload.watch_speech)}

    @app.delete("/api/answer/history")
    async def clear_answer_history(request: Request):
        return control.clear_answer_history(owner(request))

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
        data = await control.perform(owner(request), payload.generation, "tts", payload.text, payload.watch_speech)
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

    @app.post("/api/character")
    async def play_character(payload: Character, request: Request):
        return await control.play_character(owner(request), payload.expression, payload.mode, payload.target)

    @app.delete("/api/character")
    async def restore_character(request: Request):
        return await control.restore_character_auto(owner(request))

    @app.post("/api/character/bubble")
    async def character_bubble(payload: CharacterBubble, request: Request):
        return await control.set_character_bubble(owner(request), payload.text, payload.target)

    @app.delete("/api/character/bubble")
    async def clear_character_bubble(payload: CharacterTarget, request: Request):
        return await control.clear_character_bubble(owner(request), payload.target)

    @app.post("/api/device/sound")
    async def play_sound(payload: SoundRequest, request: Request):
        control.authorize(owner(request))
        return await control.robot.play_sound(payload.sound_id)

    @app.delete("/api/device/sound")
    async def stop_sound(request: Request):
        control.authorize(owner(request))
        return await control.robot.stop_sound()

    @app.put("/api/device/sound/volume")
    async def sound_volume(payload: SoundVolume, request: Request):
        control.authorize(owner(request))
        return await control.robot.set_sound_volume(payload.volume)

    @app.get("/api/device/audio")
    async def audio_status(request: Request):
        control.authorize(owner(request))
        return control.robot.audio_snapshot()

    @app.post("/api/device/audio/record")
    async def audio_record(payload: AudioRecord, request: Request):
        control.authorize(owner(request))
        return control.robot.start_audio_record(payload.echo)

    async def accept_audio_play(request: Request, *, speech: bool):
        tab = owner(request)
        control.authorize(tab)
        if request.headers.get("content-type", "").split(";", 1)[0].lower() != "audio/wav":
            raise VoiceError(415, "WAV_REQUIRED", "仅接受 PCM16 单声道 WAV")
        data = await request.body()
        if len(data) > 484096:
            raise VoiceError(413, "AUDIO_TOO_LARGE", "设备音频最多 10 秒")
        if speech:
            try:
                generation = int(request.headers.get("x-generation", ""))
            except ValueError as exc:
                raise VoiceError(422, "GENERATION_REQUIRED", "缺少当前 Watch 朗读操作代号") from exc
            text = control.take_watch_speech_text(tab, generation)
            return control.robot.start_audio_play(data, speech=True, speech_text=text)
        return control.robot.start_audio_play(data)

    @app.post("/api/device/audio/play")
    async def audio_play(request: Request):
        return await accept_audio_play(request, speech=False)

    @app.post("/api/device/audio/speech")
    async def audio_speech(request: Request):
        return await accept_audio_play(request, speech=True)

    @app.delete("/api/device/audio")
    async def audio_cancel(request: Request):
        control.authorize(owner(request))
        return await control.robot.cancel_audio()

    @app.get("/api/device/audio/result/{job_id}")
    async def audio_result(job_id: str, request: Request):
        control.authorize(owner(request))
        try:
            uuid.UUID(job_id)
        except ValueError as exc:
            raise VoiceError(422, "JOB_ID_INVALID", "音频任务编号无效") from exc
        return Response(control.robot.take_audio_result(job_id), media_type="audio/wav")

    app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")
    return app
