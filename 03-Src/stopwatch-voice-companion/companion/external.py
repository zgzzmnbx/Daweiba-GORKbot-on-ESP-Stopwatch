"""Versioned, source-scoped local notification ingress; never a workbench takeover."""
import asyncio
import contextlib
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import secrets
import sqlite3
import time
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .control import BLE_EXPRESSIONS
from .motion import watch_token
from .task_monitor import _pc_dynamic_speech
from .speech_cache import cacheable_text
from .voice import VoiceError

ID = r'^[A-Za-z0-9_.:-]{1,100}$'
ROOT = Path(__file__).resolve().parents[1]


class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)


class ExternalSpeech(Strict):
    text: str = Field(min_length=1, max_length=300)
    target: Literal['current', 'pc', 'watch'] = 'current'
    mode: Literal['auto', 'tts', 'cached'] = 'auto'


class Notification(Strict):
    protocol_version: Literal['1.0']
    source: str = Field(pattern=r'^[a-z][a-z0-9_-]{0,39}$')
    event_id: str = Field(pattern=ID)
    task_id: str = Field(min_length=1, max_length=100)
    attempt: str = Field(min_length=1, max_length=100)
    stage: str = Field(pattern=r'^[A-Za-z0-9_-]{1,60}$')
    sequence: int = Field(ge=1)
    kind: Literal['state', 'notice'] = 'notice'
    occurred_at: str = Field(min_length=10, max_length=40)
    expression: str = Field(default='idle', pattern=r'^[a-z0-9-]{2,60}$')
    expression_mode: Literal['once', 'loop'] = 'once'
    text: str = Field(default='', max_length=300)
    duration_ms: int = Field(default=8000, ge=500, le=60000)
    display_target: Literal['desktop', 'watch', 'both', 'none'] = 'both'
    speech: ExternalSpeech | None = None
    priority: int = Field(default=2, ge=0, le=5)
    ttl_ms: int = Field(default=30000, ge=1000, le=90000)
    lease_ms: int = Field(default=30000, ge=1000, le=90000)
    supersedes: list[str] = Field(default_factory=list, max_length=20)
    amount_summary: dict | None = None

    @model_validator(mode='after')
    def validate_content(self):
        import re
        date = datetime.fromisoformat(self.occurred_at.replace('Z', '+00:00'))
        if date.tzinfo is None:
            raise ValueError('occurred_at requires timezone')
        if self.expression not in BLE_EXPRESSIONS and not self.expression.startswith('motion-'):
            raise ValueError('expression is not in the catalogue')
        if self.expression == 'happy-work' and self.display_target in ('desktop', 'both'):
            raise ValueError('happy-work is Watch only')
        if any(not re.fullmatch(ID, item) for item in self.supersedes) or self.event_id in self.supersedes:
            raise ValueError('invalid supersedes')
        if self.speech and not self.speech.text.strip():
            raise ValueError('speech text cannot be blank')
        if self.display_target == 'none' and self.speech is None:
            raise ValueError('notification has no output')
        if self.amount_summary is not None:
            from .cost import monitor_amount
            value = monitor_amount(self.amount_summary, self.attempt)
            if value is None:
                raise ValueError('invalid amount_summary')
            self.amount_summary = value
        return self


class CancelTask(Strict):
    task_id: str = Field(min_length=1, max_length=100)
    attempt: str = Field(min_length=1, max_length=100)


class Heartbeat(Strict):
    event_id: str = Field(pattern=ID)
    task_id: str = Field(min_length=1, max_length=100)
    attempt: str = Field(min_length=1, max_length=100)


class ClientPolicy(Strict):
    label: str = Field(min_length=1, max_length=60)
    enabled: bool = False
    display_targets: list[Literal['desktop', 'watch']] = Field(default_factory=lambda: ['desktop', 'watch'], max_length=2)
    speech_targets: list[Literal['pc', 'watch']] = Field(default_factory=list, max_length=2)
    max_priority: int = Field(default=2, ge=0, le=5)


class RegisterClient(ClientPolicy):
    source: str = Field(pattern=r'^[a-z][a-z0-9_-]{0,39}$')


