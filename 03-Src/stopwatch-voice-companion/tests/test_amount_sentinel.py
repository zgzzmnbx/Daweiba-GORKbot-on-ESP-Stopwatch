import asyncio
import copy
from types import SimpleNamespace

import pytest

from companion.cost import monitor_events, monitor_amount
from companion.control import Controller
from companion.task_monitor import TaskMonitor, _stage_event
from companion.voice import VoiceError
from test_companion import FakeRobot, FakeVoice, wav_bytes
import companion.task_monitor as monitor_module


def event():
    return dict(event_id='a'*32,task_id='tsk_'+'b'*24,task_name='当前任务',
                attempt='attempt-1',stage='match_result',status='completed',review_rows=2,
                amount_summary=dict(value='123456.780000',currency='CNY',unit='yuan',
                                    basis='tax_included',attempt='attempt-1',calculation_status='recalculated'))


def test_amount_keeps_exact_decimal_attempt_basis_unit_and_strips_private_fields():
    raw=event();raw['amount_summary']['private']='never forward'
    sanitized=monitor_events({'events':[raw]})[0]
    assert sanitized['amount_summary']['value']=='123456.780000'
    assert 'private' not in sanitized['amount_summary']
    result=_stage_event(sanitized)
    assert result[1]=='匹配完成，含税总额123456.78元。2项待复核。'
    assert result[4]=='匹配完成，含税总额123456.78元。请复核。'
    assert result[5:] == ('dynamic_amount','含税总额123456.78元')
    raw['amount_summary']['basis']='tax_excluded'
    raw['amount_summary']['calculation_status']='unconfirmed'
    result=_stage_event(monitor_events({'events':[raw]})[0])
    assert '表内不含税金额123456.78元。公式重算未确认。' in result[4]


@pytest.mark.parametrize('field,value',[
    ('value',float('nan')),('value','NaN'),('value',True),('value','-1'),
    ('value','1e8'),('value','1000000000001'),('value','1.1234567'),
    ('unit','wan'),('currency','USD'),('basis','unknown'),('attempt','old-attempt'),
    ('calculation_status','unknown')])
def test_unknown_or_wrong_attempt_amount_never_spoken(field,value):
    raw=event();raw['amount_summary'][field]=value
    assert monitor_amount(raw['amount_summary'],raw['attempt']) is None
    sanitized=monitor_events({'events':[raw]})[0]
    assert 'amount_summary' not in sanitized
    assert len(_stage_event(sanitized))==5


def test_failed_nonmatch_and_zero_amount_contract():
    raw=event();raw['status']='failed'
    assert 'amount_summary' not in monitor_events({'events':[raw]})[0]
    assert '总额' not in _stage_event(raw)[4]
    raw=event();raw['stage']='report_generated'
    assert 'amount_summary' not in monitor_events({'events':[raw]})[0]
    raw=event();raw['amount_summary']['value']='0.00';raw['review_rows']=0
    assert _stage_event(monitor_events({'events':[raw]})[0])[4]=='匹配完成，含税总额0元。'


def test_dynamic_pc_and_watch_share_one_tts_and_keep_exact_voice_text(monkeypatch):
    monkeypatch.setattr(monitor_module,'_fixed_wav',lambda _:pytest.fail('dynamic amount cannot use fixed cache'))
    monkeypatch.setattr(monitor_module,'_pc_dynamic_speech',lambda audio,guard:'completed_by_os' if guard() else 'suppressed')
    class Robot(FakeRobot):
        async def auto_notify(self,expression,text,guard):
            self.notice=text;return 'accepted'
        async def auto_speech(self,audio,text,guard,expression=None):
            self.wav=audio;self.notice=text;return 'device_playback_completed'
    class Control:
        def __init__(self):self.robot=Robot();self.calls=[]
        def auto_available(self):return True
        async def synthesize_auto_speech(self,text,guard):self.calls.append(text);return wav_bytes()
        def stop_auto_tone(self):pass
    async def run():
        for output in ('pc','watch'):
            c=Control();m=TaskMonitor(None,c);m.enabled=True;m.target='both';m.sound=True;m.sound_target=output
            raw=monitor_events({'events':[event()]})[0]
            assert await m._notify_locked(0,raw,_stage_event(raw))
            assert c.calls==['匹配完成，含税总额123456.78元。请复核。']
            assert c.robot.notice=='含税总额123456.78元'
            assert m.history[0]['amount_summary']['attempt']=='attempt-1'
            assert m.history[0]['delivery']['sound'] in ('completed_by_os','device_playback_completed')
    asyncio.run(run())


def test_dynamic_failures_and_late_result_do_not_play(monkeypatch):
    monkeypatch.setattr(monitor_module,'_pc_dynamic_speech',lambda *args:pytest.fail('late result played'))
    class Control:
        def auto_available(self):return True
        async def synthesize_auto_speech(self,text,guard):
            raise VoiceError(403,'UPLOAD_NOT_ALLOWED','not granted')
        def stop_auto_tone(self):pass
    async def run():
        c=Control();m=TaskMonitor(None,c);m.enabled=True;m.sound=True;m.sound_target='pc';m.target='desktop'
        raw=monitor_events({'events':[event()]})[0]
        await m._notify_locked(0,raw,_stage_event(raw))
        assert m.history[0]['delivery']['sound']=='upload_not_allowed'
        async def late(text,guard):m.epoch+=1;return wav_bytes()
        c.synthesize_auto_speech=late
        assert not await m._notify_locked(0,raw,_stage_event(raw))
        assert len(m.history)==1
    asyncio.run(run())


def test_controller_auto_tts_uses_existing_session_voice_and_manual_cancel():
    class Voice(FakeVoice):
        def __init__(self):super().__init__();self.calls=[]
        async def synthesize(self,text,turn,request,speech=None):
            self.calls.append((text,turn,request,speech));return wav_bytes()
    async def run():
        voice=Voice();control=Controller(voice,FakeRobot());control.owner=control.voice_owner='human';voice.session='existing'
        control.turn=4;control.speech={'cloud_voice':'Ethan','speaker_id':3,'speed':1.0}
        control.routing=dict(tts='cloud',asr='cloud',allow_audio_upload=True,allow_text_upload=True)
        before=(control.phase,control.generation,control.turn,control.text)
        assert await control.synthesize_auto_speech('含税总额1元',lambda:True)==wav_bytes()
        assert voice.calls[0][1]==4 and voice.calls[0][3]['cloud_voice']=='Ethan'
        assert before==(control.phase,control.generation,control.turn,control.text) and not control.pending
        control.routing['allow_text_upload']=False
        with pytest.raises(VoiceError,match='上传许可'):await control.synthesize_auto_speech('1元',lambda:True)
        assert len(voice.calls)==1
        control.routing['allow_text_upload']=True
        started=asyncio.Event()
        async def delayed(*args):started.set();await asyncio.Event().wait()
        voice.synthesize=delayed
        task=asyncio.create_task(control.synthesize_auto_speech('2元',lambda:True));await started.wait();task.cancel()
        with pytest.raises(asyncio.CancelledError):await task
        assert not control.pending and voice.cancelled
    asyncio.run(run())
