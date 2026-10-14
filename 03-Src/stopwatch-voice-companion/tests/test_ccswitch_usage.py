import asyncio
from contextlib import closing
from datetime import datetime, timedelta
import sqlite3

from fastapi.testclient import TestClient
from companion.ccswitch_usage import BEIJING, CCSwitchUsage, read_today
from companion.app import create_app

NOW = datetime(2026, 10, 14, 12, tzinfo=BEIJING)


def database(tmp_path):
    path = tmp_path / 'cc-switch.db'
    with closing(sqlite3.connect(path)) as c, c:
        c.executescript('''CREATE TABLE proxy_request_logs (
          request_id TEXT PRIMARY KEY,app_type TEXT,model TEXT,data_source TEXT,
          status_code INTEGER,created_at INTEGER,input_tokens INTEGER,output_tokens INTEGER,
          cache_read_tokens INTEGER,cache_creation_tokens INTEGER,input_token_semantics INTEGER);
          CREATE TABLE usage_daily_rollups (date TEXT,app_type TEXT,request_count INTEGER,
          input_tokens INTEGER,output_tokens INTEGER,cache_read_tokens INTEGER,
          cache_creation_tokens INTEGER,input_token_semantics INTEGER);
          CREATE TABLE providers (secret TEXT); INSERT INTO providers VALUES ('must-not-leak');''')
    return path


def insert(path, name, input=1000, output=100, cached=600, created=0, semantics=0,
           source='codex_session', at=NOW, app='codex', model='gpt-test', status=200):
    with closing(sqlite3.connect(path)) as c, c:
        c.execute('INSERT INTO proxy_request_logs VALUES (?,?,?,?,?,?,?,?,?,?,?)',
                  (name, app, model, source, status, int(at.timestamp()), input, output, cached, created, semantics))


def test_cache_semantics_match_ccswitch_real_total_without_double_counting(tmp_path):
    p = database(tmp_path)
    insert(p, 'legacy')
    insert(p, 'total', semantics=1, created=200)
    insert(p, 'fresh', input=200, semantics=2, created=200)
    result = read_today(p, NOW)
    assert result['total_tokens'] == 3300
    assert result['fresh_input_tokens'] == 800
    assert result['input_tokens'] == 3000
    assert result['output_tokens'] == 300
    assert result['cache_tokens'] == 2200
    assert result['request_count'] == 3
    assert 'must-not-leak' not in str(result)


def test_session_proxy_dedup_matches_upstream_even_across_midnight(tmp_path):
    p = database(tmp_path)
    midnight = NOW.replace(hour=0)
    insert(p, 'session', at=midnight+timedelta(seconds=5), created=0)
    insert(p, 'proxy', source=None, at=midnight-timedelta(seconds=5), created=100)
    insert(p, 'other', model='different', at=midnight+timedelta(minutes=30))
    result = read_today(p, NOW)
    assert result['request_count'] == 1
    assert result['total_tokens'] == 1100


def test_failed_proxy_does_not_shadow_session_and_unknown_model_does(tmp_path):
    p = database(tmp_path)
    insert(p, 'session')
    insert(p, 'failed-proxy', source='proxy', status=500)
    assert read_today(p, NOW)['request_count'] == 2
    insert(p, 'proxy', source='proxy', model='unknown')
    assert read_today(p, NOW)['request_count'] == 2  # Session filtered, both proxy rows retained.


def test_today_boundaries_other_apps_and_rollup_are_correct(tmp_path):
    p = database(tmp_path)
    start=NOW.replace(hour=0)
    insert(p, 'yesterday', at=start-timedelta(seconds=1))
    insert(p, 'start', at=start)
    insert(p, 'last', at=start+timedelta(days=1,seconds=-1))
    insert(p, 'tomorrow', at=start+timedelta(days=1))
    insert(p, 'claude', app='claude')
    with sqlite3.connect(p) as c:
        c.execute('INSERT INTO usage_daily_rollups VALUES (?,?,?,?,?,?,?,?)', ('2026-10-14','codex',2,100,50,600,200,2))
        c.execute('INSERT INTO usage_daily_rollups VALUES (?,?,?,?,?,?,?,?)', ('2026-10-13','codex',99,999,0,0,0,2))
    result = read_today(p, NOW)
    assert result['request_count'] == 4
    assert result['total_tokens'] == 3150


