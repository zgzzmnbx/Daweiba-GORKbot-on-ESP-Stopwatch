"""Codex task and quota sentinel; no Codex task control methods."""
import asyncio
from datetime import datetime, timezone
import math
import time

from .codex_source import HookSpool, JsonlSource, QuotaRPC


MESSAGES = {
    'waiting_approval': ('需要回到 Codex 确认。', 'curious', 4),
    'waiting_input': ('需要补充信息。', 'curious', 4),
    'failed': ('本轮失败，请查看 Codex。', 'confused', 3),
    'turn_completed': ('本轮已结束，请查看结果。', 'happy', 2),
    'interrupted': ('本轮已中断，请查看 Codex。', 'idle', 2),
    'quota_low': ('Codex 额度较低，请查看详情。', 'curious', 1),
}


def _event_epoch(value, fallback=0.0):
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        return parsed.timestamp() if parsed.tzinfo else fallback
    except (TypeError, ValueError, AttributeError):
        return fallback


def quota_window(raw, index):
    if not isinstance(raw, dict):
        return None
    used = raw.get('usedPercent')
    if isinstance(used, bool) or not isinstance(used, (float, int)) or not math.isfinite(used):
        remaining = None
    else:
        remaining = round(max(0, min(100, 100 - used)), 1)
    duration = raw.get('windowDurationMins')
    duration = duration if isinstance(duration, int) and duration > 0 else None
    if duration and duration % 1440 == 0:
        name = f'{duration // 1440} 天（{duration} 分钟）'
    elif duration and duration % 60 == 0:
        name = f'{duration // 60} 小时（{duration} 分钟）'
    else:
        name = f'{duration} 分钟' if duration else f'窗口 {index}'
    reset = raw.get('resetsAt')
    reset = reset if isinstance(reset, (int, float)) and math.isfinite(reset) and reset > 0 else None
    return {'name': name,
            'duration_minutes': duration, 'remaining_percent': remaining, 'resets_at': reset}


def quota_snapshot(result):
    if not isinstance(result, dict):
        return {'status': 'unsupported', 'buckets': {}}
    entries = result.get('rateLimitsByLimitId')
    if not isinstance(entries, dict) or not entries:
        entries = {'default': result.get('rateLimits')} if result.get('rateLimits') else {}
    buckets = {}
    for key, value in entries.items():
        if not isinstance(key, str) or not isinstance(value, dict) or len(key) > 80:
            continue
        windows = [quota_window(value.get(name), i) for i, name in enumerate(('primary', 'secondary'), 1)]
        buckets[key] = {'name': value.get('limitName') if isinstance(value.get('limitName'), str) else key,
                        'windows': [item for item in windows if item]}
    return {'status': 'available' if buckets else 'no_windows', 'buckets': buckets}


