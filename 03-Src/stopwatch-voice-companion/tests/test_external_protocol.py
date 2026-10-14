import asyncio
from datetime import datetime, timezone, timedelta
import hashlib
import json
import time
import uuid

import pytest
from fastapi.testclient import TestClient
from companion.app import create_app
from companion.control import Controller
from companion.external import ClientRegistry, ExternalNotifications, Notification, Heartbeat, ClientPolicy
from companion.external_setup import provision
from companion.voice import VoiceError
from test_companion import FakeRobot, FakeVoice, wav_bytes


def notice(**changes):
    data=dict(protocol_version='1.0',source='astra',event_id=uuid.uuid4().hex,task_id='task',attempt='attempt',
              stage='anything',sequence=1,occurred_at=datetime.now(timezone.utc).isoformat(),display_target='desktop',
              expression='working',text='正在处理')
    data.update(changes)
    return Notification(**data)


class Robot(FakeRobot):
    async def auto_notify(self, expression, text, guard):
        self.events.append(('notice', expression, text));return 'accepted' if guard() else 'suppressed'
    async def auto_speech(self, audio, text, guard, expression=None):
        self.events.append(('speech',text));return 'device_playback_completed' if guard() else 'suppressed'


def system(tmp_path):
    registry=ClientRegistry(tmp_path/'registry.json')
    registry.save_client('astra',ClientPolicy(label='智算',enabled=True,display_targets=['desktop','watch'],speech_targets=['pc','watch'],max_priority=5),create=True)
    control=Controller(FakeVoice(),Robot());control.owner=control.voice_owner='human';control.voice.session='current'
    control.routing.update(tts='cloud',allow_text_upload=True)
    external=ExternalNotifications(control,registry,tmp_path/'receipts.sqlite3');control.external_notifications=external
    return control,external


async def settled(external):
    tasks=list(external.tasks.values())
    if tasks:await asyncio.wait_for(asyncio.gather(*tasks,return_exceptions=True),3)


def test_idempotent_delivery_conflicts_stale_and_source_scope(tmp_path):
    async def run():
        c,e=system(tmp_path);p=notice();r,status=await e.accept('astra',p);assert status==202
        await settled(e)
        assert e.read('astra',p.event_id)['status']=='completed'
        assert c.desktop_state()['character']['bubble']=='正在处理'
        r,status=await e.accept('astra',p);assert status==200 and r['duplicate']
        with pytest.raises(VoiceError) as caught:await e.accept('astra',p.model_copy(update={'text':'changed'}))
        assert caught.value.code=='EXTERNAL_EVENT_CONFLICT'
        with pytest.raises(VoiceError) as caught:await e.accept('astra',notice(sequence=1))
        assert caught.value.code=='EXTERNAL_EVENT_SUPERSEDED'
        with pytest.raises(VoiceError):await e.accept('other',notice(sequence=2))
        with pytest.raises(VoiceError):e.read('other',p.event_id)
        await e.close()
    asyncio.run(run())


def test_new_stage_cancels_queued_old_and_cancel_tombstone(tmp_path):
    async def run():
        c,e=system(tmp_path);c.manual_until=time.monotonic()+10
        old=notice();await e.accept('astra',old);await asyncio.sleep(.01)
        new=notice(sequence=2,expression='happy');await e.accept('astra',new)
        assert e.read('astra',old.event_id)['status']=='cancelled'
        c.manual_until=0;await settled(e)
        assert c.desktop_state()['character']['expression']=='happy'
        await e.cancel_task('astra','task','attempt')
        with pytest.raises(VoiceError) as caught:await e.accept('astra',notice(sequence=3))
        assert caught.value.code=='EXTERNAL_TASK_CANCELLED'
        await e.accept('astra',notice(sequence=3,attempt='new'));await settled(e)
        await e.close()
    asyncio.run(run())


