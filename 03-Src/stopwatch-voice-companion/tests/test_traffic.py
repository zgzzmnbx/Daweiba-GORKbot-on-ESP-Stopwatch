import asyncio
import json
import threading
import uuid

from fastapi.testclient import TestClient
from companion.app import create_app
from companion.control import Controller
from companion.traffic import TrafficMonitor
from companion.traffic.accounting import Ledger
from companion.traffic.interfaces import InterfaceRates
from test_companion import FakeVoice, FakeRobot
from test_traffic_accounting import snapshot, connection


def test_interfaces_reset_hotplug_and_sleep_never_spike():
    r = InterfaceRates()
    assert r.ingest({'a': (100, 200)}, 1)['up_speed'] is None
    assert r.ingest({'a': (120, 260)}, 3)['down_speed'] == 30
    v = r.ingest({'a': (1, 2), 'b': (10000, 20000)}, 4)
    assert v['up_speed'] == 0
    assert r.ingest({'b': (10010, 20010)}, 5)['up_speed'] == 10
    assert r.ingest({'b': (500000, 600000)}, 40)['down_speed'] is None
    assert r.ingest({}, 41)['status'] == 'unavailable'


def test_proxy_speed_excludes_direct_and_reset_is_unknown():
    ledger = Ledger(':memory:')
    try:
        ledger.ingest(snapshot(0, 0), now=100)
        ledger.ingest(snapshot(1000, 2000, connection(up=100, down=400),
                               connection('direct', up=900, down=1600, route='DIRECT')), now=102)
        assert ledger.latest['proxy_up_speed'] == 50
        assert ledger.latest['proxy_down_speed'] == 200
        ledger.ingest(snapshot(2000, 5000, connection(up=1000, down=3000)), now=140)
        assert ledger.latest['proxy_down_speed'] is None
        ledger.ingest(snapshot(1, 1), now=103)
        assert ledger.latest['proxy_down_speed'] is None
    finally:
        ledger.close()


def test_disabled_no_collectors_and_stop_discards_late_history(tmp_path):
    async def run():
        entered, release = threading.Event(), threading.Event()
        calls=[]
        def history():
            calls.append('history');entered.set();release.wait(3)
            return {'available': True, 'rows': [{'day':'2026-10-15','app':'private.exe','upload':1,'download':2}]}
        m=TrafficMonitor(tmp_path,clash=lambda:snapshot(0,0),interfaces=lambda:{'a':(0,0)},history=history)
        await m.start();await asyncio.sleep(.01)
        assert calls == []
        await m.configure(True)
        await asyncio.to_thread(entered.wait,2)
        stop=asyncio.create_task(m.configure(False))
        await asyncio.sleep(.02);release.set();await stop
        assert not m.tasks and m.ledger is None
        assert m.history['rows'] == []
        assert not TrafficMonitor(tmp_path).enabled
        assert m.snapshot()['clash']['status']=='disabled'
        await m.close()
    asyncio.run(run())


def test_same_database_cannot_be_sampled_twice(tmp_path):
    async def run():
        opts=dict(clash=lambda:snapshot(0,0),interfaces=lambda:{},history=lambda:{'available':True,'rows':[]})
        first=TrafficMonitor(tmp_path,**opts)
        await first.configure(True)
        second=TrafficMonitor(tmp_path,**opts)
        await second.start()
        assert second.enabled is False and second.ledger is None
        assert first.enabled
        await first.close()
        await second.configure(True)
        assert second.enabled
        await second.close()
    asyncio.run(run())


def test_real_api_owner_and_input_validation_without_voice_or_network(tmp_path):
    control=Controller(FakeVoice(),FakeRobot());control.owner=str(uuid.uuid4())
    app=create_app({'traffic_data_dir':str(tmp_path)},controller=control)
    app.state.traffic.clash_reader=lambda:snapshot(0,0)
    app.state.traffic.interface_reader=lambda:{'test':(1,2)}
    app.state.traffic.history_reader=lambda:{'available':True,'rows':[]}
    with TestClient(app,base_url='http://127.0.0.1:8766') as client:
        assert client.get('/api/traffic').json()['enabled'] is False
        assert client.put('/api/traffic',json={'enabled':True}).status_code==401
        headers={'X-Companion-Client':control.owner}
        for v in [1,'true',None,[]]:
            assert client.put('/api/traffic',headers=headers,json={'enabled':v}).status_code==422
        assert client.put('/api/traffic',headers=headers,json={'enabled':True,'path':'private'}).status_code==422
        assert client.put('/api/traffic',headers=headers,json={'enabled':True}).json()['enabled']
        assert 'processes' not in client.get('/api/traffic').json()
        assert 'processes' in client.get('/api/traffic?details=true').json()
        assert client.put('/api/traffic',headers=headers,json={'enabled':False}).json()['enabled'] is False
        assert control.robot.events==[] and control.voice.session is None


def test_failure_never_exposes_exception_or_fake_zero(tmp_path):
    async def run():
        def fail():raise OSError('secret=PRIVATE; C:/credentials')
        m=TrafficMonitor(tmp_path,clash=fail,interfaces=fail,history=fail)
        await m.configure(True);await asyncio.sleep(.1)
        value=m.snapshot(True)
        assert value['clash']['status']=='unavailable'
        assert value['physical']['down_speed'] is None
        assert 'PRIVATE' not in json.dumps(value)
        await m.close()
    asyncio.run(run())


def test_windows_history_keeps_only_safe_fields_and_does_not_add_to_clash(tmp_path):
    async def run():
        m=TrafficMonitor(tmp_path,clash=lambda:snapshot(0,0),interfaces=lambda:{'a':(0,0)},
            history=lambda:{'available':True,'rows':[
                {'day':'2026-10-15','app':'app.exe','upload':10,'download':30,'identity':'SECRET','network':'HOME'},
                {'day':'2026-10-15','app':'app.exe','upload':20,'download':10}]})
        await m.configure(True);await asyncio.sleep(.1)
        value=m.snapshot(True)
        assert value['history']['rows']==[{'day':'2026-10-15','name':'app.exe','upload':30,'download':40}]
        assert value['clash']['routes']['PROXY']['upload']==0
        assert 'SECRET' not in json.dumps(value) and 'HOME' not in json.dumps(value)
        await m.close()
        assert TrafficMonitor(tmp_path).history['status']=='stale'
    asyncio.run(run())
