"""Read-only Codex event sources. Never retain a prompt, answer or tool body."""
import asyncio
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import time
import re


EVENTS = {'task_started': 'running', 'task_complete': 'turn_completed'}
HOOK_EVENTS = {
    'UserPromptSubmit': 'running', 'PreToolUse': 'running',
    'PostToolUse': 'running', 'PermissionRequest': 'waiting_approval',
    'Stop': 'turn_completed', 'Interrupt': 'interrupted',
}


def _short_id(value):
    if not isinstance(value, str) or not 1 <= len(value) <= 100:
        return ''
    return value if all(c.isalnum() or c in '-_' for c in value) else ''


def _safe_time(value):
    if not isinstance(value, str):
        return ''
    try:
        datetime.fromisoformat(value.replace('Z', '+00:00'))
        return value[:40]
    except ValueError:
        return ''


def normalize_hook(raw):
    """Whitelist only verifiable lifecycle fields from documented hook input."""
    if not isinstance(raw, dict):
        return None
    event = raw.get('hook_event_name')
    kind = HOOK_EVENTS.get(event)
    thread = _short_id(raw.get('session_id'))
    if not kind or not thread:
        return None
    turn = _short_id(raw.get('turn_id'))
    if event == 'Stop' and raw.get('stop_hook_active'):
        # Other hooks can continue the same turn. Do not claim a final result.
        return None
    return {'source': 'hook', 'source_instance': thread, 'thread_id': thread,
            'turn_id': turn, 'event_id': _short_id(raw.get('event_id')) or '',
            'kind': kind, 'occurred_at': _safe_time(raw.get('timestamp')),
            'observed_at': datetime.now(timezone.utc).isoformat(),
            'capabilities': ['running', 'waiting_approval', 'turn_completed', 'interrupted'],
            'sanitized_label': thread[:8]}


def normalize_jsonl(raw, thread):
    if not isinstance(raw, dict) or raw.get('type') != 'event_msg':
        return None
    payload = raw.get('payload')
    if not isinstance(payload, dict):
        return None
    kind = EVENTS.get(payload.get('type'))
    turn = _short_id(payload.get('turn_id'))
    if not kind or not turn:
        return None
    return {'source': 'jsonl', 'source_instance': thread, 'thread_id': thread,
            'turn_id': turn, 'event_id': f"{turn}:{kind}", 'kind': kind,
            'occurred_at': _safe_time(raw.get('timestamp')),
            'observed_at': datetime.now(timezone.utc).isoformat(),
            'capabilities': ['running', 'turn_completed'], 'sanitized_label': thread[:8]}


class JsonlSource:
    """Bounded incremental tailer. A first scan establishes state without alerts."""
    def __init__(self, root=None, max_files=40):
        self.root = Path(root or Path(os.environ.get('CODEX_HOME') or Path.home() / '.codex') / 'sessions')
        self.max_files = max_files
        self.files = {}
        self.last_discovery = 0.0
        self.last_full_discovery = 0.0
        self.capability = 'not_connected'
        self.initial_discovery = True
        self.activated_at = time.time()

    def reset_baseline(self):
        self.files.clear()
        self.initial_discovery = True
        self.last_full_discovery = 0.0
        self.last_discovery = 0.0
        self.activated_at = time.time()

    def _discover(self, full=False):
        # Only recent day directories are rescanned; active files remain pinned.
        now = datetime.now(timezone.utc)
        paths = []
        for day in (now, now.fromtimestamp(now.timestamp() - 86400, timezone.utc)):
            folder = self.root / day.strftime('%Y') / day.strftime('%m') / day.strftime('%d')
            try:
                paths.extend(folder.glob('*.jsonl'))
            except OSError:
                pass
        if full:
            try:
                paths.extend(self.root.glob('*/*/*/*.jsonl'))
            except OSError:
                pass
        paths = sorted(set(paths), key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True)
        return paths[:self.max_files]

    def poll(self):
        if not self.root.is_dir():
            self.capability = 'unavailable'
            return []
        if time.monotonic() - self.last_discovery >= 1:
            self.last_discovery = time.monotonic()
            full = not self.last_full_discovery or time.monotonic() - self.last_full_discovery >= 60
            if full:
                self.last_full_discovery = time.monotonic()
            for index, path in enumerate(self._discover(full=full)):
                # Discovery may reach an old file only after the first bounded scan.
                # File mtime alone cannot make its historical events current.
                try:
                    changed_after_enable = path.stat().st_mtime >= self.activated_at
                except OSError:
                    continue
                self.files.setdefault(path, {'new': not self.initial_discovery and changed_after_enable,
                                             'tail_size': 1024 * 1024 if index < 8 else 128 * 1024})
            self.initial_discovery = False
            if len(self.files) > self.max_files:
                for path in list(self.files)[:-self.max_files]:
                    self.files.pop(path, None)
        out = []
        budget = 512 * 1024
        for path, cursor in list(self.files.items()):
            if budget <= 0:
                break
            try:
                stat = path.stat()
                identity = (stat.st_dev, stat.st_ino)
                if 'identity' not in cursor or cursor['identity'] != identity or stat.st_size < cursor['offset']:
                    # Initial or replaced file: inspect a bounded tail for current state.
                    new_file = cursor.get('new', False)
                    start = 0 if new_file else max(0, stat.st_size - cursor.get('tail_size', 128 * 1024))
                    cursor = {'identity': identity, 'offset': start,
                              'partial': b'', 'baseline_end': 0 if new_file else stat.st_size,
                              'skip_first': start > 0}
                with path.open('rb') as handle:
                    handle.seek(cursor['offset'])
                    baseline_left = cursor['baseline_end'] - cursor['offset']
                    read_limit = min(budget, 128 * 1024, baseline_left) if baseline_left > 0 else min(budget, 128 * 1024)
                    chunk = handle.read(read_limit)
                is_baseline = cursor['offset'] < cursor['baseline_end']
                cursor['offset'] += len(chunk)
                budget -= len(chunk)
                lines = (cursor['partial'] + chunk).split(b'\n')
                cursor['partial'] = lines.pop()[-16384:]
                if cursor['skip_first'] and lines:
                    lines.pop(0)  # partial first line of a tail sample
                    cursor['skip_first'] = False
                match = re.search(r'([0-9a-fA-F]{8}-[0-9a-fA-F-]{27,40})$', path.stem)
                thread = _short_id(match.group(1)) if match else ''
                for line in lines:
                    if len(line) > 65536:
                        continue
                    try:
                        event = normalize_jsonl(json.loads(line), thread)
                    except (ValueError, UnicodeError):
                        continue
                    if event:
                        event['baseline'] = is_baseline
                        out.append(event)
                self.files[path] = cursor
            except OSError:
                self.files.pop(path, None)
        self.capability = 'available'
        return out