def test_active_speech_not_interrupted_by_stage_or_priority_and_manual_wins(tmp_path,monkeypatch):
    async def run():
        c,e=system(tmp_path);started=asyncio.Event();release=asyncio.Event();calls=[]
        async def synth(text,guard):
            calls.append(text);started.set();await release.wait();return wav_bytes()
        c.synthesize_auto_speech=synth
        monkeypatch.setattr('companion.external._pc_dynamic_speech',lambda data,guard:'completed_by_os' if guard() else 'suppressed')
        old=notice(speech={'text':'旧阶段'});await e.accept('astra',old);await started.wait()
        newer=notice(sequence=2,priority=4,text='失败',speech={'text':'新阶段'})
        await e.accept('astra',newer)
        assert e.read('astra',old.event_id)['status']=='dispatching'
        assert c.desktop_state()['character']['bubble']=='失败'
        assert calls==['旧阶段']
        release.set();await settled(e);assert calls==['旧阶段','新阶段']
        assert e.read('astra',old.event_id)['delivery']['speech']=='completed_by_os'
        assert e.read('astra',newer.event_id)['delivery']['speech']=='completed_by_os'
        await c.play_character('human','happy','once','desktop')
        assert not e.leases and not e.paused
        assert c.desktop_state()['character']['expression']=='happy'
        await e.close()
    asyncio.run(run())


def test_state_heartbeat_expiry_partial_and_no_revival(tmp_path):
    async def run():
        c,e=system(tmp_path);e.start()
        p=notice(kind='state',lease_ms=1000,display_target='both')
        async def offline(*args):return 'offline'
        c.robot.auto_notify=offline
        await e.accept('astra',p);await settled(e)
        assert e.read('astra',p.event_id)['status']=='partial'
        heartbeat=Heartbeat(event_id=p.event_id,task_id='task',attempt='attempt')
        before=e.leases[('astra',p.event_id)]['until']
        await e.heartbeat('astra',heartbeat)
        assert e.leases[('astra',p.event_id)]['until']>=before
        e.leases[('astra',p.event_id)]['until']=0;await asyncio.sleep(.15)
        assert e.read('astra',p.event_id)['status']=='expired'
        with pytest.raises(VoiceError):await e.heartbeat('astra',heartbeat)
        await e.close()
    asyncio.run(run())


def test_permissions_rechecked_current_output_and_no_secret_list(tmp_path):
    async def run():
        c,e=system(tmp_path)
        e.registry.save_client('astra',ClientPolicy(label='智算',enabled=True,display_targets=['desktop'],speech_targets=['pc'],max_priority=2))
        assert 'token_sha256' not in str(e.registry.public_clients())
        for p in (notice(priority=3),notice(display_target='both')):
            with pytest.raises(VoiceError):await e.accept('astra',p)
        c.manual_until=time.monotonic()+10
        p=notice(speech={'text':'不会播放'})
        await e.accept('astra',p);c.output_target='watch';c.manual_until=0;await settled(e)
        assert e.read('astra',p.event_id)['error']=='EXTERNAL_OUTPUT_DENIED'
        await e.close()
    asyncio.run(run())


def test_restart_no_replay_and_global_stop_pauses_ordinary_stop_does_not(tmp_path):
    async def run():
        c,e=system(tmp_path);c.manual_until=time.monotonic()+10;p=notice();await e.accept('astra',p)
        # Simulate an interrupted process's persisted queued row separately.
        row=e.read('astra',p.event_id);await e.close()
        import sqlite3
        db=sqlite3.connect(e.path);db.execute('UPDATE notices SET record=?',(json.dumps(row),));db.commit();db.close()
        new=ExternalNotifications(c,e.registry,e.path);c.external_notifications=new
        assert new.read('astra',p.event_id)['status']=='interrupted' and not new.tasks
        await c.stop('human',1);assert not new.paused
        await c.desktop_stop();assert new.paused
        with pytest.raises(VoiceError):await new.accept('astra',notice(sequence=2))
        new.paused=False;c.manual_until=0;await new.accept('astra',notice(sequence=2));await settled(new)
        await new.close()
    asyncio.run(run())


def test_expired_validation_and_unknown_fields_do_not_expose_secrets(tmp_path):
    async def run():
        c,e=system(tmp_path)
        with pytest.raises(VoiceError) as caught:await e.accept('astra',notice(occurred_at=(datetime.now(timezone.utc)-timedelta(seconds=31)).isoformat()))
        assert caught.value.code=='EXTERNAL_EVENT_EXPIRED'
        await e.close()
    asyncio.run(run())
    for data in ({'text': 'x'*301},{'sequence':True},{'occurred_at':'2026-01-01T00:00:00'},{'extra':'secret'},{'expression':'does-not-exist'}):
        with pytest.raises(ValueError):notice(**data)


