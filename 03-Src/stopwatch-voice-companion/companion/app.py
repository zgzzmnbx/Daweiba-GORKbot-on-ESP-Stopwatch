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
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, SecretStr

from . import __version__
from .voice_volume import VoiceVolume
from .traffic import TrafficMonitor
from .motion import MotionStore, MotionLibrary, Conflict
from .control import Controller, BLE_EXPRESSIONS
from .answer import AnswerClient
from .answer_store import AnswerStore, BASE_URL as DEEPSEEK_URL
from .cost import CostClient, MONITOR_TASK_ID
from .task_monitor import TaskMonitor
from .codex_monitor import CodexMonitor
from .codex_source import JsonlSource, HookSpool, QuotaRPC
from .quota_usage import QuotaUsage
from .ccswitch_usage import CCSwitchUsage
from . import sentinel_voice_library as voice_library
from . import speech_cache
from .robot import Robot, BleConsoleError
from .voice import VoiceClient, VoiceError
from .external import ClientRegistry, ExternalNotifications, Notification, CancelTask, Heartbeat, ClientPolicy, RegisterClient

ROOT = Path(__file__).resolve().parents[1]

class PCVoiceVolume(BaseModel):
    model_config = ConfigDict(extra='forbid')
    volume: int = Field(ge=0, le=100, strict=True)

class AnswerSetup(BaseModel):
    model_config = ConfigDict(extra='forbid')
    model: Literal['deepseek-flash','deepseek-v4-pro'] = 'deepseek-flash'
    api_key: SecretStr = SecretStr('')
    system_prompt: str | None = Field(default=None,max_length=2000)
    max_chars: int | None = Field(default=None,ge=5,le=300,strict=True)

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

class NetworkProvision(Payload):
    ssid:str=Field(min_length=1,max_length=32)
    password:SecretStr
    revision:int=Field(ge=0)
    via:Literal['ble','usb']='ble'

class NetworkMode(Payload):
    policy:Literal['auto_wifi_first','ble_only','wifi_only']
    power:Literal['auto','performance','eco']
    revision:int=Field(ge=0)

class NetworkAddress(Payload):
    address:str=Field(default='',max_length=15)

class WatchEnabled(Payload):
    enabled:bool


class TrafficEnabled(Payload):
    enabled: bool


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
    sound_target: Literal["pc", "watch"] | None = None
    speech: "Speech | None" = None


class Speech(Payload):
    speaker_id: int = Field(default=3, ge=3, le=102)
    cloud_voice: str = Field(default="Cherry", min_length=1, max_length=40)
    speed: float = Field(default=1.0, ge=0.75, le=1.5)


class Text(Generation):
    text: str = Field(min_length=1, max_length=300)
    watch_speech: bool = False


class AnswerText(Text):
    speech_pending: bool = False


class CostQuery(Generation):
    question: str = Field(min_length=1, max_length=1000)
    allow_ai: bool = False


class MonitorSettings(Payload):
    enabled: bool
    source: Literal['legacy', 'astra'] = 'legacy'
    mode: Literal['auto', 'specific'] = 'auto'
    task_id: str = Field(default='', max_length=28)
    target: Literal['desktop', 'watch', 'both'] = 'desktop'
    sound: bool = False
    sound_kind: Literal['speech', 'beep'] = 'speech'
    sound_target: Literal['pc', 'watch'] = 'pc'


class CodexSettings(Payload):
    enabled: bool = True
    mode: Literal['auto', 'specific'] = 'auto'
    thread_id: str = Field(default='', max_length=100, pattern=r'^[A-Za-z0-9_-]*$')
    target: Literal['desktop', 'watch', 'both'] = 'desktop'
    sound: bool = False
    sound_target: Literal['pc', 'watch'] = 'pc'
    threshold: int = Field(default=20, ge=1, le=99)
    bucket_id: str = Field(default='', max_length=80)
    ring_mode: Literal['hidden', 'visible', 'hover'] = 'hidden'
    drop_step: int = Field(default=2, ge=1, le=20)
    drop_animation: bool = True


class VoiceLibraryGenerate(Payload):
    item_id: str = Field(default='', max_length=40)
    force: bool = False


class State(Generation):
    state: Literal["idle", "listening", "speaking", "error"]


