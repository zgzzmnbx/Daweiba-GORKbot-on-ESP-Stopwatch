import asyncio

import pytest

from companion import speech_cache as cache
from companion.control import Controller
from companion.voice import VoiceError
from test_companion import FakeVoice, FakeRobot, wav_bytes


PROFILE={'route':'cloud','voice':'Cherry','model':'qwen3-tts-flash','region':'beijing',
         'speed':1.0,'sample_rate':24000,'voice_protocol':'0.3.3'}
TEXT='风险检查已开始。'


@pytest.fixture(autouse=True)
def isolated_cache(tmp_path,monkeypatch):
    monkeypatch.setattr(cache,'cache_dir',lambda:tmp_path/'audio')


def test_exact_text_and_every_synthesis_parameter_are_separate():
    audio=wav_bytes(24000)
    cache.save(TEXT,PROFILE,audio)
    assert cache.read(TEXT,PROFILE)==audio
    assert cache.read(TEXT+' ',PROFILE) is None
    for name,value in [('voice','Ethan'),('model','another-model'),('region','singapore'),
                       ('speed',1.2),('sample_rate',16000),('voice_protocol','next')]:
        assert cache.read(TEXT,{**PROFILE,name:value}) is None


@pytest.mark.parametrize('text',['含税金额 12345.67 元','发现 2 项风险','发现两项风险','总额一万元'])
def test_rendered_business_values_reuse_exact_audio(text):
    assert cache.cacheable_text(text)
    cache.save(text,PROFILE,wav_bytes(24000))
    assert cache.read(text,PROFILE)==wav_bytes(24000)
    assert cache.read(text+'。',PROFILE) is None


def test_unresolved_template_cannot_be_cached():
    text='{risk_count}项'
    assert not cache.cacheable_text(text)
    with pytest.raises(ValueError):
        cache.save(text,PROFILE,wav_bytes(24000))
    assert not cache.cache_dir().exists()


def test_valid_pc_audio_is_reusable_without_changing_watch_playback_limits():
    audio=wav_bytes(24000,frames=240001)
    cache.save('含税总额 12345.67 元，风险 2 项。',PROFILE,audio)
    assert cache.read('含税总额 12345.67 元，风险 2 项。',PROFILE)==audio
    from companion.robot import read_wav
    with pytest.raises(ValueError):read_wav(audio)


def test_corrupt_or_malformed_cache_is_a_miss_and_can_be_repaired():
    cache.save(TEXT,PROFILE,wav_bytes(24000))
    root=cache.cache_dir();key=cache.key_for(TEXT,PROFILE)
    (root/(key+'.wav')).write_bytes(b'broken')
    assert cache.read(TEXT,PROFILE) is None
    cache.save(TEXT,PROFILE,wav_bytes(24000))
    (root/(key+'.json')).write_text('[]')
    assert cache.read(TEXT,PROFILE) is None
    cache.save(TEXT,PROFILE,wav_bytes(24000))
    assert cache.read(TEXT,PROFILE)==wav_bytes(24000)
    assert not list(root.glob('*.tmp'))
    assert TEXT not in (root/(key+'.json')).read_text()


class Voice(FakeVoice):
    def __init__(self):
        super().__init__();self.calls=[];self.block=None
    async def capabilities(self):
        return {'cloud':{'tts_model':PROFILE['model'],'region':'beijing','default_voice':'Cherry','request_voice':True}}
    async def health(self):
        return {'ready':True,'version':'0.3.3'}
    async def synthesize(self,text,*args):
        self.calls.append(text)
        if self.block:await self.block.wait()
        return wav_bytes(24000)


def controller():
    c=Controller(Voice(),FakeRobot())
    c.owner=c.voice_owner='owner';c.voice.session='session';c.turn=1
    c.routing={'tts':'cloud','allow_text_upload':True}
    c.speech={'cloud_voice':'Cherry','speed':1.0,'request_voice':True}
    return c


def test_amount_and_count_reuse_survives_restart_but_changed_content_is_fresh():
    async def run():
        c=controller()
        await c.fixed_speech(TEXT,lambda:True)
        await c.fixed_speech(TEXT,lambda:True)
        assert c.voice.calls==[TEXT] and c.fixed_speech_hits==1
        newer=controller()
        await newer.fixed_speech(TEXT,lambda:True)
        assert not newer.voice.calls
        for _ in range(2):await newer.fixed_speech('发现 2 项风险，含税金额 12345.67 元。',lambda:True)
        assert len(newer.voice.calls)==1
        assert len(list(cache.cache_dir().glob('*.wav')))==2
        await newer.fixed_speech('发现 3 项风险，含税金额 12345.67 元。',lambda:True)
        await newer.fixed_speech('发现 2 项风险，含税金额 12346.67 元。',lambda:True)
        assert len(newer.voice.calls)==3
        newer.speech['cloud_voice']='Ethan'
        await newer.fixed_speech(TEXT,lambda:True)
        assert len(newer.voice.calls)==4
    asyncio.run(run())


def test_cached_only_miss_and_revoked_permission_do_not_synthesize():
    async def run():
        c=controller()
        with pytest.raises(VoiceError):await c.fixed_speech(TEXT,lambda:True,cached_only=True)
        assert not c.voice.calls
        await c.fixed_speech(TEXT,lambda:True)
        c.routing['allow_text_upload']=False
        with pytest.raises(VoiceError):await c.fixed_speech(TEXT,lambda:True)
        assert len(c.voice.calls)==1
        c.routing['allow_text_upload']=True;c.voice_owner='other'
        with pytest.raises(VoiceError):await c.fixed_speech(TEXT,lambda:True)
        assert len(c.voice.calls)==1
    asyncio.run(run())


def test_generation_change_discards_late_audio_without_persisting():
    async def run():
        c=controller();c.voice.block=asyncio.Event()
        task=asyncio.create_task(c.fixed_speech(TEXT,lambda:True))
        while not c.voice.calls:await asyncio.sleep(0)
        c.generation+=1;c.voice.block.set()
        with pytest.raises(VoiceError):await task
        assert not cache.cache_dir().exists() and not c.pending
    asyncio.run(run())


def test_warmup_synthesizes_without_playing_and_skips_existing_audio():
    async def run():
        c=controller();initial=c.character.copy()
        entries=[('fixed','risk',TEXT)]
        assert await c.warm_fixed_speech(entries)==['fixed']
        assert await c.warm_fixed_speech(entries)==[]
        assert len(c.voice.calls)==1 and c.character==initial
        assert c.fixed_speech_warmup['state']=='ready'
        assert await c.warm_fixed_speech(entries,force=True)==['fixed']
        assert len(c.voice.calls)==2
    asyncio.run(run())