class ClientRegistry:
    def __init__(self, path=None):
        self.path = Path(path or ROOT / 'external-clients.local.json')

    def clients(self):
        try:
            data = json.loads(self.path.read_text(encoding='utf-8'))
            return {key:value for key,value in data['clients'].items() if isinstance(value,dict)} if isinstance(data.get('clients'), dict) else {}
        except (OSError, ValueError, TypeError, KeyError):
            return {}  # unreadable configuration never grants access

    def enabled(self, source):
        return self.clients().get(source, {}).get('enabled') is True

    def public_clients(self):
        return [{'source': source, **{k: v for k, v in value.items() if k in ('label','enabled','display_targets','speech_targets','max_priority')}}
                for source, value in self.clients().items()]

    def save_client(self, source, policy, *, create=False):
        from .external_setup import write_private
        clients = self.clients()
        if create and source in clients:
            raise VoiceError(409, 'EXTERNAL_CLIENT_EXISTS', '该程序已经登记')
        if not create and source not in clients:
            raise VoiceError(404, 'EXTERNAL_CLIENT_MISSING', '程序未登记')
        token = secrets.token_urlsafe(32) if create else None
        clients[source] = {**policy.model_dump(), 'token_sha256': hashlib.sha256(token.encode()).hexdigest()
                           if token else clients[source]['token_sha256']}
        write_private(self.path, {'clients': clients})
        result = {'source': source, **policy.model_dump()}
        if token:
            result['token'] = token  # one-time local owner response; never GET/list/log
        return result

    def authenticate(self, authorization):
        if not authorization.startswith('Bearer ') or len(authorization) > 200:
            raise VoiceError(401, 'EXTERNAL_AUTH_REQUIRED', '外部调用需独立 Bearer 令牌')
        digest = hashlib.sha256(authorization[7:].encode()).hexdigest()
        for source, client in self.clients().items():
            if isinstance(client, dict) and secrets.compare_digest(str(client.get('token_sha256', '')), digest):
                if client.get('enabled') is not True:
                    raise VoiceError(403, 'EXTERNAL_CLIENT_DISABLED', '此来源的外部通知尚未启用')
                return source
        raise VoiceError(401, 'EXTERNAL_AUTH_REQUIRED', '外部调用令牌无效')