def test_empty_missing_and_unknown_schema_or_semantics_never_fake_zero(tmp_path):
    p = database(tmp_path)
    assert read_today(p, NOW)['total_tokens'] == 0
    missing = tmp_path/'missing.db'
    assert read_today(missing, NOW)['status'] == 'missing'
    assert not missing.exists()
    insert(p, 'new-semantics', semantics=3)
    assert read_today(p, NOW)['total_tokens'] is None
    with sqlite3.connect(p) as c:
        c.execute('DROP TABLE usage_daily_rollups')
    assert read_today(p, NOW)['status'] == 'unsupported'


def test_adapter_is_readonly_and_observes_live_wal_without_checkpoints(tmp_path):
    p = database(tmp_path)
    writer = sqlite3.connect(p)
    writer.execute('PRAGMA journal_mode=WAL')
    writer.execute('INSERT INTO proxy_request_logs VALUES (?,?,?,?,?,?,?,?,?,?,?)',
                   ('live','codex','gpt-test','codex_session',200,int(NOW.timestamp()),1000,100,600,0,0))
    writer.commit()
    before = p.read_bytes()
    assert read_today(p, NOW)['total_tokens'] == 1100
    assert p.read_bytes() == before
    assert writer.execute('SELECT COUNT(*) FROM providers').fetchone()[0] == 1
    writer.close()


def test_cache_coalesces_reads_fails_safely_and_clears_yesterday(tmp_path):
    p = database(tmp_path)
    insert(p, 'one')
    now=[NOW];clock=[0]
    service=CCSwitchUsage(p,now=lambda:now[0],monotonic=lambda:clock[0])
    async def run():
        first, second = await asyncio.gather(service.get(),service.get())
        assert first == second
        insert(p,'two')
        assert (await service.get())['total_tokens'] == 1100
        clock[0]=21
        assert (await service.get())['total_tokens'] == 2200
        p.unlink();clock[0]=42
        stale=await service.get()
        assert stale['stale'] and stale['total_tokens'] == 2200
        now[0]+=timedelta(days=1)
        next_day=await service.get()
        assert next_day['total_tokens'] is None and next_day['date']=='2026-10-15'
    asyncio.run(run())


def test_busy_corrupt_database_returns_safe_state_without_paths(tmp_path):
    p = database(tmp_path)
    writer=sqlite3.connect(p);writer.execute('BEGIN EXCLUSIVE')
    service=CCSwitchUsage(p,now=lambda:NOW)
    result=asyncio.run(service.get())
    assert result['status']=='unavailable' and result['total_tokens'] is None
    assert str(p) not in str(result)
    writer.close();p.write_bytes(b'corrupt')
    assert asyncio.run(CCSwitchUsage(p,now=lambda:NOW).get())['status']=='unavailable'


def test_loopback_endpoint_uses_only_configured_fixture_and_returns_aggregates(tmp_path):
    p=database(tmp_path)
    # Use today's date because the endpoint uses its own clock.
    insert(p,'today',at=datetime.now(BEIJING))
    app=create_app({'port':8766,'ccswitch_db_path':str(p),'answer_state_path':tmp_path/'answer.local.json'})
    client=TestClient(app,base_url='http://127.0.0.1:8766')
    try:
        # Do not enter lifespan: this isolated GET needs no voice/device startup.
        result=client.get('/api/desktop/token-usage').json()
        assert result['total_tokens']==1100
        assert set(result)<= {'date','timezone','source','scope','status','stale','sampled_at','total_tokens',
                             'input_tokens','fresh_input_tokens','output_tokens','cache_tokens','request_count','last_event_at'}
    finally:
        client.close()
