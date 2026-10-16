"""Gork traffic module: collectors and accounting have no voice/device dependencies."""
import asyncio
import copy
import json
import os
from pathlib import Path
import time

from .accounting import Ledger, stamp
from .interfaces import InterfaceRates, read_interfaces
from .pipe_client import MihomoClient
from .system_usage import read_system_usage


class TrafficMonitor:
    def __init__(self, directory=None, *, clash=None, interfaces=None, history=None):
        self.directory = Path(directory) if directory else None
        self.clash_reader = clash or MihomoClient().get
        self.interface_reader = interfaces or read_interfaces
        self.history_reader = history or read_system_usage
        self.enabled = False
        self.generation = 0
        self.tasks = []
        self.lock = asyncio.Lock()
        self.ledger = None
        self.file_lock = None
        self.nic = InterfaceRates()
        self.physical = {'status': 'disabled'}
        self.clash = {'status': 'disabled'}
        self.history = {'status': 'unknown', 'rows': []}
        self.detail = {}
        if self.directory:
            try:
                self.enabled = json.loads((self.directory / 'settings.json').read_text())['enabled'] is True
            except (OSError, ValueError, KeyError, TypeError):
                pass
            try:
                self.history = json.loads((self.directory / 'windows-history.json').read_text(encoding='utf-8'))
                if not isinstance(self.history, dict) or not isinstance(self.history.get('rows'), list):
                    raise ValueError('Invalid history')
                self.history['status'] = 'stale'
            except (OSError, ValueError, TypeError):
                self.history = {'status': 'unknown', 'rows': []}

    def _save(self, name, value):
        if self.directory:
            self.directory.mkdir(parents=True, exist_ok=True)
            target = self.directory / name
            temp = target.with_suffix('.tmp')
            temp.write_text(json.dumps(value, ensure_ascii=False), encoding='utf-8')
            os.replace(temp, target)

    async def start(self):
        if self.enabled:
            try:
                await self._launch()
            except Exception:
                # Optional diagnostics must not prevent voice/device startup.
                self.enabled = False
                self.clash = {'status': 'unavailable'}

    async def _launch(self):
        if self.directory:
            self.directory.mkdir(parents=True, exist_ok=True)
        try:
            if self.directory:
                self.file_lock = open(self.directory / 'collector.lock', 'a+b')
                if self.file_lock.seek(0, 2) == 0:
                    self.file_lock.write(b'0')
                    self.file_lock.flush()
                self.file_lock.seek(0)
                if os.name == 'nt':
                    import msvcrt
                    msvcrt.locking(self.file_lock.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(self.file_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.ledger = Ledger(str(self.directory / 'traffic.sqlite3') if self.directory else ':memory:')
        except Exception:
            if self.file_lock:
                self.file_lock.close()
                self.file_lock = None
            raise
        self.clash = {'status': 'connecting'}
        self.physical = {'status': 'baseline'}
        self.nic = InterfaceRates()
        gen = self.generation
        self.tasks = [asyncio.create_task(self._loop(kind, interval, gen))
                      for kind, interval in [('interfaces', 1), ('clash', 1), ('history', 900)]]

    async def _stop(self):
        self.generation += 1
        # Await in-flight bounded reads before closing their ledger; cancel sleeps,
        # never abandon a thread still using SQLite or a Windows pipe.
        for task in self.tasks:
            if getattr(task, '_traffic_sleeping', False):
                task.cancel()
        await asyncio.gather(*self.tasks, return_exceptions=True)
        self.tasks = []
        if self.ledger:
            self.ledger.close()
            self.ledger = None
        if self.file_lock:
            self.file_lock.close()
            self.file_lock = None
        self.physical = {**self.physical, 'status': 'disabled'}
        self.clash = {**self.clash, 'status': 'disabled'}

    async def configure(self, enabled):
        async with self.lock:
            if enabled == self.enabled:
                return self.snapshot()
            self._save('settings.json', {'enabled': enabled})
            self.enabled = enabled
            if enabled:
                try:
                    await self._launch()
                except Exception:
                    self.enabled = False
                    self._save('settings.json', {'enabled': False})
                    raise
            else:
                await self._stop()
            return self.snapshot()

    async def close(self):
        async with self.lock:
            await self._stop()

    async def _loop(self, kind, interval, gen):
        task = asyncio.current_task()
        while gen == self.generation and self.enabled:
            started = time.monotonic()
            try:
                reader = {'interfaces': self.interface_reader, 'clash': self.clash_reader,
                          'history': self.history_reader}[kind]
                result = await asyncio.to_thread(reader)
                if gen != self.generation or not self.enabled:
                    return
                now = time.time()
                if kind == 'interfaces':
                    self.physical = self.nic.ingest(result, time.monotonic()) | {'updated_at': now}
                elif kind == 'clash':
                    await asyncio.to_thread(self.ledger.ingest, result)
                    self.detail = await asyncio.to_thread(self.ledger.state, 'today')
                    self.detail['day'] = stamp()[:10]
                    self.clash = {'status': 'available', 'updated_at': now,
                                  'latest': self.detail['latest'], 'routes': self.detail['routes'],
                                  'core': self.detail['core'], 'difference': self.detail['difference']}
                else:
                    if not result.get('available'):
                        raise OSError('History unavailable')
                    # Only expose basename/day/bytes. Do not expose adapter names,
                    # app paths, identity hashes, pipe path or credentials.
                    rows = {}
                    for row in result.get('rows', []):
                        key = (row['day'], row['app'])
                        entry = rows.setdefault(key, {'day': key[0], 'name': key[1], 'upload': 0, 'download': 0})
                        entry['upload'] += max(0, int(row['upload']))
                        entry['download'] += max(0, int(row['download']))
                    self.history = {'status': 'partial' if result.get('errors') else 'available',
                                    'updated_at': now, 'rows': sorted(rows.values(), key=lambda r:r['upload']+r['download'], reverse=True)}
                    self._save('windows-history.json', self.history)
            except asyncio.CancelledError:
                return
            except Exception:
                if kind == 'clash':
                    self.clash = {**self.clash, 'status': 'unavailable'}
                    if self.ledger:
                        await asyncio.to_thread(self.ledger.boundary, 'disconnected')
                elif kind == 'interfaces':
                    self.nic.reset()
                    self.physical = {**self.physical, 'status': 'unavailable', 'up_speed': None, 'down_speed': None}
                else:
                    self.history = {**self.history, 'status': 'stale' if self.history.get('updated_at') else 'unavailable'}
            if gen != self.generation or not self.enabled:
                return
            task._traffic_sleeping = True
            try:
                await asyncio.sleep(max(.1, interval - (time.monotonic() - started)))
            except asyncio.CancelledError:
                return
            finally:
                task._traffic_sleeping = False

    def snapshot(self, details=False):
        result = {'enabled': self.enabled, 'physical': self.physical, 'clash': self.clash,
                  'day': stamp()[:10]}
        if details:
            result |= {'history': self.history, 'processes': self.detail.get('processes', []),
                       'domains': self.detail.get('domains', []), 'connections': self.detail.get('connections', [])}
        result = copy.deepcopy(result)
        if self.detail.get('day') and self.detail['day'] != result['day']:
            # An old snapshot must never be relabelled as the new day's usage.
            result['clash'].pop('routes', None)
            result['clash'].pop('difference', None)
            for key in ('processes', 'domains', 'connections'):
                if key in result:
                    result[key] = []
        for key in ('physical', 'clash'):
            if self.enabled and result[key].get('updated_at') and time.time() - result[key]['updated_at'] > 5:
                result[key]['status'] = 'stale'
        return result