class CodexMonitor:
    def __init__(self, control, *, jsonl=None, hooks=None, rpc=None):
        self.control = control
        self.jsonl = jsonl or JsonlSource()
        self.hooks = hooks or HookSpool(control.codex_spool)
        self.rpc = rpc or QuotaRPC()
        self.enabled = False
        self.epoch = 0
        self.worker = None
        self.quota_task = None
        self.mode = 'auto'
        self.thread_id = ''
        self.target = 'desktop'
        self.sound = False
        self.sound_target = 'pc'
        self.threshold = 20
        self.bucket_id = ''
        self.ring_mode = 'hidden'
        self.threads = {}
        self.focus = ''
        self.history = []
        self.seen = set()
        self.task_status = 'disabled'
        self.quota_status = 'disabled'
        self.quota = {'status': 'unknown', 'buckets': {}}
        self.quota_at = 0.0
        self.quota_error = ''
        self.quota_next = 0.0
        self.quota_failures = 0
        self.low_armed = {}
        self.revision = 0
        self.alerts = set()
        self.refresh_event = asyncio.Event()
        self.quota_busy = False
        self.quota_last_request = 0.0
        self.watch_started_for = None
        self.accept_after = 0.0

    def configure_values(self, values):
        for key in ('mode', 'thread_id', 'target', 'sound', 'sound_target', 'threshold', 'bucket_id', 'ring_mode'):
            setattr(self, key, values[key])

    async def configure(self, values):
        if (self.enabled and values['enabled'] and values['mode'] == self.mode
                and values['thread_id'] == self.thread_id):
            previous_limit = (self.threshold, self.bucket_id)
            self.configure_values(values)
            if previous_limit != (self.threshold, self.bucket_id):
                self.low_armed.clear()
            return self.state()
        self.epoch += 1
        self.enabled = False
        for worker in (self.worker, self.quota_task):
            if worker:
                worker.cancel()
        for alert in tuple(self.alerts):
            alert.cancel()
        await self.rpc.close()
        for worker in (self.worker, self.quota_task):
            if worker:
                try: await worker
                except asyncio.CancelledError: pass
        self.worker = self.quota_task = None
        if self.alerts:
            await asyncio.gather(*self.alerts, return_exceptions=True)
        self.alerts.clear()
        self.jsonl.reset_baseline()
        self.hooks.reset_baseline()
        self.hooks.disable()
        self.control.notifications.clear('codex')
        self.configure_values(values)
        self.threads.clear(); self.focus = ''; self.seen.clear(); self.low_armed.clear()
        self.watch_started_for = None
        self.task_status = self.quota_status = 'disabled'
        self.quota = {'status': 'unknown', 'buckets': {}}
        self.quota_at = 0
        self.quota_error = ''
        self.quota_next = 0
        self.quota_failures = 0
        self.quota_last_request = 0.0
        self.refresh_event.clear()
        if values['enabled']:
            self.accept_after = time.time()
            self.enabled = True
            self.task_status = 'connecting'
            self.quota_status = 'connecting'
            self.worker = asyncio.create_task(self._task_loop(self.epoch))
            self.quota_task = asyncio.create_task(self._quota_loop(self.epoch))
        return self.state()

    async def stop(self):
        await self.configure({'enabled': False, 'mode': self.mode, 'thread_id': self.thread_id,
                              'target': self.target, 'sound': self.sound,
                              'sound_target': self.sound_target, 'threshold': self.threshold,
                              'bucket_id': self.bucket_id, 'ring_mode': self.ring_mode})

    def state(self):
        now = time.time()
        quota = {'status': self.quota['status'], 'buckets': self.quota['buckets'],
                 'sampled_at': datetime.fromtimestamp(self.quota_at, timezone.utc).isoformat() if self.quota_at else '',
                 'stale': not self.quota_at or now - self.quota_at > 300}
        if self.quota_at:
            for bucket in quota['buckets'].values():
                if any(w['resets_at'] and w['resets_at'] <= now for w in bucket['windows']):
                    quota['stale'] = True
        focus = self.thread_id if self.mode == 'specific' else self.focus
        return {'enabled': self.enabled, 'mode': self.mode, 'thread_id': self.thread_id,
                'target': self.target, 'sound': self.sound, 'sound_target': self.sound_target,
                'threshold': self.threshold, 'bucket_id': self.bucket_id, 'ring_mode': self.ring_mode,
                'task_status': self.task_status, 'quota_status': self.quota_status,
                'quota_error': self.quota_error, 'quota': quota,
                'task_capabilities': {'jsonl': ['running', 'turn_completed'],
                                      'hook': ['running', 'waiting_approval', 'turn_completed', 'interrupted']},
                'focus': focus, 'current': self.threads.get(focus),
                'threads': list(self.threads.values())[:30], 'history': self.history[:50]}

    def desktop_summary(self):
        state = self.state()
        bucket = state['quota']['buckets'].get(self.bucket_id)
        if not bucket and state['quota']['buckets']:
            bucket = next(iter(state['quota']['buckets'].values()))
        return {'enabled': self.enabled and self.ring_mode != 'hidden', 'ring_mode': self.ring_mode,
                'status': self.quota_status,
                'stale': state['quota']['stale'], 'bucket': bucket if self.enabled else None,
                'scope': '当前监测账号额度'}

    async def _task_loop(self, epoch):
        while self.enabled and epoch == self.epoch:
            try:
                await asyncio.to_thread(self.hooks.heartbeat)
                events = await asyncio.to_thread(self.jsonl.poll)
                events += await asyncio.to_thread(self.hooks.poll)
                self.task_status = 'available' if self.jsonl.capability == 'available' else 'unavailable'
                for event in events:
                    if epoch != self.epoch: return
                    await self.accept(event, epoch)
                for item in self.threads.values():
                    if item['status'] in ('running', 'waiting_approval', 'waiting_input') and time.time() - item['seen_epoch'] > 120:
                        item['status'] = 'stale'
                focus = self.thread_id if self.mode == 'specific' else self.focus
                current = self.threads.get(focus)
                watch_key = (focus, current['turn_id']) if current and current['status'] == 'running' else None
                if (watch_key and self.target in ('watch', 'both') and watch_key != self.watch_started_for
                        and self.control.auto_available() and not self.control.notifications.active
                        and not self.control.notifications.queue and not self.control.notifications.current()):
                    guard = lambda: (self.enabled and epoch == self.epoch and self.control.auto_available()
                                     and self.threads.get(focus, {}).get('status') == 'running')
                    try:
                        if await self.control.robot.auto_expression('working', guard) == 'accepted':
                            self.watch_started_for = watch_key
                    except Exception:
                        pass
                if not watch_key:
                    self.watch_started_for = None
                await asyncio.sleep(1)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.task_status = 'unavailable'
                self.accept_after = time.time()
                self.jsonl.reset_baseline()
                self.hooks.reset_baseline()
                await asyncio.sleep(5)

    async def accept(self, event, epoch=None):
        if not self.enabled or (epoch is not None and epoch != self.epoch): return
        thread = event['thread_id']; turn = event['turn_id']; kind = event['kind']
        if not thread or len(thread) > 100: return
        if not turn and kind in ('turn_completed', 'interrupted', 'failed'):
            turn = self.threads.get(thread, {}).get('turn_id', '')
        if not turn and kind != 'running': return
        key = (event['source'], event['source_instance'], thread, turn,
               event['event_id'] or f"{kind}:{event['occurred_at']}")
        if key in self.seen: return
        self.seen.add(key)
        if len(self.seen) > 4000: self.seen = set(list(self.seen)[-2000:])
        previous = self.threads.get(thread)
        if previous and previous['turn_id'] != turn and kind not in ('running',):
            return
        event_time = _event_epoch(event['occurred_at'], time.time())
        if previous and previous['turn_id'] != turn and previous['last_seen'] and event['occurred_at']:
            if event_time < _event_epoch(previous['last_seen']):
                return
        if previous and previous['turn_id'] == turn:
            if previous['status'] in ('turn_completed', 'failed', 'interrupted') and kind == 'running': return
            if kind == previous['status']:
                previous['last_seen'] = event['occurred_at'] or previous['last_seen']
                previous['seen_epoch'] = event_time
                return
        item = {'thread_id': thread, 'turn_id': turn, 'label': event['sanitized_label'],
                'source': event['source'], 'status': kind, 'last_seen': event['occurred_at'],
                'seen_epoch': event_time, 'capabilities': event['capabilities']}
        self.threads[thread] = item
        if previous and previous['status'] != kind:
            self.control.notifications.clear('codex')
        if self.mode == 'auto' and (not self.focus or self.focus not in self.threads
                                    or self.threads[self.focus]['status'] in ('stale', 'turn_completed', 'failed', 'interrupted')):
            self.focus = thread
        # Delayed discovery, reconnects and old files with a new mtime must
        # never turn historical turns into alerts.
        if event.get('baseline') or kind == 'running' or _event_epoch(event.get('occurred_at')) < self.accept_after:
            return
        if kind in MESSAGES:
            task = asyncio.create_task(self._notify(kind, thread, turn, item, self.epoch,
                                                     event.get('observed_at', '')))
            self.alerts.add(task)
            task.add_done_callback(self.alerts.discard)

    async def _notify(self, kind, thread, turn, item, epoch, observed_at=''):
        message, expression, priority = MESSAGES[kind]
        def valid():
            return (self.enabled and self.epoch == epoch and self.threads.get(thread, {}).get('turn_id') == turn
                    and self.threads[thread]['status'] == kind)
        async def action():
            response_started_at = datetime.now(timezone.utc).isoformat()
            delivery = {'desktop': 'not_requested', 'watch': 'not_requested', 'sound': 'off'}
            if self.target in ('desktop', 'both'):
                self.revision += 1
                completed = kind == 'turn_completed'
                self.control.notifications.show(
                    'codex', expression, message, self.revision, priority=priority,
                    seconds=300 if completed else 12,
                    block_seconds=12,
                    dismiss_on_click=completed)
                delivery['desktop'] = 'displayed_to_client'
            if self.target in ('watch', 'both'):
                try: delivery['watch'] = await self.control.robot.auto_notify(expression, message, valid)
                except Exception: delivery['watch'] = 'failed'
            if self.sound and valid():
                if self.sound_target == 'watch':
                    try: delivery['sound'] = await self.control.robot.auto_sound(2, valid)
                    except Exception: delivery['sound'] = 'failed'
                else:
                    delivery['sound'] = await self.control.play_auto_tone(valid)
            if valid():
                self.history.insert(0, {'at': datetime.now().astimezone().isoformat(timespec='seconds'),
                                        'source_at': item.get('last_seen', ''), 'detected_at': observed_at,
                                        'response_started_at': response_started_at,
                                        'thread_id': thread, 'kind': kind, 'message': message,
                                        'delivery': delivery})
                del self.history[50:]
        await self.control.notifications.dispatch(source='codex', priority=priority, valid=valid, action=action)

    async def _quota_loop(self, epoch):
        while self.enabled and epoch == self.epoch:
            delay = max(0, self.quota_next - time.monotonic())
            if delay:
                try:
                    await asyncio.wait_for(self.refresh_event.wait(), delay)
                    self.refresh_event.clear()
                except asyncio.TimeoutError:
                    pass
            if not self.enabled or epoch != self.epoch: return
            if time.monotonic() - self.quota_last_request < 5:
                self.quota_next = self.quota_last_request + 5
                continue
            try:
                self.quota_busy = True
                self.quota_last_request = time.monotonic()
                raw = await self.rpc.read()
                if epoch != self.epoch: return
                self.quota = quota_snapshot(raw)
                self.quota_at = time.time()
                self.quota_status = self.quota['status']
                self.quota_error = ''
                self.quota_failures = 0
                self.quota_next = time.monotonic() + 120
                await self._check_low(epoch)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                code = str(exc) if isinstance(exc, RuntimeError) else ''
                explanations = {'cli_missing': ('cli_missing', '本机找不到 Codex CLI'),
                                'api_key_account': ('api_key', '当前为 API Key 模式，未提供 ChatGPT 额度'),
                                'unsupported_account': ('unsupported_account', '当前账号类型不提供该额度'),
                                'not_logged_in': ('not_logged_in', 'Codex 尚未登录可用账号'),
                                'rpc_error_-32601': ('unsupported_rpc', '此 Codex 版本不支持额度读取'),
                                'rpc_error_401': ('auth_failed', 'Codex 认证失败'),
                                'rpc_error_403': ('auth_failed', 'Codex 认证失败')}
                self.quota_status, self.quota_error = explanations.get(code, ('unavailable', '额度读取暂不可用'))
                self.quota_failures += 1
                self.quota_next = time.monotonic() + min(900, 15 * 2 ** min(self.quota_failures, 6))
            finally:
                self.quota_busy = False

    async def refresh_quota(self):
        if not self.enabled: return self.state()
        # Repeated refresh clicks and the timer join the same scheduled request.
        if not self.quota_busy:
            self.quota_next = min(self.quota_next, time.monotonic())
            self.refresh_event.set()
        return self.state()

    async def _check_low(self, epoch):
        if self.state()['quota']['stale']: return
        buckets = self.quota['buckets']
        selected = self.bucket_id if self.bucket_id in buckets else next(iter(buckets), '')
        for index, window in enumerate(buckets.get(selected, {}).get('windows', [])):
            remaining = window['remaining_percent']
            if remaining is None: continue
            key = (selected, index, window['resets_at'])
            if remaining >= self.threshold + 5:
                self.low_armed[key] = True
            elif remaining <= self.threshold and self.low_armed.get(key, True):
                self.low_armed[key] = False
                task = asyncio.create_task(self._quota_alert(key, epoch))
                self.alerts.add(task)
                task.add_done_callback(self.alerts.discard)

    async def _quota_alert(self, key, epoch):
        message, expression, priority = MESSAGES['quota_low']
        valid = lambda: self.enabled and self.epoch == epoch and not self.state()['quota']['stale'] and not self.low_armed.get(key, True)
        async def action():
            delivery = {'desktop': 'not_requested', 'watch': 'not_requested', 'sound': 'off'}
            if self.target in ('desktop', 'both'):
                self.revision += 1
                self.control.notifications.show('codex', expression, message, self.revision, priority=priority)
                delivery['desktop'] = 'displayed_to_client'
            if self.target in ('watch', 'both'):
                try: delivery['watch'] = await self.control.robot.auto_notify(expression, message, valid)
                except Exception: delivery['watch'] = 'failed'
            if self.sound and valid():
                if self.sound_target == 'watch':
                    try: delivery['sound'] = await self.control.robot.auto_sound(2, valid)
                    except Exception: delivery['sound'] = 'failed'
                else: delivery['sound'] = await self.control.play_auto_tone(valid)
            if valid():
                self.history.insert(0, {'at': datetime.now().astimezone().isoformat(timespec='seconds'),
                                        'thread_id': '', 'kind': 'quota_low', 'message': message,
                                        'delivery': delivery})
                del self.history[50:]
        await self.control.notifications.dispatch(source='codex', priority=priority, valid=valid, action=action)
