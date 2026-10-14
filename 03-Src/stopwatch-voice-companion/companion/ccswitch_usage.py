"""Read CC Switch's Codex usage ledger without touching credentials or source logs.

Accounting follows CC Switch v3.20.3 sql_helpers.rs and usage_stats.rs:
normalize cached input, apply its session/proxy filter, add daily rollups.
"""
import asyncio
from contextlib import closing
from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
import sqlite3
import time

BEIJING = timezone(timedelta(hours=8))
TOKEN_COLUMNS = {'app_type', 'input_tokens', 'output_tokens', 'cache_read_tokens',
                 'cache_creation_tokens', 'input_token_semantics'}
DETAIL_COLUMNS = TOKEN_COLUMNS | {'created_at', 'model', 'data_source', 'status_code'}
ROLLUP_COLUMNS = TOKEN_COLUMNS | {'date', 'request_count'}


def fresh_input(alias):
    # Cache-inclusive Codex input: never count the same cached tokens twice.
    return f'''CASE
      WHEN {alias}.input_token_semantics=2 THEN {alias}.input_tokens
      WHEN {alias}.input_token_semantics=1
        AND {alias}.input_tokens>=({alias}.cache_read_tokens+{alias}.cache_creation_tokens)
        THEN {alias}.input_tokens-{alias}.cache_read_tokens-{alias}.cache_creation_tokens
      WHEN {alias}.input_token_semantics=0 AND {alias}.input_tokens>={alias}.cache_read_tokens
        THEN {alias}.input_tokens-{alias}.cache_read_tokens
      ELSE {alias}.input_tokens END'''


EFFECTIVE_DETAIL = '''NOT (
  COALESCE(l.data_source,'proxy') IN ('session_log','codex_session','gemini_session','opencode_session')
  AND EXISTS (SELECT 1 FROM proxy_request_logs p
    WHERE COALESCE(p.data_source,'proxy')='proxy' AND p.app_type=l.app_type
      AND p.status_code>=200 AND p.status_code<300
      AND p.input_tokens=l.input_tokens AND p.output_tokens=l.output_tokens
      AND p.cache_read_tokens=l.cache_read_tokens
      AND (p.cache_creation_tokens=l.cache_creation_tokens OR
        (l.cache_creation_tokens=0 AND l.data_source IN ('codex_session','gemini_session','opencode_session')))
      AND p.created_at BETWEEN l.created_at-600 AND l.created_at+600
      AND (LOWER(p.model)=LOWER(l.model) OR LOWER(p.model)='unknown' OR LOWER(l.model)='unknown'))
)'''


def read_today(path, now=None):
    now = now or datetime.now(BEIJING)
    day = now.astimezone(BEIJING).date()
    start = datetime.combine(day, datetime.min.time(), BEIJING)
    bounds = (int(start.timestamp()), int((start + timedelta(days=1)).timestamp()))
    result = {'date': day.isoformat(), 'timezone': 'Asia/Hong_Kong', 'source': 'ccswitch',
              'scope': 'local_codex', 'status': 'available', 'stale': False,
              'sampled_at': now.astimezone(BEIJING).isoformat()}
    path = Path(path).expanduser().resolve()
    if not path.is_file():
        return {**result, 'status': 'missing', 'total_tokens': None}
    # mode=ro observes committed WAL data; immutable or copying just .db would miss it.
    with closing(sqlite3.connect(path.as_uri() + '?mode=ro', uri=True, timeout=.2)) as conn:
        conn.execute('PRAGMA query_only=ON')
        deadline = time.monotonic() + 2
        conn.set_progress_handler(lambda: int(time.monotonic() > deadline), 1000)
        conn.execute('BEGIN')  # Detail/rollup queries must see the same snapshot.
        for table, required in (('proxy_request_logs', DETAIL_COLUMNS), ('usage_daily_rollups', ROLLUP_COLUMNS)):
            columns = {r[1] for r in conn.execute(f'PRAGMA table_info({table})')}
            if not required <= columns:
                return {**result, 'status': 'unsupported', 'total_tokens': None}
        unknown = conn.execute('''SELECT 1 FROM proxy_request_logs WHERE app_type='codex'
          AND created_at>=? AND created_at<? AND (input_token_semantics IS NULL OR input_token_semantics NOT IN (0,1,2))
          UNION ALL SELECT 1 FROM usage_daily_rollups WHERE app_type='codex' AND date=?
          AND (input_token_semantics IS NULL OR input_token_semantics NOT IN (0,1,2)) LIMIT 1''', (*bounds, day.isoformat())).fetchone()
        if unknown:
            return {**result, 'status': 'unsupported', 'total_tokens': None}
        detail = conn.execute(f'''SELECT COUNT(*), COALESCE(SUM({fresh_input('l')}),0),
          COALESCE(SUM(l.output_tokens),0), COALESCE(SUM(l.cache_read_tokens),0),
          COALESCE(SUM(l.cache_creation_tokens),0)
          FROM proxy_request_logs l WHERE l.app_type='codex' AND l.created_at>=? AND l.created_at<?
          AND {EFFECTIVE_DETAIL}''', bounds).fetchone()
        rollup = conn.execute(f'''SELECT COALESCE(SUM(r.request_count),0), COALESCE(SUM({fresh_input('r')}),0),
          COALESCE(SUM(r.output_tokens),0), COALESCE(SUM(r.cache_read_tokens),0),
          COALESCE(SUM(r.cache_creation_tokens),0)
          FROM usage_daily_rollups r WHERE r.app_type='codex' AND r.date=?''', (day.isoformat(),)).fetchone()
        requests, fresh, output, cached, created = [a + b for a, b in zip(detail, rollup)]
        if any(type(n) is not int or n < 0 for n in (requests, fresh, output, cached, created)):
            return {**result, 'status': 'unsupported', 'total_tokens': None}
        last = conn.execute("SELECT MAX(created_at) FROM proxy_request_logs WHERE app_type='codex'").fetchone()[0]
    return {**result, 'total_tokens': fresh + output + cached + created,
            'input_tokens': fresh + cached + created, 'fresh_input_tokens': fresh,
            'output_tokens': output, 'cache_tokens': cached + created, 'request_count': requests,
            'last_event_at': last}


class CCSwitchUsage:
    def __init__(self, path=None, now=None, monotonic=None):
        self.path = Path(path) if path is not None else Path(os.environ.get('CC_SWITCH_HOME') or Path.home() / '.cc-switch') / 'cc-switch.db'
        self.now = now or (lambda: datetime.now(BEIJING))
        self.monotonic = monotonic or time.monotonic
        self.lock = asyncio.Lock()
        self.cached = None
        self.next_read = 0

    async def get(self):
        async with self.lock:
            now = self.now()
            day = now.astimezone(BEIJING).date().isoformat()
            same_day = self.cached and self.cached['date'] == day
            if same_day and self.monotonic() < self.next_read:
                return dict(self.cached)
            try:
                value = await asyncio.to_thread(read_today, self.path, now)
            except (sqlite3.Error, OSError, ValueError, OverflowError):
                value = {'date': day, 'timezone': 'Asia/Hong_Kong', 'source': 'ccswitch',
                         'scope': 'local_codex', 'status': 'unavailable', 'stale': True,
                         'total_tokens': None, 'sampled_at': now.isoformat()}
            if value['status'] != 'available' and same_day and self.cached.get('total_tokens') is not None:
                value = {**self.cached, 'status': value['status'], 'stale': True}
            self.cached = value
            self.next_read = self.monotonic() + 20
            return dict(value)
