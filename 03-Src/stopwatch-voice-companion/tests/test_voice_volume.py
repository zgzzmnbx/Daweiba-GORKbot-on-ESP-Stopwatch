from array import array
import asyncio
import io
import uuid
import wave

from fastapi.testclient import TestClient

from companion.app import create_app
from companion.control import Controller
from companion.voice_volume import VoiceVolume, scale_speech_wav
from test_companion import FakeVoice, FakeRobot


def test_pc_gain_scales_pcm_only_and_preserves_wav_format():
    target=io.BytesIO()
    with wave.open(target,'wb') as output:
        output.setparams((1,2,16000,0,'NONE','not compressed'))
        output.writeframes(array('h',[-32768,-1000,0,1000,32767]).tobytes())
    original=target.getvalue()
    for volume,expected in [(0,[0]*5),(50,[-16384,-500,0,500,16384])]:
        with wave.open(io.BytesIO(scale_speech_wav(original,volume)),'rb') as result:
            assert result.getnchannels()==1 and result.getframerate()==16000
            assert list(array('h',result.readframes(5)))==expected
    assert scale_speech_wav(original,100) is original


def test_pc_volume_owner_validation_persistence_and_no_playback(tmp_path):
    control=Controller(FakeVoice(),FakeRobot());owner=str(uuid.uuid4());control.owner=owner
    path=tmp_path/'voice-volume.local.json'
    app=create_app({'voice_volume_path':str(path)},controller=control)
    with TestClient(app,base_url='http://127.0.0.1:8766') as client:
        assert client.get('/api/voice/volume').json()=={'volume':100}
        assert client.put('/api/voice/volume',json={'volume':30}).status_code==401
        headers={'X-Companion-Client':owner}
        for value in [-1,101,True,'40',1.5]:
            assert client.put('/api/voice/volume',headers=headers,json={'volume':value}).status_code==422
        assert client.put('/api/voice/volume',headers=headers,json={'volume':37}).json()=={'volume':37}
        assert VoiceVolume(path).value==37
        assert control.robot.events==[]
        assert control.voice.session is None
        assert control.pc_voice_volume==37


def test_notification_gain_changes_pc_bytes_only_and_keeps_original_for_watch(tmp_path,monkeypatch):
    from test_external_protocol import system, notice, settled
    async def run():
        control,external=system(tmp_path);control.pc_voice_volume=50
        data=io.BytesIO()
        with wave.open(data,'wb') as output:
            output.setparams((1,2,16000,0,'NONE','not compressed'))
            output.writeframes(array('h',[1000,-1000]).tobytes())
        original=data.getvalue();pc,watch=[],[]
        async def synth(*args):return original
        async def on_watch(audio,*args):watch.append(audio);return 'device_playback_completed'
        control.synthesize_auto_speech=synth;control.robot.auto_speech=on_watch
        monkeypatch.setattr('companion.external._pc_dynamic_speech',lambda audio,guard:(pc.append(audio),'completed_by_os')[1])
        await external.accept('astra',notice(sequence=1,speech={'text':'电脑','target':'pc','mode':'tts'}));await settled(external)
        await external.accept('astra',notice(sequence=2,speech={'text':'Watch','target':'watch','mode':'tts'}));await settled(external)
        with wave.open(io.BytesIO(pc[0]),'rb') as result:
            assert list(array('h',result.readframes(2)))==[500,-500]
        assert watch==[original]
        await external.close()
    asyncio.run(run())