class HookSpool:
    def __init__(self, folder):
        self.folder = Path(folder)
        self.ready = False

    def reset_baseline(self):
        if self.folder.is_dir():
            for path in self.folder.glob('*.json'):
                if path.name != 'enabled.json':
                    path.unlink(missing_ok=True)
        self.ready = True

    def heartbeat(self):
        self.folder.mkdir(parents=True, exist_ok=True)
        marker = self.folder / 'enabled.json'
        temporary = self.folder / 'enabled.tmp'
        temporary.write_text(json.dumps({'expires_at': time.time() + 5}), encoding='utf-8')
        temporary.replace(marker)

    def disable(self):
        (self.folder / 'enabled.json').unlink(missing_ok=True)

    def poll(self):
        if not self.folder.is_dir():
            return []
        paths = sorted(path for path in self.folder.glob('*.json') if path.name != 'enabled.json')[:100]
        out = []
        for path in paths:
            try:
                if path.stat().st_size <= 4096:
                    event = normalize_hook(json.loads(path.read_text(encoding='utf-8')))
                    if event:
                        event['baseline'] = not self.ready
                        out.append(event)
            except (OSError, ValueError):
                pass
            finally:
                path.unlink(missing_ok=True)
        self.ready = True
        return out


class QuotaRPC:
    """One short-lived app-server process per read, never a thread controller."""
    def __init__(self, executable='codex'):
        self.executable = executable
        self.process = None

    async def read(self, timeout=12):
        executable = shutil.which(self.executable)
        if not executable:
            raise RuntimeError('cli_missing')
        kwargs = {}
        if os.name == 'nt':
            import subprocess
            kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW
        proc = await asyncio.create_subprocess_exec(executable, 'app-server', '--listen', 'stdio://',
                   stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
                   stderr=asyncio.subprocess.DEVNULL, **kwargs)
        self.process = proc
        try:
            async def call():
                pending = {}
                async def send(value):
                    proc.stdin.write((json.dumps(value, separators=(',', ':')) + '\n').encode())
                    await proc.stdin.drain()
                async def response(expected):
                    if expected in pending:
                        return pending.pop(expected)
                    while True:
                        line = await proc.stdout.readline()
                        if not line: raise RuntimeError('rpc_disconnected')
                        obj = json.loads(line)
                        if obj.get('id') == expected:
                            return obj
                        other = obj.get('id')
                        if type(other) is int and 1 <= other <= 3 and len(pending) < 3:
                            pending[other] = obj
                await send({'jsonrpc': '2.0', 'id': 1, 'method': 'initialize',
                            'params': {'clientInfo': {'name': 'gork-quota-readonly', 'version': '0.18.1'}}})
                obj = await response(1)
                if 'error' in obj: raise RuntimeError('rpc_initialize')
                await send({'jsonrpc': '2.0', 'method': 'initialized'})
                await send({'jsonrpc': '2.0', 'id': 2, 'method': 'account/read',
                            'params': {'refreshToken': False}})
                account_response = await response(2)
                if 'error' not in account_response:
                    account_result = account_response.get('result') or {}
                    account = account_result.get('account')
                    if isinstance(account, dict) and account.get('type') == 'apiKey':
                        raise RuntimeError('api_key_account')
                    if isinstance(account, dict) and account.get('type') == 'amazonBedrock':
                        raise RuntimeError('unsupported_account')
                    if account is None and account_result.get('requiresOpenaiAuth'):
                        raise RuntimeError('not_logged_in')
                await send({'jsonrpc': '2.0', 'id': 3, 'method': 'account/rateLimits/read', 'params': {}})
                result = await response(3)
                if 'error' in result:
                    code = result['error'].get('code') if isinstance(result['error'], dict) else None
                    raise RuntimeError(f'rpc_error_{code}')
                return result.get('result', {})
            return await asyncio.wait_for(call(), timeout)
        finally:
            if proc.returncode is None:
                proc.kill()
            await proc.wait()
            self.process = None

    async def close(self):
        if self.process and self.process.returncode is None:
            self.process.kill()
            await self.process.wait()
