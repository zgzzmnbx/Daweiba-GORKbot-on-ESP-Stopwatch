"""Isolated loopback Gork fixture. No hardware, cloud or speaker access."""
import asyncio
from pathlib import Path
import sys
import uuid

ROOT=Path(__file__).resolve().parents[1]
MODULE=ROOT/'03-Src/stopwatch-voice-companion'
sys.path[:0]=[str(MODULE),str(MODULE/'tests')]
import uvicorn
from companion.app import create_app
from companion.control import Controller
from companion.external import ClientRegistry, ClientPolicy
from companion.external_setup import provision
import companion.external as module
from test_companion import FakeRobot, FakeVoice, wav_bytes

WORK=ROOT/'Codex-Temp/external-integration'
WORK.mkdir(parents=True,exist_ok=True)
registry=WORK/'external-clients.local.json'
provision('astra',WORK/'client.external.local.json',registry_path=registry,enable=True)
ClientRegistry(registry).save_client('astra',ClientPolicy(label='Astra 联调替身',enabled=True,speech_targets=['pc','watch'],max_priority=5))
for file in ('sentinel.local.json','codex.local.json'):
    (WORK/file).write_text('{"enabled":false}',encoding='utf-8')
class Robot(FakeRobot):
    async def auto_notify(self,expression,text,guard):
        if not guard():return 'suppressed'
        self.events.append({'expression':expression,'text':text,'fixture':True})
        return 'accepted'
    async def auto_speech(self,audio,text,guard,expression=None):
        if not guard():return 'suppressed'
        self.events.append({'audio_bytes':len(audio),'text':text,'fixture':True})
        return 'device_playback_completed'

voice=FakeVoice();voice.session='fixture-session'
control=Controller(voice,Robot());control.owner=control.voice_owner=str(uuid.uuid4());control.routing.update(tts='cloud',allow_text_upload=True)
control.speech={'cloud_voice':'Ethan','speaker_id':3,'speed':1.0}
module._pc_dynamic_speech=lambda audio,guard:'completed_by_os' if guard() else 'suppressed'
config={'port':8782,'auto_connect_voice':False,'auto_connect_device':False,
        'external_clients_path':str(registry),'external_receipts_path':str(WORK/'external-notifications.local.sqlite3'),
        'sentinel_state_path':str(WORK/'sentinel.local.json'),'codex_state_path':str(WORK/'codex.local.json'),
        'motion_state_path':str(WORK/'motion.local.json'),'motion_library_path':str(WORK/'motion-library.local.json')}
app=create_app(config,controller=control)
@app.get('/api/fixture/output')
async def fixture_output():return {'fixture':True,'hardware':False,'cloud':False,'speaker':False,'outputs':control.robot.events,'character':control.desktop_state()['character']}
print('Isolated Gork fixture at http://127.0.0.1:8782; no physical outputs',flush=True)
uvicorn.run(app,host='127.0.0.1',port=8782,log_level='warning',access_log=False)