class ExternalNotifications:
    """Separate visual leases from the shared, non-overlapping audio dispatch lane."""
    def __init__(self, control, registry, path=None):
        self.control, self.registry = control, registry
        self.path = Path(path or ROOT / 'external-notifications.local.sqlite3')
        self.db = None
        self.tasks, self.leases = {}, {}
        self.accept_lock = asyncio.Lock()
        self.maintenance = None
        self.pruned_at = 0
        self.watch_key = None
        self.watch_generation = None
        self.watch_identity = None
        self.audio_key = None
        self.paused = False

    def start(self):
        self.database()
        self.maintenance = asyncio.create_task(self.maintain())

    def database(self):
        if self.db is None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.db = sqlite3.connect(self.path)
            self.db.execute('CREATE TABLE IF NOT EXISTS notices (source TEXT, event_id TEXT, fingerprint TEXT, record TEXT, created REAL, PRIMARY KEY(source,event_id))')
            self.db.execute('CREATE TABLE IF NOT EXISTS latest (source TEXT, task_id TEXT, sequence INTEGER, event_id TEXT, PRIMARY KEY(source,task_id))')
            self.db.execute('CREATE TABLE IF NOT EXISTS cancelled (source TEXT, task_id TEXT, attempt TEXT, expires REAL, PRIMARY KEY(source,task_id,attempt))')
            for source, event_id, raw in self.db.execute('SELECT source,event_id,record FROM notices').fetchall():
                record = json.loads(raw)
                if record['status'] in ('queued', 'dispatching', 'active') or (record['status']=='partial' and record['request']['kind']=='state'):
                    record['status'] = 'interrupted'
                    self.db.execute('UPDATE notices SET record=? WHERE source=? AND event_id=?', (json.dumps(record, ensure_ascii=False), source, event_id))
            self.db.commit()
        return self.db

    def read(self, source, event_id):
        row = self.database().execute('SELECT record FROM notices WHERE source=? AND event_id=?', (source, event_id)).fetchone()
        if row is None:
            raise VoiceError(404, 'EXTERNAL_RECEIPT_NOT_FOUND', '此来源没有该回执')
        return json.loads(row[0])

    def save(self, record):
        self.database().execute('UPDATE notices SET record=? WHERE source=? AND event_id=?', (json.dumps(record, ensure_ascii=False), record['source'], record['event_id']))
        self.db.commit()

    def history(self, source=None, limit=30):
        sql = 'SELECT record FROM notices'
        params = ()
        if source is not None:
            sql += ' WHERE source=?'; params = (source,)
        rows = self.database().execute(sql+' ORDER BY created DESC LIMIT ?', (*params, limit)).fetchall()
        return [json.loads(row[0]) for row in rows]

    def visual_available(self):
        return (self.control.phase not in ('listening','processing','generating','speaking')
                and self.control.manual_until <= time.monotonic()
                and (self.audio_key is not None or self.control.auto_available()))

    def current(self, target='desktop'):
        now = time.monotonic()
        candidates = [lease for lease in self.leases.values() if lease['until'] > now
                      and self.registry.enabled(lease['source']) and not self.paused
                      and lease['generation'] == self.control.generation
                      and lease['request']['display_target'] in (target, 'both')]
        if not candidates:
            return None
        lease = max(candidates, key=lambda value: (value['request']['priority'], value['created']))
        data = lease['request']
        return {'source': 'external:'+lease['source'], 'expression': data['expression'], 'bubble': data['text'],
                'mode': data['expression_mode'], 'custom_motion': lease['custom'],
                'revision': lease['revision'], 'priority': data['priority'], 'key': lease['key'],
                'delivery': lease['delivery'].get(target,'not_requested')}

    def blocking_notice(self, exclude_source):
        if not self.visual_available():
            return None
        values=[lease for key,lease in self.leases.items() if lease['until']>time.monotonic()
                and lease['request']['kind']=='notice' and lease['request']['display_target']!='none' and self.registry.enabled(key[0])
                and 'external:'+key[0]+':'+key[1] != exclude_source]
        return max(values,key=lambda item:item['request']['priority'])['request'] if values else None

    def speech_target(self, payload):
        if payload.speech is None:
            return None
        target = payload.speech.target
        return self.control.output_target if target == 'current' else target

    def policy_check(self, source, payload):
        policy = self.registry.clients().get(source, {})
        if payload.priority > policy.get('max_priority', 2):
            raise VoiceError(403, 'EXTERNAL_PRIORITY_DENIED', '超过此程序获准的最高优先级')
        targets = ['desktop','watch'] if payload.display_target == 'both' else [] if payload.display_target == 'none' else [payload.display_target]
        if any(target not in policy.get('display_targets', []) for target in targets):
            raise VoiceError(403, 'EXTERNAL_OUTPUT_DENIED', '显示位置不在此程序的授权范围')
        target = self.speech_target(payload)
        if target and target not in policy.get('speech_targets', []):
            raise VoiceError(403, 'EXTERNAL_OUTPUT_DENIED', '声音位置不在此程序的授权范围')
        return target

    def _put_lease(self, record, payload, custom):
        key = (record['source'], record['event_id'])
        if key in self.leases or record.get('visual_started'):
            return
        record['visual_started'] = True
        if payload.display_target in ('desktop','both'):record['delivery']['desktop']='displayed'
        self.save(record)
        seconds = (payload.lease_ms if payload.kind == 'state' else payload.duration_ms) / 1000
        self.leases[key] = {'key': key, 'source': record['source'], 'request': payload.model_dump(),
                            'custom': custom, 'delivery':record['delivery'], 'until': time.monotonic()+seconds,
                            'generation': self.control.generation, 'created': time.time(),
                            'revision': int(time.time()*1000000)}

    async def accept(self, source, payload):
        async with self.accept_lock:
            return await self._accept(source,payload)

    async def _accept(self, source, payload):
        if payload.source != source:
            raise VoiceError(403, 'EXTERNAL_SOURCE_MISMATCH', '令牌不属于此来源')
        data = payload.model_dump()
        fingerprint = hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        db = self.database()
        row = db.execute('SELECT fingerprint,record FROM notices WHERE source=? AND event_id=?', (source, payload.event_id)).fetchone()
        if row:
            if row[0] != fingerprint:
                raise VoiceError(409, 'EXTERNAL_EVENT_CONFLICT', '相同 event_id 的内容不可修改')
            return {**json.loads(row[1]), 'duplicate': True}, 200
        if self.paused:
            raise VoiceError(409, 'EXTERNAL_PAUSED', '停止全部已暂停外部通知，需在Gork恢复')
        self.policy_check(source, payload)
        now = time.time()
        tombstone = db.execute('SELECT expires FROM cancelled WHERE source=? AND task_id=? AND attempt=?', (source,payload.task_id,payload.attempt)).fetchone()
        if tombstone and tombstone[0] > now:
            raise VoiceError(410, 'EXTERNAL_TASK_CANCELLED', '此轮次已取消，拒绝晚到通知')
        age = now - datetime.fromisoformat(payload.occurred_at.replace('Z', '+00:00')).timestamp()
        if age < -30 or age*1000 >= payload.ttl_ms:
            raise VoiceError(410, 'EXTERNAL_EVENT_EXPIRED', '事件已过期或来源时钟超前')
        last = db.execute('SELECT sequence,event_id FROM latest WHERE source=? AND task_id=?', (source,payload.task_id)).fetchone()
        if last and payload.sequence <= last[0]:
            raise VoiceError(409, 'EXTERNAL_EVENT_SUPERSEDED', '旧阶段序列已被更新阶段替代')
        if len(self.tasks) >= 32 or sum(key[0] == source for key in self.tasks) >= 8:
            raise VoiceError(429, 'EXTERNAL_QUEUE_FULL', '通知队列已满，请稍后重试')
        custom = None
        if payload.expression.startswith('motion-'):
            try:
                custom = self.control.motion_library.get(payload.expression)
            except (KeyError, OSError, ValueError, AttributeError):
                raise VoiceError(422, 'EXTERNAL_EXPRESSION_MISSING', '自定义表情不存在')
        db.execute('DELETE FROM notices WHERE created<?', (now-86400,))
        db.execute('DELETE FROM cancelled WHERE expires<?', (now,))
        if db.execute('SELECT COUNT(*) FROM notices').fetchone()[0] >= 1000:
            raise VoiceError(429, 'EXTERNAL_RECEIPTS_FULL', '当天回执容量已满')
        record = {'protocol_version': '1.0', 'source': source, 'event_id': payload.event_id,
                  'task_id': payload.task_id, 'attempt': payload.attempt, 'stage': payload.stage,
                  'status': 'queued', 'duplicate': False, 'accepted_at': datetime.now(timezone.utc).isoformat(),
                  'receipt_url': '/api/external/notifications/'+payload.event_id,
                  'delivery': {'desktop': 'not_requested', 'watch': 'not_requested', 'speech': 'not_requested'},
                  'request': data}
        db.execute('INSERT INTO notices VALUES (?,?,?,?,?)', (source,payload.event_id,fingerprint,json.dumps(record,ensure_ascii=False),now))
        db.execute('INSERT OR REPLACE INTO latest VALUES (?,?,?,?)', (source,payload.task_id,payload.sequence,payload.event_id))
        db.commit()
        # Never interrupt an already-started utterance merely because a new phase arrived.
        for key in list(set(self.tasks) | set(self.leases)):
            old = self.read(*key)
            if key[0] == source and (old['task_id'] == payload.task_id or key[1] in payload.supersedes):
                if old['status'] == 'queued':
                    await self.cancel(*key)
                self.leases.pop(key, None)
                if old['status'] == 'active':
                    old['status'] = 'superseded'; self.save(old)
        if (payload.priority >= 4 or payload.kind == 'state') and self.visual_available():
            self._put_lease(record,payload,custom)  # immediate visual alert, speech still queued
        key = (source,payload.event_id)
        self.tasks[key] = asyncio.create_task(self.run(record,payload,custom,max(.001,payload.ttl_ms/1000-max(0,age))))
        return record, 202

    async def heartbeat(self, source, payload):
        key = (source,payload.event_id)
        record = self.read(*key)
        if record['task_id'] != payload.task_id or record['attempt'] != payload.attempt or record['request']['kind'] != 'state':
            raise VoiceError(409, 'EXTERNAL_STATE_MISMATCH', '报活须对应同一条状态及轮次')
        lease = self.leases.get(key)
        if not lease or lease['until'] <= time.monotonic() or self.paused or lease['generation'] != self.control.generation or record['status'] not in ('active','dispatching','partial'):
            raise VoiceError(409, 'EXTERNAL_STATE_NOT_ACTIVE', '状态未生效或已失效，报活不会复活旧状态')
        lease['until'] = time.monotonic()+record['request']['lease_ms']/1000
        return {'event_id': payload.event_id, 'renewed': True, 'lease_ms': record['request']['lease_ms']}

    async def cancel(self, source, event_id):
        record = self.read(source,event_id)
        key = (source,event_id)
        had_lease=key in self.leases
        self.leases.pop(key,None)
        task = self.tasks.get(key)
        if task or had_lease or record['status'] == 'active':
            record['status'] = 'cancelled'; self.save(record)
        if task:
            if self.audio_key == key:
                self.control.stop_auto_tone()
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
            if self.tasks.get(key) is task:self.tasks.pop(key,None)
        return self.read(*key)

    async def cancel_task(self, source, task_id, attempt):
        self.database().execute('INSERT OR REPLACE INTO cancelled VALUES (?,?,?,?)', (source,task_id,attempt,time.time()+86400))
        self.db.commit()
        result=[]
        for key in list(set(self.tasks)|set(self.leases)):
            record=self.read(*key)
            if key[0]==source and record['task_id']==task_id and record['attempt']==attempt:
                result.append((await self.cancel(*key))['event_id'])
        return {'cancelled':result, 'tombstone_seconds':86400}

    async def cancel_source(self, source):
        for key in list(set(self.tasks)|set(self.leases)):
            if key[0]==source:
                await self.cancel(*key)

    def manual_started(self):
        for key in list(self.leases):
            record=self.read(*key)
            if record['status'] in ('active','partial'):
                record['status']='cancelled';self.save(record)
        self.leases.clear()
        self.watch_key=None
        active=[task for key,task in list(self.tasks.items()) if self.read(*key)['status']=='dispatching']
        if self.audio_key is not None:
            self.control.stop_auto_tone()
        for task in active:
            task.cancel()

    async def yield_to_manual(self):
        owns_watch=self.watch_key is not None and self._device_identity()==self.watch_identity
        running=[task for key,task in list(self.tasks.items()) if self.read(*key)['status']=='dispatching']
        self.manual_started()
        if running:
            await asyncio.gather(*running,return_exceptions=True)
        if owns_watch:
            with contextlib.suppress(Exception):
                await self.control.robot.clear_bubble()

    async def stop(self):
        self.paused=True
        for key in list(set(self.tasks)|set(self.leases)):
            await self.cancel(*key)

    async def close(self):
        await self.stop()
        if self.maintenance:
            self.maintenance.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self.maintenance
            self.maintenance=None
        if self.db:
            self.db.close();self.db=None

    def _device_identity(self):
        robot=self.control.robot
        try:
            client=robot.device_client()
            return (client,getattr(client,'boot',None),getattr(client,'session',None),getattr(robot,'operation_epoch',None))
        except Exception:
            return None

    async def maintain(self):
        try:
            while True:
                if time.monotonic()-self.pruned_at>=60:
                    self.database().execute('DELETE FROM notices WHERE created<?',(time.time()-86400,))
                    self.db.execute('DELETE FROM cancelled WHERE expires<?',(time.time(),))
                    self.db.commit();self.pruned_at=time.monotonic()
                disabled={key[0] for key in list(self.tasks) if not self.registry.enabled(key[0])}
                for source in disabled:
                    await self.cancel_source(source)
                for key,lease in list(self.leases.items()):
                    if lease['until']<=time.monotonic() or not self.registry.enabled(key[0]) or self.paused or lease['generation']!=self.control.generation:
                        self.leases.pop(key,None)
                        record=self.read(*key)
                        if record['status'] in ('active','partial'):
                            record['status']='expired';self.save(record)
                # Only restore a Watch display that this lane still owns on the same link.
                if self.watch_key and self.control.auto_available() and not self.control.notifications.active:
                    visible=self.current('watch')
                    next_key=visible['key'] if visible else None
                    if next_key!=self.watch_key:
                        guard=lambda: self.control.auto_available() and self.control.generation==self.watch_generation and self._device_identity()==self.watch_identity
                        if guard():
                            try:
                                command='idle';text=''
                                if visible:
                                    from .robot import short_bubble
                                    command=watch_token(visible['custom_motion']) if visible['custom_motion'] else visible['expression']
                                    if visible['mode']=='loop':command='loop '+command
                                    text=short_bubble(visible['bubble'])
                                result=await self.control.robot.auto_notify(command,text,guard)
                                if result!='accepted':next_key=None
                            except Exception:
                                next_key=None
                        else:
                            next_key=None
                        self.watch_key=next_key
                await asyncio.sleep(.1)
        except asyncio.CancelledError:
            raise

    async def run(self, record, payload, custom, ttl):
        key=(record['source'],record['event_id']);generation=None
        deadline=time.monotonic()+ttl
        def valid():
            task=self.tasks.get(key)
            return (task is not None and not task.cancelling() and not self.paused
                    and self.registry.enabled(key[0]) and record['status']!='cancelled'
                    and (generation is None or (self.control.generation==generation
                         and self.control.phase not in ('listening','processing','generating','speaking')
                         and self.control.manual_until<=time.monotonic())))
        async def output():
            nonlocal generation
            generation=self.control.generation
            speech_target=self.policy_check(key[0],payload)  # recheck current routing and live permissions at dispatch
            record['status']='dispatching';self.save(record)
            self._put_lease(record,payload,custom)
            command=watch_token(custom) if custom else payload.expression
            if payload.expression_mode=='loop':command='loop '+command
            from .robot import short_bubble
            text=short_bubble(payload.text)
            if payload.display_target in ('desktop','both'):
                record['delivery']['desktop']='displayed'
            if payload.display_target in ('watch','both'):
                try:
                    record['delivery']['watch']=await self.control.robot.auto_notify(command,text,valid)
                    if record['delivery']['watch']=='accepted':
                        self.watch_key=key;self.watch_generation=generation;self.watch_identity=self._device_identity()
                except Exception:
                    record['delivery']['watch']='failed'
            if payload.speech and valid():
                self.audio_key=key
                try:
                    speech=payload.speech;audio=None
                    reusable=speech.mode!='tts' and cacheable_text(speech.text)
                    if reusable and self.control.routing.get('tts')=='cloud':
                        audio=await self.control.fixed_speech(speech.text,valid,cached_only=speech.mode=='cached')
                    elif reusable and speech.mode=='cached':
                        raise VoiceError(409,'CACHE_VOICE_MISMATCH','缓存需与当前已应用的云端音色一致')
                    else:
                        audio=await self.control.synthesize_auto_speech(speech.text,valid)
                    if valid():
                        if speech_target=='pc':
                            record['delivery']['speech']=await asyncio.to_thread(_pc_dynamic_speech,audio,valid)
                        else:
                            record['delivery']['speech']=await self.control.robot.auto_speech(audio,text if payload.display_target in ('watch','both') else None,valid,command if payload.display_target in ('watch','both') else None)
                except VoiceError as exc:record['delivery']['speech']=exc.code.lower()
                except Exception:record['delivery']['speech']='failed'
                finally:
                    if self.audio_key==key:self.audio_key=None
            if not valid():
                record['status']='cancelled';self.leases.pop(key,None)
            else:
                successes={'displayed','accepted','completed_by_os','device_playback_completed'}
                values=[v for v in record['delivery'].values() if v!='not_requested']
                good=sum(v in successes for v in values)
                record['status']='active' if payload.kind=='state' and key in self.leases else 'completed'
                if good!=len(values):record['status']='partial' if good else 'failed'
                if record['status']=='failed':self.leases.pop(key,None)
            self.save(record)
        try:
            done=await self.control.notifications.dispatch(source='external:'+key[0]+':'+key[1],priority=payload.priority,valid=valid,action=output,ttl=ttl)
            if not done and record['status']=='queued':
                record['status']='expired' if time.monotonic()>=deadline else 'cancelled'
                self.leases.pop(key,None);self.save(record)
        except asyncio.CancelledError:
            record['status']='cancelled';self.leases.pop(key,None);self.save(record)
            raise
        except VoiceError as exc:
            record['status']='failed';record['error']=exc.code;self.leases.pop(key,None);self.save(record)
        except Exception:
            record['status']='failed';self.leases.pop(key,None);self.save(record)
        finally:
            self.tasks.pop(key,None)