class Device(Payload):
    address: str = Field(min_length=1, max_length=100)


class Character(Payload):
    expression: str = Field(min_length=2, max_length=20, pattern=r"^[a-z0-9-]+$")
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


SENTINEL_DEFAULTS = {'source': 'legacy', 'enabled': True, 'mode': 'auto', 'task_id': '',
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
    # Each backend start enables observation; manual off lasts for this run.
    # Keep all saved task/output preferences and leave the saved file untouched.
    values['enabled'] = True
    return values


def owner(request):
    value = request.headers.get("x-companion-client", "")
    try:
        uuid.UUID(value)
    except ValueError as exc:
        raise VoiceError(401, "CLIENT_REQUIRED", "请从工作台连接会话") from exc
    return value


def create_app(config=None, controller=None, cost_client=None, astra_client=None):
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
    answer_store=AnswerStore(config.get('answer_state_path',ROOT/'answer.local.json'))
    control = controller or Controller(VoiceClient(url, config.get("request_timeout", 60)), Robot(),
        AnswerClient(DEEPSEEK_URL if answer_store.key else config.get("answer_base_url", ""),
            answer_store.model if answer_store.key else config.get("answer_model", ""),
            config.get("answer_api_key_env", "GORK_ANSWER_API_KEY"), config.get("request_timeout", 60),api_key=answer_store.key,
            system_prompt=answer_store.system_prompt,max_chars=answer_store.max_chars),
        config.get("answer_history_turns", 4))
    traffic_path = config.get('traffic_data_dir', None if controller is not None else
                              str(Path(os.environ.get('LOCALAPPDATA', str(ROOT))) / 'GorkRobot' / 'traffic'))
    traffic = TrafficMonitor(traffic_path)
    pc_volume = VoiceVolume(config.get('voice_volume_path', None if controller is not None else ROOT / 'voice-volume.local.json'))
    control.pc_voice_volume = pc_volume.value
    astra_cost = astra_client or CostClient('http://127.0.0.1:5189', expected_service='zhisuan-astra')
    monitor_sources = {'legacy': cost, 'astra': astra_cost}
    monitor_source = 'legacy'
    sentinel_config_lock = asyncio.Lock()
    monitor = TaskMonitor(cost, control)
    external_registry = ClientRegistry(config.get('external_clients_path'))
    external = ExternalNotifications(control, external_registry, config.get('external_receipts_path', ':memory:' if controller is not None else None))
    control.external_notifications = external
    codex = CodexMonitor(control,
        jsonl=JsonlSource(config.get('codex_jsonl_root')),
        hooks=HookSpool(config.get('codex_hook_queue', control.codex_spool)),
        rpc=QuotaRPC(config.get('codex_executable', 'codex')))
    motion_store = MotionStore(config.get('motion_state_path', ROOT / 'motion.local.json'))
    motion_library = MotionLibrary(config.get('motion_library_path', ROOT / 'motion-library.local.json'))
    control.motion_library=motion_library
    voice_library_lock = control.fixed_speech_lock
    control.task_monitor = monitor
    control.codex_monitor = codex
    sentinel_path = Path(config.get('sentinel_state_path', ROOT / 'sentinel.local.json'))
    sentinel_initial = _sentinel_preferences(sentinel_path)
    monitor_source = sentinel_initial.pop('source', 'legacy')
    monitor.cost = monitor_sources[monitor_source]
    codex_path = Path(config.get('codex_state_path', ROOT / 'codex-sentinel.local.json'))
    codex_initial = _codex_preferences(codex_path)

    @asynccontextmanager
    async def lifespan(app):
        control.robot.start()
        if controller is None and auto_connect_device:
            control.robot.start_auto_connect(config.get("device_address", ""))
        start_service()
        initial = dict(sentinel_initial)
        if external_registry.enabled(monitor_source):
            initial['enabled'] = False
        await monitor.configure(**initial)
        await codex.configure(codex_initial)
        external.start()
        await traffic.start()
        async def prewarm():
            while True:
                if (control.owner and control.owner==control.voice_owner and control.voice.session
                        and control.turn and control.routing.get('tts')=='cloud'
                        and control.routing.get('allow_text_upload') and control.auto_available()):
                    try:
                        await control.warm_fixed_speech(voice_library.PHRASES)
                    except VoiceError:
                        pass  # Manual generation remains available; no automatic cloud retries.
                    return
                await asyncio.sleep(2)
        warmup_task=asyncio.create_task(prewarm()) if config.get('prewarm_fixed_voice',False) is True else None
        try:
            yield
        finally:
            if warmup_task:
                warmup_task.cancel()
                await asyncio.gather(warmup_task,return_exceptions=True)
            await traffic.close()
            await external.close()
            await monitor.stop()
            await codex.stop()
            await hover_quota.rpc.close()
            await control.close()
            await cost.close()
            await astra_cost.close()
            if manager:
                await asyncio.to_thread(manager.close)
            if service_task:
                await service_task

    app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    @app.exception_handler(RequestValidationError)
    async def safe_validation(request,exc):
        return JSONResponse({'error':{'code':'INVALID_INPUT','message':'输入格式不正确，请检查字段；秘密输入不会回显'}},status_code=422)

    @app.get('/api/device/network')
    async def network_status(request:Request):
        control.authorize(owner(request))
        return control.robot.network.snapshot()

    @app.post('/api/device/network/provision')
    async def network_provision(payload:NetworkProvision,request:Request):
        control.authorize(owner(request))
        try:
            method=control.robot.network.provision_usb if payload.via=='usb' else control.robot.network.provision
            return await method(payload.ssid,payload.password.get_secret_value(),payload.revision)
        except (ValueError,ConnectionError) as exc:raise VoiceError(409,'NETWORK_SETUP',str(exc)) from exc

    @app.patch('/api/device/network')
    async def network_mode(payload:NetworkMode,request:Request):
        control.authorize(owner(request))
        try:return await control.robot.network.settings(payload.policy,payload.power,payload.revision)
        except (ValueError,ConnectionError) as exc:raise VoiceError(409,'NETWORK_SETTINGS',str(exc)) from exc

    @app.post('/api/device/network/connect')
    async def network_connect(payload:NetworkAddress,request:Request):
        control.authorize(owner(request))
        try:return await control.robot.network.manual_connect(payload.address)
        except ValueError as exc:raise VoiceError(422,'NETWORK_ADDRESS',str(exc)) from exc

    @app.delete('/api/device/network')
    async def network_forget(request:Request):
        control.authorize(owner(request))
        await control.robot.cancel_audio()
        return await control.robot.network.forget()

    @app.get('/api/watch/dialogue')
    async def watch_dialogue_status(request:Request):
        control.authorize(owner(request))
        return control.watch_dialogue.snapshot()

    @app.post('/api/watch/dialogue')
    async def watch_dialogue_enable(payload:WatchEnabled,request:Request):
        return await control.watch_dialogue.enable(owner(request),payload.enabled)

    @app.post('/api/watch/dialogue/shorten')
    async def watch_dialogue_shorten(request:Request):
        return await control.watch_dialogue.shorten(owner(request))
    app.state.motion_store = motion_store
    app.state.motion_library = motion_library
    app.state.control = control
    app.state.traffic = traffic
    app.state.cost = cost
    app.state.task_monitor = monitor
    app.state.codex_monitor = codex
    app.state.external_notifications = external
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
        if request.url.path == '/static/motion/index.html':
            response.headers['Content-Security-Policy'] = response.headers['Content-Security-Policy'].replace("frame-ancestors 'none'", "frame-ancestors 'self'")
        return response

    def external_source(request):
        source = external_registry.authenticate(request.headers.get('authorization', ''))
        if monitor.enabled and monitor_source == source:
            raise VoiceError(409, 'SOURCE_MODE_CONFLICT', '此来源正由任务哨兵轮询，请先关闭轮询')
        return source

    @app.get('/api/external/capabilities')
    async def external_capabilities():
        return {'protocol_version': '1.0', 'transport': 'loopback_http',
                'authentication': 'source_scoped_bearer', 'expressions': sorted(BLE_EXPRESSIONS),
                'custom_expressions_url': '/api/motion/expressions',
                'schema': Notification.model_json_schema(), 'idempotency_seconds': 86400,
                'max_queue': 32, 'max_queue_per_source': 8,
                'watch_text_chars': 24, 'watch_audio_seconds': 10}

    @app.get('/api/external/status')
    async def external_status(request: Request):
        source = external_source(request)
        return {'protocol_version': '1.0', 'source': source, 'enabled': True,
                'paused': external.paused, 'mode': 'push',
                'pending': sum(key[0] == source for key in external.tasks),
                'policy': next(item for item in external_registry.public_clients() if item['source']==source),
                'current_sound_target': control.output_target}

    @app.post('/api/external/notifications')
    async def external_notification(payload: Notification, request: Request):
        record, status = await external.accept(external_source(request), payload)
        return JSONResponse(record, status_code=status)

    @app.get('/api/external/notifications/{event_id}')
    async def external_receipt(event_id: str, request: Request):
        return external.read(external_source(request), event_id)

    @app.delete('/api/external/notifications/{event_id}')
    async def external_cancel(event_id: str, request: Request):
        return await external.cancel(external_source(request), event_id)

    @app.post('/api/external/cancel')
    async def external_cancel_task(payload: CancelTask, request: Request):
        return await external.cancel_task(external_source(request), payload.task_id, payload.attempt)

    @app.post('/api/external/heartbeat')
    async def external_heartbeat(payload: Heartbeat, request: Request):
        return await external.heartbeat(external_source(request), payload)

    @app.get('/api/traffic')
    async def traffic_snapshot(details: bool = False):
        return traffic.snapshot(details)

    @app.put('/api/traffic')
    async def traffic_configure(payload: TrafficEnabled, request: Request):
        control.renew_workspace(owner(request))
        try:
            return await traffic.configure(payload.enabled)
        except (OSError, ValueError):
            raise VoiceError(503, 'TRAFFIC_UNAVAILABLE', '流量监测暂时无法启动或保存，请稍后重试')

    @app.get('/api/voice/volume')
    async def get_voice_volume():
        return {'volume': control.pc_voice_volume}

    @app.put('/api/voice/volume')
    async def set_voice_volume(payload: PCVoiceVolume, request: Request):
        control.renew_workspace(owner(request))
        try:
            pc_volume.save(payload.volume)
        except OSError as error:
            raise VoiceError(503, 'VOICE_VOLUME_SAVE_FAILED', '语音音量暂时无法保存，请稍后重试') from error
        control.pc_voice_volume = pc_volume.value
        return {'volume': control.pc_voice_volume}

    @app.get('/api/external/protocol')
    async def external_protocol():
        return FileResponse(PROJECT_ROOT / '00-docs/接口/Gork机器人通用输出接口-v1.0.0-【codex】.md', media_type='text/markdown; charset=utf-8')

    @app.get('/api/external/overview')
    async def external_overview(request: Request):
        control.renew_workspace(owner(request))
        return {'clients': external_registry.public_clients(), 'paused': external.paused,
                'pending': len(external.tasks), 'current_sound_target': control.output_target,
                'current': {target: external.current(target) for target in ('desktop','watch')},
                'receipts': external.history(),
                'poll_source': monitor_source if monitor.enabled else None}

    @app.post('/api/external/clients')
    async def external_register(payload: RegisterClient, request: Request):
        control.renew_workspace(owner(request))
        async with sentinel_config_lock:
            if payload.enabled and monitor.enabled and monitor_source==payload.source:
                raise VoiceError(409, 'SOURCE_MODE_CONFLICT', '先关闭此来源的兼容轮询，再启用直接通知')
            return external_registry.save_client(payload.source, ClientPolicy(**payload.model_dump(exclude={'source'})), create=True)

    @app.put('/api/external/clients/{source}')
    async def external_policy(source: str, payload: ClientPolicy, request: Request):
        control.renew_workspace(owner(request))
        async with sentinel_config_lock:
            if payload.enabled and monitor.enabled and monitor_source==source:
                raise VoiceError(409, 'SOURCE_MODE_CONFLICT', '先关闭此来源的兼容轮询，再启用直接通知')
            result=external_registry.save_client(source,payload)
            await external.cancel_source(source)
            return result

    @app.post('/api/external/owner-cancel')
    async def external_owner_cancel(payload: dict, request: Request):
        control.renew_workspace(owner(request))
        if set(payload)!={'source','event_id'} or not all(isinstance(value,str) for value in payload.values()):
            raise VoiceError(422,'CANCEL_INVALID','请选择一条通知')
        return await external.cancel(payload['source'],payload['event_id'])

    @app.patch('/api/external/output')
    async def external_output(payload: dict, request: Request):
        control.renew_workspace(owner(request))
        if set(payload)!={'target'} or payload['target'] not in ('pc','watch'):
            raise VoiceError(422,'OUTPUT_INVALID','声音位置需为电脑或 Watch')
        control.output_target=payload['target']
        return {'target':control.output_target}

    @app.post('/api/external/pause')
    async def external_pause(request: Request):
        control.renew_workspace(owner(request))
        async with sentinel_config_lock:
            external_registry.set_notifications_paused(True)
            await external.stop()
        return {'paused': True}

    @app.post('/api/external/resume')
    async def external_resume(request: Request):
        control.renew_workspace(owner(request))
        async with sentinel_config_lock:
            external_registry.set_notifications_paused(False)
            external.paused = False
        return {'paused': False}

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
            "external_protocol": '1.0',
            "pid": os.getpid(), "launch": os.environ.get("GORK_LAUNCH_TOKEN", ""),
            "device_address": config.get("device_address", ""),
            "voice_url": url, "auto_connect_voice": auto_connect_voice,
            "watch_speech_sync": True,
            "answer_speech_continuity":True,
            "robot": control.robot.snapshot(),"watch_dialogue":control.watch_dialogue.snapshot() if control.watch_dialogue else {"enabled":False,"stage":"disabled"}}
        result["external_presentation"] = control.desktop_state()["character"] if external.current() and external.visual_available() else None
        result["answer"] = control.answer_capability()
        result['answer_expression']=control.answer_motion if control.phase=='generating' and control.answer_motion_generation==control.generation else None
        result['interaction_expression']=control.interaction_motion()
        result['speech_output']={'route':control.routing['tts'],
            'applied':{key:control.speech[key] for key in ('speaker_id','cloud_voice','speed') if control.speech and key in control.speech},
            'last':control.last_speech_output,
            'observation':getattr(control.voice,'tts_observation',None)}
        result['fixed_speech_cache']={'hits':control.fixed_speech_hits,'misses':control.fixed_speech_misses,
                                    'warmup':dict(control.fixed_speech_warmup)}
        result['answer_setup'] = answer_store.snapshot()
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

    @app.get('/api/motion/config')
    async def motion_config():
        try:
            return await asyncio.to_thread(motion_store.read)
        except (OSError, ValueError) as exc:
            raise VoiceError(503, 'MOTION_READ_FAILED', str(exc)) from exc

    @app.put('/api/motion/config')
    @app.post('/api/motion/config/recover')
    async def reject_global_motion_write():
        raise VoiceError(409, 'MOTION_DEFAULT_READ_ONLY', '默认表情不可改写，请保存为自定义表情')

    @app.get('/api/motion/expressions')
    async def custom_expressions():
        try:
            return await asyncio.to_thread(motion_library.read)
        except (OSError, ValueError) as exc:
            raise VoiceError(503, 'MOTION_LIBRARY_READ_FAILED', str(exc)) from exc

    @app.get('/api/motion/expressions/{item_id}')
    async def custom_expression(item_id: str):
        try:
            return await asyncio.to_thread(motion_library.get, item_id)
        except KeyError as exc:
            raise VoiceError(404, 'MOTION_EXPRESSION_MISSING', '自定义表情不存在') from exc
        except (OSError, ValueError) as exc:
            raise VoiceError(503, 'MOTION_LIBRARY_READ_FAILED', str(exc)) from exc

    async def write_custom_expression(request, item_id=None):
        data = bytearray()
        async for chunk in request.stream():
            data.extend(chunk)
            if len(data) > 24576:
                raise VoiceError(413, 'MOTION_TOO_LARGE', '表情请求不能超过 24 KiB')
        try:
            payload = json.loads(data)
            if type(payload) is not dict or set(payload) != {'name', 'scene', 'config', 'expected_revision'}:
                raise ValueError('表情保存字段无效')
            return await asyncio.to_thread(motion_library.save_expression, payload['name'], payload['scene'],
                                           payload['config'], payload['expected_revision'], item_id)
        except Conflict as exc:
            raise VoiceError(409, 'MOTION_CONFLICT', str(exc)) from exc
        except (ValueError, TypeError) as exc:
            raise VoiceError(422, 'MOTION_INVALID', str(exc)) from exc
        except OSError as exc:
            raise VoiceError(503, 'MOTION_WRITE_FAILED', '写入失败，最近有效表情库已保留') from exc

    @app.post('/api/motion/expressions')
    async def add_custom_expression(request: Request):
        return await write_custom_expression(request)

    @app.put('/api/motion/expressions/{item_id}')
    async def update_custom_expression(item_id: str, request: Request):
        return await write_custom_expression(request, item_id)

    @app.get('/api/motion/watch/{kind}')
    async def export_watch_motion(kind: Literal['json', 'header'], expression_id: str):
        from convert_gork_motion import convert, cpp
        record = await custom_expression(expression_id)
        try:
            mapped = convert(record['config'], record['revision'])
            data = cpp(mapped) if kind == 'header' else json.dumps(mapped, ensure_ascii=False, indent=2)
            name = 'motion_config.h' if kind == 'header' else 'gork-scenes.watch.json'
            return Response(data, media_type='text/plain; charset=utf-8',
                            headers={'Content-Disposition': f'attachment; filename="{name}"'})
        except (OSError, ValueError) as exc:
            raise VoiceError(503, 'MOTION_WATCH_EXPORT_FAILED', str(exc)) from exc

    cc_usage = CCSwitchUsage(config.get('ccswitch_db_path'))
    hover_quota = QuotaUsage(QuotaRPC(config.get('codex_executable', 'codex')), codex)

    @app.get("/api/desktop/quota-usage")
    async def desktop_quota_usage():
        return await hover_quota.get()

    @app.get("/api/desktop/token-usage")
    async def desktop_token_usage():
        return await cc_usage.get()

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

    def monitored_state():
        return {**monitor.state(), 'source': monitor_source}

    @app.get('/api/cost/sources')
    async def sentinel_sources():
        return {'service': 'gork-console', 'schema_version': 1, 'source': monitor_source,
                'sources': [{'id': 'legacy', 'name': '原版造价智算'}, {'id': 'astra', 'name': '智算 Astra'}]}

    @app.get('/api/cost/sentinel')
    async def sentinel_state():
        return monitored_state()

    @app.get('/api/cost/sentinel/projects')
    async def sentinel_projects(request: Request, source: Literal['legacy', 'astra'] = 'legacy', page: int = 1):
        who = owner(request)
        control.renew_workspace(who)
        if not 1 <= page <= 10000:
            raise VoiceError(422, 'COST_PAGE', '无效页码')
        result = await monitor_sources[source].projects(page)
        control.authorize(who)
        return result

    @app.get('/api/cost/sentinel/projects/{project_id}')
    async def sentinel_project(project_id: str, request: Request, source: Literal['legacy', 'astra'] = 'legacy'):
        who = owner(request)
        control.renew_workspace(who)
        result = await monitor_sources[source].project(project_id)
        control.authorize(who)
        return result

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
        try:
            profile=await control.fixed_speech_profile()
        except VoiceError:
            return {'voice':'','voice_label':'尚未应用云端音色','model':'','ready':0,'total':len(voice_library.PHRASES),
                    'items':[{'id':key,'group':group,'text':text,'ready':False} for key,group,text in voice_library.PHRASES]}
        result=await asyncio.to_thread(voice_library.catalogue_for,profile)
        result['warmup']=dict(control.fixed_speech_warmup)
        return result

    @app.get('/api/character/voice-library/{item_id}/preview')
    async def sentinel_voice_preview(item_id: str):
        item = voice_library.BY_ID.get(item_id)
        if not item:
            raise VoiceError(404, 'VOICE_LIBRARY_ITEM', '播报短句不存在')
        profile=await control.fixed_speech_profile()
        audio=await asyncio.to_thread(speech_cache.read,item[2],profile)
        if audio is None:
            raise VoiceError(404, 'VOICE_LIBRARY_MISSING', '该短句尚无可用的本地语音，请先生成')
        return Response(audio,media_type='audio/wav')

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
        entries = ([voice_library.BY_ID[payload.item_id]] if payload.item_id else voice_library.PHRASES)
        generated=await control.warm_fixed_speech(entries,force=payload.force)
        return {'generated':generated,'library':await sentinel_voice_library()}

    @app.put('/api/cost/sentinel')
    async def sentinel_settings(payload: MonitorSettings, request: Request):
        nonlocal monitor_source
        control.renew_workspace(owner(request))
        if payload.enabled and payload.mode == 'specific' and not MONITOR_TASK_ID.fullmatch(payload.task_id):
            raise VoiceError(422, 'COST_TASK_ID', '请选择有效的智算任务')
        settings = payload.model_dump()
        async with sentinel_config_lock:
            if payload.enabled and external_registry.enabled(payload.source):
                raise VoiceError(409, 'SOURCE_MODE_CONFLICT', '此来源已启用外部推送，请先停用推送后开启轮询')
            control.renew_workspace(owner(request))
            if payload.enabled and (payload.source == 'astra' or payload.source != monitor_source):
                # Validate identity/task before saving or replacing a working source.
                selected = monitor_sources[payload.source]
                await selected.health()
                if payload.mode == 'specific':
                    await selected.monitor_task(payload.task_id)
                control.renew_workspace(owner(request))
            try:
                await asyncio.to_thread(_save_sentinel_preferences, sentinel_path, settings)
            except OSError as exc:
                raise VoiceError(503, 'MONITOR_PREFERENCES', '任务哨兵设置无法保存，请检查本机目录权限') from exc
            selected_source = settings.pop('source')
            context_changed = (selected_source != monitor_source or payload.mode != monitor.mode
                               or (payload.mode == 'specific' and payload.task_id != monitor.task_id))
            if selected_source != monitor_source:
                await monitor.stop()
                monitor.cost = monitor_sources[selected_source]
                monitor_source = selected_source
            if context_changed:
                monitor.last_result = None
                monitor.history = []
            monitor.last_success_at = ''
            await monitor.configure(**settings)
            return monitored_state()

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
        result = await control.settings(owner(request), payload.generation, routing, payload.allow_answer_upload,
                                      payload.speech.model_dump() if payload.speech else None)
        if payload.sound_target is not None:
            control.output_target = payload.sound_target
        return result

    @app.get('/api/answer/config')
    async def answer_config():
        return answer_store.snapshot()

    @app.post('/api/answer/config')
    async def answer_config_save(payload: AnswerSetup, request: Request):
        async with control.lock:
            control.authorize(owner(request))
            if control.answer_tasks or control.pending or (control.watch_dialogue and control.watch_dialogue.owner) or control.robot.audio_snapshot().get('running'):
                raise VoiceError(409,'ANSWER_SETUP_BUSY','请先停止当前对话和设备音频，再保存 AI 配置')
            try:await asyncio.to_thread(answer_store.save,payload.api_key.get_secret_value(),payload.model,payload.system_prompt,payload.max_chars)
            except ValueError as exc:raise VoiceError(422,'ANSWER_SETUP_INVALID',str(exc)) from exc
            except Exception as exc:raise VoiceError(500,'ANSWER_SETUP_FAILED','AI 配置未保存，请检查本机凭据保护与文件权限') from exc
            previous=control.answer
            control.answer=AnswerClient(DEEPSEEK_URL,answer_store.model,api_key=answer_store.key,
                system_prompt=answer_store.system_prompt,max_chars=answer_store.max_chars)
            control.answer_history.clear()
            if previous:await previous.close()
        return {**answer_store.snapshot(),'capability':control.answer_capability()}

    @app.post("/api/answer")
    async def answer(payload: AnswerText, request: Request):
        if not payload.text.strip():
            raise VoiceError(422, "TEXT_EMPTY", "请输入要发送的文字")
        text=await control.ask(owner(request),payload.generation,payload.text,payload.watch_speech,speech_pending=payload.speech_pending)
        return {"text":text,"interaction_expression":control.interaction_motion()}

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
        return {"ok": True,"interaction_expression":control.interaction_motion()}

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
        entry = await custom_expression(payload.expression) if payload.expression.startswith('motion-') else None
        return await control.play_character(owner(request), payload.expression, payload.mode, payload.target, entry)

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
