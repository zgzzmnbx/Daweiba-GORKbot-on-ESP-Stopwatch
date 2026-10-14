"""Read-only live accounting parity check; persist sanitized aggregates only."""
from contextlib import closing
from datetime import datetime, timedelta, timezone
import importlib.util
import json
import os
from pathlib import Path
import sqlite3

root=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('usage',root/'03-Src/stopwatch-voice-companion/companion/ccswitch_usage.py')
usage=importlib.util.module_from_spec(spec);spec.loader.exec_module(usage)
db=Path(os.environ.get('CC_SWITCH_HOME') or Path.home()/'.cc-switch')/'cc-switch.db'
now=datetime.now(timezone(timedelta(hours=8)))
day=now.date().isoformat();start=now.replace(hour=0,minute=0,second=0,microsecond=0)

# Independent arithmetic for the confirmed local DB, whose sources are session
# records only. The production fixture tests cover mixed session/proxy dedup.
with closing(sqlite3.connect(db.as_uri()+'?mode=ro',uri=True)) as c:
    c.execute('PRAGMA query_only=ON');c.execute('BEGIN')
    sources={r[0] for r in c.execute("SELECT DISTINCT data_source FROM proxy_request_logs WHERE app_type='codex'")}
    if sources != {'codex_session'}:
        raise RuntimeError('Live parity fixture expects the currently confirmed session-only source')
    row=c.execute('''SELECT COUNT(*), COALESCE(SUM(CASE
      WHEN input_token_semantics=2 THEN input_tokens
      WHEN input_token_semantics=1 AND input_tokens>=cache_read_tokens+cache_creation_tokens THEN input_tokens-cache_read_tokens-cache_creation_tokens
      WHEN input_token_semantics=0 AND input_tokens>=cache_read_tokens THEN input_tokens-cache_read_tokens
      ELSE input_tokens END),0), COALESCE(SUM(output_tokens),0),COALESCE(SUM(cache_read_tokens),0),COALESCE(SUM(cache_creation_tokens),0)
      FROM proxy_request_logs WHERE app_type='codex' AND created_at>=? AND created_at<?''',
      (int(start.timestamp()),int((start+timedelta(days=1)).timestamp()))).fetchone()
    assert c.execute("SELECT COUNT(*) FROM usage_daily_rollups WHERE app_type='codex' AND date=?",(day,)).fetchone()[0]==0
actual=usage.read_today(db,now)
count,fresh,output,cached,created=row
assert actual['request_count']==count
assert actual['total_tokens']==fresh+output+cached+created
assert actual['input_tokens']==fresh+cached+created
out=root/'Codex-Temp/ccswitch-hover-20261014';out.mkdir(parents=True,exist_ok=True)
(out/'live-usage.json').write_text(json.dumps(actual,ensure_ascii=False,indent=2),encoding='utf-8')
(out/'live-parity.json').write_text(json.dumps({'result':'PASS','scope':'CC Switch v3.20.3 / Codex / local day / all providers',
  'date':day,'request_count':count,'real_total_tokens':fresh+output+cached+created,'cached_tokens':cached+created,
  'method':'read-only production adapter compared with independent CC Switch summary arithmetic'},ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'result':'PASS','date':day,'today_tokens':actual['total_tokens'],'requests':count}))