def test_http_registration_scope_host_origin_and_mutual_exclusion(tmp_path):
    c=Controller(FakeVoice(),Robot());owner=str(uuid.uuid4());c.owner=owner
    app=create_app(dict(external_clients_path=str(tmp_path/'registry.json'),external_receipts_path=str(tmp_path/'receipts.sqlite3'),
                        sentinel_state_path=str(tmp_path/'sentinel.json'),codex_state_path=str(tmp_path/'codex.json'),
                        motion_state_path=str(tmp_path/'motion.json'),motion_library_path=str(tmp_path/'library.json')),controller=c)
    with TestClient(app,base_url='http://127.0.0.1:8766') as http:
        headers={'X-Companion-Client':owner}
        assert http.get('/api/external/capabilities').status_code==200
        assert http.post('/api/external/clients',json={'source':'astra','label':'智算'}).status_code==401
        created=http.post('/api/external/clients',headers=headers,json={'source':'astra','label':'智算','enabled':True,'display_targets':['desktop']}).json()
        token=created['token'];auth={'Authorization':'Bearer '+token}
        p=notice().model_dump()
        assert http.post('/api/external/notifications',headers=auth,json=p).status_code==202
        assert http.get('/api/external/notifications/'+p['event_id'],headers=auth).status_code==200
        assert token not in http.get('/api/external/overview',headers=headers).text
        assert http.get('/api/external/status',headers=auth).json()['policy']['speech_targets']==[]
        assert http.get('/api/external/status',headers={**auth,'Origin':'http://evil.invalid'}).status_code==403
        assert http.get('/api/external/status',headers={**auth,'Host':'evil.invalid'}).status_code==403
        assert http.post('/api/external/notifications',headers=auth,json={**p,'secret':token}).status_code==422
        assert token not in http.post('/api/external/notifications',headers=auth,json={**p,'secret':token}).text
        assert http.put('/api/cost/sentinel',headers=headers,json={'enabled':True,'source':'astra','mode':'auto','target':'desktop','sound':False}).status_code==409
        assert http.put('/api/external/clients/astra',headers=headers,json={'label':'智算','enabled':False}).status_code==200
        assert http.get('/api/external/status',headers=auth).status_code==403


def test_private_provision_preserves_existing_and_requires_explicit_rotate(tmp_path):
    path=tmp_path/'token.external.local.json';registry=tmp_path/'registry.json'
    assert provision('astra',path,registry_path=registry)['enabled'] is False
    original=path.read_text();provision('astra',path,registry_path=registry)
    assert path.read_text()==original
    with pytest.raises((ValueError,OSError)):provision('astra',tmp_path/'missing.json',registry_path=registry)
    provision('astra',path,registry_path=registry,rotate=True)
    assert path.read_text()!=original and 'token' not in ClientRegistry(registry).public_clients()[0]

def test_different_task_notices_queue_for_display_duration_without_hiding_active_voice(tmp_path,monkeypatch):
    async def run():
        c,e=system(tmp_path);e.start();calls=[]
        monkeypatch.setattr('companion.external._pc_dynamic_speech',lambda data,guard:'completed_by_os')
        p=notice(task_id='one',duration_ms=500);q=notice(task_id='two',duration_ms=500)
        await e.accept('astra',p);await settled(e)
        await e.accept('astra',q);await asyncio.sleep(.05)
        assert e.read('astra',q.event_id)['status']=='queued'
        assert c.desktop_state()['character']['bubble']==p.text
        await settled(e)
        assert e.read('astra',q.event_id)['status']=='completed'
        await e.close()
    asyncio.run(run())

def test_concurrent_new_stages_keep_latest_and_cancel_before_start_frees_queue(tmp_path):
    async def run():
        c,e=system(tmp_path);c.manual_until=time.monotonic()+10
        for sequence in range(1,12):
            p=notice(sequence=sequence)
            await e.accept('astra',p)
            assert len(e.tasks)<=1
        await asyncio.gather(e.accept('astra',notice(sequence=12)),e.accept('astra',notice(sequence=13)))
        c.manual_until=0;await settled(e)
        rows=e.history();latest=next(row for row in rows if row['request']['sequence']==13)
        assert latest['status']=='completed'
        assert all(row['status']=='cancelled' for row in rows if row['request']['sequence']<13)
        await e.close()
    asyncio.run(run())
