import asyncio
import hashlib
import json
import multiprocessing
import secrets
import time
from collections import deque
from dataclasses import dataclass, field

from .engines import worker_main
from .cloud import CloudEngines, CloudError


class ServiceError(Exception):
    def __init__(self, status, code, message):
        self.status, self.code, self.message = status, code, message
        super().__init__(message)


@dataclass
class Job:
    request_id: str
    session_id: str
    turn_id: int
    kind: str
    fingerprint: str
    payload: dict = field(default_factory=dict)
    status: str = "queued"
    created: float = field(default_factory=time.monotonic)
    done: asyncio.Event = field(default_factory=asyncio.Event)
    value: dict = field(default_factory=dict)
    error: dict | None = None
    metrics: dict = field(default_factory=dict)
    mode: str = 'local'

    def public(self):
        return {"protocol_version": 1, "request_id": self.request_id, "session_id": self.session_id,
            "turn_id": self.turn_id, "generation": self.turn_id, "kind": self.kind, "status": self.status,
            "mode": self.mode, "provider": self.value.get("provider"), "metrics": self.metrics,
            "result": {k: v for k, v in self.value.get("result", {}).items() if k != "audio"}, "error": self.error}


class Broker:
    def __init__(self, config, worker_target=worker_main, cloud=None):
        self.config = config
        self.worker_target = worker_target
        self.queue = asyncio.Queue(maxsize=config.max_queue)
        self.jobs = {}
        self.session_id = None
        self.last_seen = 0.0
        self.turn = 0
        self.process = self.connection = self.task = None
        self.engines = {k: {"state": "loading"} for k in ("asr", "tts")}
        self.events = deque(maxlen=128)
        self.event_sequence = 0
        self.active_id = None
        self.cloud = cloud or CloudEngines(config)
        self.cloud_task = self.boot_task = None
        self.cloud_requests = 0
        self.session_cloud_requests = 0
        self.routing = self._default_routing()
        self.turn_routing = dict(self.routing)

    def _default_routing(self):
        return {'asr':self.config.asr_mode, 'tts':self.config.tts_mode,
                'allow_audio_upload':self.config.allow_audio_upload, 'allow_text_upload':self.config.allow_text_upload}

    def cloud_status(self):
        return {**self.cloud.status(), 'session_requests':self.session_cloud_requests,
                'process_requests':self.cloud_requests, 'session_request_limit':self.config.cloud_request_limit}

    def set_routing(self, session, routing):
        self.authorize(session)
        self.routing = dict(routing)
        # Revocation takes effect immediately even for already queued cloud jobs.
        for job in self.jobs.values():
            permission='allow_audio_upload' if job.kind=='asr' else 'allow_text_upload'
            if job.mode=='cloud' and not job.done.is_set() and not routing[permission]:
                self._cancel(job)
        return dict(self.routing)

    async def start(self):
        self.boot_task = asyncio.create_task(self._boot())
        self.task = asyncio.create_task(self._dispatch())

    def _kill_worker(self):
        if self.process:
            if self.process.is_alive():
                self.process.terminate()
            self.process.join(timeout=2)
            if self.process.is_alive():
                self.process.kill()
                self.process.join(timeout=2)
            self.process.close()
            self.process = None
        if self.connection:
            self.connection.close()
            self.connection = None

    async def close(self):
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        if self.boot_task:
            self.boot_task.cancel()
            try:
                await self.boot_task
            except asyncio.CancelledError:
                pass
        self._kill_worker()
        for job in self.jobs.values():
            self._cancel(job)

    async def _receive(self, timeout):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.connection.poll():
                return self.connection.recv()
            if not self.process.is_alive():
                raise RuntimeError("Inference worker exited")
            await asyncio.sleep(0.02)
        raise TimeoutError("Inference deadline exceeded")

    async def _boot(self):
        self._kill_worker()
        self.engines = {k: {"state": "loading"} for k in ("asr", "tts")}
        ctx = multiprocessing.get_context("spawn")
        self.connection, child = ctx.Pipe()
        self.process = ctx.Process(target=self.worker_target, args=(child, self.config), daemon=True)
        self.process.start()
        child.close()
        try:
            hello = await self._receive(120)
            self.engines = hello["status"]
        except Exception:
            self._kill_worker()
            self.engines = {k: {"state": "error", "message": "模型进程启动失败，请检查模型文件后重启服务"} for k in ("asr", "tts")}

    def _event(self, job):
        self.event_sequence += 1
        self.events.append({"sequence": self.event_sequence, "request_id": job.request_id,
            "session_id": job.session_id, "turn_id": job.turn_id, "generation": job.turn_id,
            "status": job.status, "kind": job.kind, "metrics": job.metrics, "error": job.error})

    async def _dispatch(self):
        while True:
            job = await self.queue.get()
            try:
                if job.done.is_set():
                    continue
                if job.mode == 'local' and self.engines[job.kind]["state"] != "ready":
                    job.status = "failed"
                    job.error = {"code": "ENGINE_UNAVAILABLE", "message": "本地模型尚未就绪", "http_status": 503}
                    job.done.set()
                    self._event(job)
                    continue
                self.active_id = job.request_id
                job.status = "running"
                job.metrics["queue_ms"] = round((time.monotonic() - job.created) * 1000, 2)
                self._event(job)
                timeout = self.config.asr_timeout if job.kind == "asr" else self.config.tts_timeout
                try:
                    if job.mode == 'cloud':
                        self._check_cloud(job.kind)
                        self.session_cloud_requests += 1
                        self.cloud_requests += 1
                        self.cloud_task = asyncio.create_task(self.cloud.run(job.kind, job.payload))
                        result = {'ok':True,'value':await self.cloud_task}
                    else:
                        self.connection.send({"kind": job.kind, "payload": job.payload})
                        result = await self._receive(timeout)
                    if not job.done.is_set():
                        if not result["ok"]:
                            raise ValueError("Model failed")
                        job.value = result["value"]
                        job.metrics.update(job.value["metrics"])
                        job.metrics["server_total_ms"] = round((time.monotonic() - job.created) * 1000, 2)
                        job.status = "completed"
                except asyncio.CancelledError:
                    if asyncio.current_task().cancelling() or not job.done.is_set():
                        raise
                except (CloudError, ServiceError) as exc:
                    if not job.done.is_set():
                        job.status = 'failed'
                        job.error = {'code':exc.code,'message':exc.message,'http_status':exc.status}
                except Exception as exc:
                    if not job.done.is_set():
                        job.status = "failed"
                        job.error = {"code": "ENGINE_TIMEOUT" if isinstance(exc, TimeoutError) else "ENGINE_FAILED",
                            "message": "本地推理超时，正在恢复模型" if isinstance(exc, TimeoutError) else "本地推理失败，请检查输入或重试",
                            "http_status": 504 if isinstance(exc, TimeoutError) else 503}
                        if job.mode == 'cloud':
                            job.error = {'code':'CLOUD_FAILED','message':'云端处理失败，本次未重试','http_status':502}
                        job.done.set()
                        self._event(job)
                    if job.mode == 'local':
                        await self._boot()
                finally:
                    job.payload = {}
                    if not job.done.is_set():
                        job.done.set()
                        self._event(job)
                    self.active_id = None
                    self.cloud_task = None
            finally:
                self.queue.task_done()

    def _prune(self):
        now = time.monotonic()
        for key, job in list(self.jobs.items()):
            if job.done.is_set() and now - job.created > 300:
                del self.jobs[key]
        if self.session_id and now - self.last_seen > 900:
            self.end_session(self.session_id)

    def authorize(self, session):
        self._prune()
        if not session or not self.session_id or not secrets.compare_digest(session, self.session_id):
            raise ServiceError(401, "SESSION_INVALID", "会话已失效，请重新连接")
        self.last_seen = time.monotonic()

    def new_session(self, replace=False):
        self._prune()
        if self.session_id and not replace:
            raise ServiceError(409, "SESSION_BUSY", "另一个页面正在使用语音服务，可点击接管会话")
        if self.session_id:
            self.end_session(self.session_id)
        self.session_id = secrets.token_urlsafe(32)
        self.routing = self._default_routing()
        self.turn_routing = dict(self.routing)
        self.session_cloud_requests = 0
        self.turn = 0
        self.last_seen = time.monotonic()
        return {"session_id": self.session_id, "turn_id": self.turn, "protocol_version": 1}

    def end_session(self, session):
        for job in self.jobs.values():
            if job.session_id == session:
                self._cancel(job)
                job.value = {}
        self.jobs.clear()
        self.session_id = None

    def next_turn(self, session):
        self.authorize(session)
        for job in self.jobs.values():
            if not job.done.is_set():
                self._cancel(job)
        self.turn += 1
        self.turn_routing = dict(self.routing)
        return {"turn_id": self.turn, "generation": self.turn}

    def _check_cloud(self, kind):
        permission = 'allow_audio_upload' if kind == 'asr' else 'allow_text_upload'
        if not self.turn_routing[permission] or not self.routing[permission]:
            raise ServiceError(403,'UPLOAD_PERMISSION_REQUIRED','本会话未允许上传该类内容')
        if not self.cloud.available():
            raise ServiceError(503,'CLOUD_NOT_CONFIGURED','尚未配置本模块的百炼 API Key；可切回本地继续使用')
        if self.session_cloud_requests >= self.config.cloud_request_limit:
            raise ServiceError(429,'CLOUD_SESSION_LIMIT','本会话云端请求已达上限，请检查用量后重新建立会话')

    def submit(self, session, turn, request_id, kind, payload):
        self.authorize(session)
        if turn != self.turn or turn < 1:
            raise ServiceError(409, "STALE_TURN", "该轮次已经过期")
        canonical = payload["audio"] if kind == "asr" else json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()
        mode = self.turn_routing[kind]
        fingerprint = hashlib.sha256((kind + mode).encode() + canonical).hexdigest()
        if request_id in self.jobs:
            existing = self.jobs[request_id]
            if existing.session_id != session or existing.turn_id != turn:
                raise ServiceError(409, "REQUEST_CONFLICT", "请求标识已用于其他轮次")
            if existing.status == "cancelled":
                return existing
            if existing.fingerprint != fingerprint:
                raise ServiceError(409, "REQUEST_CONFLICT", "相同请求标识不能使用不同输入")
            return existing
        if mode == 'cloud':
            self._check_cloud(kind)
        if mode == 'local' and self.engines[kind]["state"] != "ready":
            raise ServiceError(503, "ENGINE_UNAVAILABLE", "模型尚未就绪，请查看引擎状态")
        if self.queue.full():
            raise ServiceError(429, "QUEUE_FULL", "语音引擎繁忙，请稍候重试")
        # Keep up to 16 short-lived request results (including WAV) in memory.
        while len(self.jobs) >= 16:
            key = next((k for k, v in self.jobs.items() if v.done.is_set() and k != self.active_id), None)
            if key is None:
                raise ServiceError(429, "QUEUE_FULL", "待处理请求过多")
            del self.jobs[key]
        job = Job(request_id, session, turn, kind, fingerprint, payload, mode=mode)
        self.jobs[request_id] = job
        self.queue.put_nowait(job)
        self._event(job)
        return job

    def get(self, session, request_id):
        self.authorize(session)
        job = self.jobs.get(request_id)
        if not job or job.session_id != session:
            raise ServiceError(404, "NOT_FOUND", "请求不存在或已过期")
        return job

    def _cancel(self, job):
        if job.status == "cancelled":
            return
        job.status = "cancelled"
        if job.mode == 'cloud' and job.request_id == self.active_id and self.cloud_task:
            self.cloud_task.cancel()
        job.error = {"code": "CANCELLED", "message": "已停止本轮，迟到结果将丢弃", "http_status": 409}
        job.payload = {}
        job.value = {}
        job.done.set()
        self._event(job)

    def cancel(self, session, request_id, turn):
        self.authorize(session)
        job = self.jobs.get(request_id)
        if job:
            if job.session_id != session or job.turn_id != turn:
                raise ServiceError(409, "REQUEST_CONFLICT", "请求与轮次不匹配")
        else:
            if turn != self.turn:
                raise ServiceError(409, "STALE_TURN", "该轮次已过期")
            if len(self.jobs) >= 16:
                raise ServiceError(429, "QUEUE_FULL", "请求缓存已满")
            # A cancel may arrive before the upload; retain a tombstone.
            job = Job(request_id, session, turn, "unknown", "")
            self.jobs[request_id] = job
        self._cancel(job)
        return job.public()
