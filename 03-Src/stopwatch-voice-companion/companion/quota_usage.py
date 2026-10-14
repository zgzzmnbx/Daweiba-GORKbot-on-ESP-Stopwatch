"""Hover-only official quota reads, independent of task/notification preferences."""
import asyncio
from copy import deepcopy
from datetime import datetime, timezone
import time

from .codex_monitor import quota_snapshot


class QuotaUsage:
    def __init__(self, rpc, monitor, *, clock=time.time, monotonic=time.monotonic):
        self.rpc, self.monitor = rpc, monitor
        self.clock, self.monotonic = clock, monotonic
        self.lock = asyncio.Lock()
        self.value = {'status': 'unknown', 'buckets': {}, 'sampled_at': '', 'stale': True}
        self.next_read = 0

    def snapshot(self):
        value = deepcopy(self.value)
        now = self.clock()
        if value.get('sampled_at') and now - datetime.fromisoformat(value['sampled_at']).timestamp() > 300:
            value['stale'] = True
        if any(w.get('resets_at') and w['resets_at'] <= now
               for b in value['buckets'].values() for w in b['windows']):
            value['stale'] = True
        return {**value, 'source': 'codex_official', 'scope': '当前 Codex CLI 登录账号',
                'bucket_id': self.monitor.bucket_id}

    async def get(self):
        async with self.lock:
            # Reuse fresh sentinel data when already enabled; never enable it here.
            state = self.monitor.state()
            shared = state['quota']
            if state['enabled'] and state['quota_status'] == 'available' and not shared['stale']:
                self.value = deepcopy(shared)
                self.next_read = 0
                return self.snapshot()
            expired = self.snapshot()['stale'] and not self.value['stale'] and self.value['status'] == 'available'
            if self.monotonic() < self.next_read and not expired:
                return self.snapshot()
            try:
                result = quota_snapshot(await self.rpc.read())
                self.value = {**result, 'sampled_at': datetime.fromtimestamp(self.clock(), timezone.utc).isoformat(),
                              'stale': result['status'] != 'available'}
                self.next_read = self.monotonic() + 120
                if self.snapshot()['stale']:
                    self.value['stale'] = True
                    self.next_read = self.monotonic() + 30
            except Exception as exc:
                status = {'cli_missing': 'cli_missing', 'not_logged_in': 'not_logged_in',
                          'rpc_network': 'network_error', 'rpc_timeout': 'timeout',
                          'api_key_account': 'api_key_account', 'unsupported_account': 'unsupported'}.get(str(exc), 'unavailable')
                # Never keep another login's old percentages after an explicit account rejection.
                if status in ('not_logged_in', 'api_key_account', 'unsupported'):
                    self.value = {'buckets': {}, 'sampled_at': ''}
                self.value = {**self.value, 'status': status, 'stale': True}
                self.next_read = self.monotonic() + 30
            return self.snapshot()
