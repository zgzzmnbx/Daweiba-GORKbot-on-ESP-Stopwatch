import asyncio
from fastapi.testclient import TestClient

from companion.app import create_app
from companion.codex_source import QuotaRPC
from companion.quota_usage import QuotaUsage


class Monitor:
    bucket_id = ''
    def state(self):
        return {'enabled': False, 'quota_status': 'disabled',
                'quota': {'status': 'unknown', 'buckets': {}, 'stale': True}}


def payload(reset=2000):
    return {'rateLimitsByLimitId': {'codex': {'limitName': 'Codex',
            'primary': {'usedPercent': 23.4, 'windowDurationMins': 10080, 'resetsAt': reset}}}}


def test_disabled_monitor_read_coalesced_cached_expired_and_failure():
    class RPC:
        calls = 0
        error = None
        async def read(self):
            self.calls += 1
            await asyncio.sleep(0)
            if self.error:
                raise RuntimeError(self.error)
            return payload()
    now=[1000];clock=[0];rpc=RPC();monitor=Monitor()
    service=QuotaUsage(rpc,monitor,clock=lambda:now[0],monotonic=lambda:clock[0])
    async def run():
        first,second=await asyncio.gather(service.get(),service.get())
        assert first==second and rpc.calls==1
        assert first['buckets']['codex']['windows'][0]['remaining_percent']==76.6
        assert len(first['buckets']['codex']['windows'])==1
        assert not monitor.state()['enabled']
        await service.get();assert rpc.calls==1
        clock[0]=121;rpc.error='private secret path'
        stale=await service.get()
        assert stale['status']=='unavailable' and stale['stale'] and stale['buckets']
        assert 'private' not in str(stale)
        clock[0]=152;rpc.error='not_logged_in'
        assert (await service.get())['buckets']=={}
        clock[0]=183;rpc.error=None;now[0]=2100
        expired=await service.get()
        assert expired['stale'] and expired['buckets']
        await service.get();assert rpc.calls==4,'expired server result backs off rather than hot-looping'
    asyncio.run(run())


def test_fresh_sentinel_reused_then_standalone_refresh_when_disabled():
    class RPC:
        async def read(self):
            return payload()
    monitor=Monitor();state=monitor.state()
    state.update(enabled=True,quota_status='available')
    state['quota']={'status':'available','buckets':{'shared':{'name':'Shared','windows':[]}},'stale':False,'sampled_at':''}
    monitor.state=lambda:state
    rpc=RPC();service=QuotaUsage(rpc,monitor,clock=lambda:1000)
    async def run():
        assert 'shared' in (await service.get())['buckets']
        state['enabled']=False
        assert 'codex' in (await service.get())['buckets']
    asyncio.run(run())


def test_actual_quota_endpoint_is_readonly_and_does_not_enable_sentinel(tmp_path,monkeypatch):
    calls=[]
    async def read(self,timeout=12):
        calls.append(True)
        return payload(9999999999)
    monkeypatch.setattr(QuotaRPC,'read',read)
    app=create_app({'port':8766,'answer_state_path':tmp_path/'answer.local.json'})
    client=TestClient(app,base_url='http://127.0.0.1:8766')
    try:
        value=client.get('/api/desktop/quota-usage').json()
        assert value['source']=='codex_official' and value['status']=='available'
        assert not app.state.codex_monitor.enabled
        assert value['buckets']['codex']['windows'][0]['duration_minutes']==10080
        assert len(calls)==1
    finally:
        client.close()


def test_transport_failure_has_safe_explanation_and_recovers_after_backoff():
    class RPC:
        fails=True
        async def read(self):
            if self.fails:raise RuntimeError('rpc_network')
            return payload()
    clock=[0];rpc=RPC();service=QuotaUsage(rpc,Monitor(),clock=lambda:1000,monotonic=lambda:clock[0])
    async def run():
        failed=await service.get()
        assert failed['status']=='network_error' and failed['buckets']=={} and failed['stale']
        rpc.fails=False;clock[0]=31
        restored=await service.get()
        assert restored['status']=='available' and not restored['stale']
    asyncio.run(run())
