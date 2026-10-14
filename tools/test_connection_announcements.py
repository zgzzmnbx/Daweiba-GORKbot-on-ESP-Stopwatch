"""Run production cue scheduling and SoundControl against bounded I2S/BLE stubs."""
from pathlib import Path
import json
import shutil
import subprocess
import wave
import struct
import re
from test_motion_native import IMAGE

ROOT = Path(__file__).resolve().parents[1]
FW = ROOT / '03-Src/stopwatch-grok-avatar'
OUT = ROOT / 'Codex-Temp/connection-voice-v01110/native'

BLE = r'''
#pragma once
#include <cstdint>
#include <cstddef>
struct esp_ble_gatts_cb_param_t {struct Write {uint16_t conn_id=1,len=0,offset=0;bool is_prep=false;uint8_t* value=nullptr;} write;};
struct BLECharacteristicCallbacks;
struct BLECharacteristic {static constexpr int PROPERTY_WRITE=1,PROPERTY_READ=2,PROPERTY_NOTIFY=4;void setAccessPermissions(int){}void setCallbacks(BLECharacteristicCallbacks*){}template<class T>void addDescriptor(T*){}};
struct BLECharacteristicCallbacks {virtual void onWrite(BLECharacteristic*,esp_ble_gatts_cb_param_t*){}};
struct BLEService {BLECharacteristic c;BLECharacteristic* createCharacteristic(const char*,int){return &c;}void start(){}};
struct BLEServer {BLEService s;BLEService* createService(const char*){return &s;}};
constexpr int ESP_GATT_PERM_WRITE_ENCRYPTED=1,ESP_GATT_PERM_READ_ENCRYPTED=2;
using portMUX_TYPE=int;
#define portMUX_INITIALIZER_UNLOCKED 0
#define portENTER_CRITICAL(p) ((void)0)
#define portEXIT_CRITICAL(p) ((void)0)
'''
M5 = r'''
#pragma once
#include <cstdint>
#include <cstddef>
struct Button {bool clicked=false,down=false;bool wasClicked(){return clicked;}bool wasPressed(){return down;}};
struct SpeakerStub {bool playing=false,ok=true;int calls=0;const int16_t* pcm=nullptr;size_t samples=0;bool isPlaying(){return playing;}bool playRaw(const int16_t* p,size_t n,int rate,bool,int,int,bool){++calls;pcm=p;samples=n;playing=ok;return ok&&rate==16000;}};
struct M5Stub {Button BtnA,BtnB;SpeakerStub Speaker;};
inline M5Stub M5;
'''
CONTROL = r'''
#pragma once
#include "BLEDevice.h"
struct BLEControl {bool trusted=false;uint32_t epoch=1;int notifications=0;uint32_t linkEpoch(){return epoch;}uint16_t connectionId(){return 1;}bool audioPeerAllowed(int){return trusted;}bool sendNotification(BLECharacteristic*,const uint8_t*,size_t){++notifications;return true;}};
'''
TEST = r'''
#include <cassert>
#include <iostream>
#include "M5Unified.h"
#include "ble_stub.h"
#include "sound_control.h"
#include "speaker_output.h"
#include "connection_announcements.h"
#include "connection_voice.h"
inline bool driverOk=true;
inline SpeakerGainProfile usedGain=SpeakerGainProfile::Unity;
SpeakerStartResult startStopWatchSpeaker(uint8_t,SpeakerGainProfile gain){usedGain=gain;return driverOk?SpeakerStartResult::Ok:SpeakerStartResult::Driver;}
void stopStopWatchSpeaker(){M5.Speaker.playing=false;}
const char* speakerStartResultText(SpeakerStartResult){return "test";}
BLEControl bleControl;
SoundControl soundControl(bleControl);
ConnectionAnnouncements connectionAnnouncements;
ConnectionAnnouncements::Cue activeConnectionCue=ConnectionAnnouncements::None;
uint32_t connectionSoundStopEpoch=0;
struct NetworkControl {bool joined=false;bool wifiJoined(){return joined;}} networkControl;
struct AudioProbe {bool occupied=false,waiting=false;bool busy(){return occupied;}bool preparing(uint32_t){return waiting;}} audioProbe;
enum class PanelPage {Settings,Audio};
bool menuOpen=false,menuToggleLatched=false;
PanelPage panelPage=PanelPage::Settings;
void tick(uint32_t nowMs){INTEGRATION}
void reset(){soundControl.stopNow(false);soundControl.setInitialVolume(75);connectionAnnouncements=ConnectionAnnouncements{};connectionSoundStopEpoch=soundControl.stopEpoch();bleControl.trusted=false;bleControl.notifications=0;networkControl.joined=false;audioProbe.occupied=audioProbe.waiting=false;M5.BtnA.clicked=M5.BtnB.down=false;M5.Speaker.ok=driverOk=true;menuOpen=false;}
void command(uint8_t op,uint16_t id,uint8_t arg=0){uint8_t p[9]={1,op,uint8_t(id),uint8_t(id>>8),0,0,0,0,arg};esp_ble_gatts_cb_param_t params;params.write.len=9;params.write.value=p;soundControl.onWrite(nullptr,&params);}
int main(){
 using A=ConnectionAnnouncements;
 reset();tick(0);tick(1000);assert(!soundControl.isPlaying());
 // Actual Wi-Fi join does not depend on a PC or TLS session.
 networkControl.joined=true;tick(1100);tick(1399);assert(!soundControl.isPlaying());tick(1400);
 assert(soundControl.isAnnouncing()&&M5.Speaker.pcm==gork_connection_voice::kWifi&&usedGain==SpeakerGainProfile::Unity);
 assert(bleControl.notifications==0);int plays=M5.Speaker.calls;tick(1500);assert(M5.Speaker.calls==plays);
 M5.Speaker.playing=false;tick(3000);tick(3100);assert(!soundControl.isPlaying());tick(3500);assert(M5.Speaker.calls==plays);
 // Connected-but-untrusted BLE must be silent; trust establishes a new event.
 bleControl.trusted=false;tick(3600);assert(M5.Speaker.calls==plays);bleControl.trusted=true;tick(3700);tick(4000);
 assert(soundControl.isAnnouncing()&&M5.Speaker.pcm==gork_connection_voice::kBle);
 assert(bleControl.notifications==0);
 // An ongoing recording/preparation immediately preempts a cue.
 audioProbe.waiting=true;tick(4001);assert(!soundControl.isPlaying());audioProbe.waiting=false;tick(4500);assert(!soundControl.isPlaying());
 // Link loss cancels pending speech; a reconnect gets one new announcement.
 reset();networkControl.joined=true;tick(0);networkControl.joined=false;tick(100);tick(500);assert(!soundControl.isPlaying());networkControl.joined=true;tick(600);tick(900);assert(soundControl.isAnnouncing());networkControl.joined=false;tick(901);assert(!soundControl.isPlaying());
 // Dual links are serialized and completing the first preserves the second.
 reset();networkControl.joined=bleControl.trusted=true;tick(1);tick(301);assert(M5.Speaker.pcm==gork_connection_voice::kWifi);
 M5.Speaker.playing=false;tick(2000);tick(2100);assert(soundControl.isAnnouncing()&&M5.Speaker.pcm==gork_connection_voice::kBle);
 // Blue stop also drops the other pending cue. No terminal id=0 BLE spam.
 M5.BtnB.down=true;tick(2101);M5.BtnB.down=false;tick(2400);assert(!soundControl.isPlaying()&&bleControl.notifications==0);
 // Mute consumes success, unmuting never replays it.
 reset();soundControl.setInitialVolume(0);networkControl.joined=true;tick(0);tick(400);soundControl.setLocalVolume(75);tick(500);assert(!soundControl.isPlaying());
 // Busy dialogues defer only within ten seconds; stale success is dropped.
 reset();networkControl.joined=true;audioProbe.occupied=true;tick(0);tick(500);assert(!soundControl.isPlaying());audioProbe.occupied=false;tick(1000);assert(soundControl.isAnnouncing());
 reset();networkControl.joined=true;audioProbe.occupied=true;tick(0);tick(10001);audioProbe.occupied=false;tick(11000);assert(!soundControl.isPlaying());
 // New physical input consumes pending announcements before starting a mic.
 reset();networkControl.joined=true;tick(0);M5.BtnA.clicked=true;tick(299);M5.BtnA.clicked=false;tick(1000);assert(!soundControl.isPlaying());
 // Remote sound commands retain their IDs/catalog and have speaker priority.
 reset();bleControl.trusted=true;networkControl.joined=true;tick(0);tick(300);command(3,7,2);tick(301);
 assert(soundControl.isPlaying()&&!soundControl.isAnnouncing()&&usedGain==SpeakerGainProfile::BuiltInLoud);
 command(4,8);tick(302);tick(1000);assert(!soundControl.isPlaying());
 // Failed speaker startup does not retry once a second.
 reset();networkControl.joined=true;driverOk=false;tick(0);tick(300);driverOk=true;tick(301);tick(2000);assert(!soundControl.isPlaying());
 // Epoch change is a new BLE connection, even if the loss was between polls.
 reset();bleControl.trusted=true;tick(0);tick(300);soundControl.stopNow(false);++bleControl.epoch;tick(400);tick(700);assert(soundControl.isAnnouncing());
 // Unsigned millis wrap preserves stability and expiration bounds.
 A scheduler;assert(scheduler.update(0xfffffff0,true,false,1,false,false,false,false)==A::None);
 assert(scheduler.update(0x120,true,false,1,false,false,false,false)==A::Wifi);
 assert(scheduler.update(0x121,true,false,1,false,false,false,false)==A::None);
 std::cout<<"PASS production main-loop cues + SoundControl: truth/trust/debounce/dedup/reconnect/dual/mute/cancel/busy/expiry/priority/failure/wrap\n";
}
'''


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for name in ('sound_control.h', 'speaker_output.h', 'connection_announcements.h', 'connection_voice.h', 'builtin_sounds.h'):
        shutil.copy2(FW / 'src' / name, OUT / name)
    (OUT / 'sound_control.cpp').write_text((FW / 'src/sound_control.cpp').read_text(encoding='utf-8').replace('#include "ble_control.h"', '#include "ble_stub.h"'), encoding='utf-8')
    (OUT / 'BLEDevice.h').write_text(BLE, encoding='utf-8')
    (OUT / 'BLE2902.h').write_text('#pragma once\nstruct BLE2902 {void setAccessPermissions(int){}};\n', encoding='utf-8')
    (OUT / 'M5Unified.h').write_text(M5, encoding='utf-8')
    (OUT / 'ble_stub.h').write_text(CONTROL, encoding='utf-8')
    main_source = (FW / 'src/main.cpp').read_text(encoding='utf-8')
    integration = main_source.split('  const bool connectionAudioBlocked =', 1)[1].split('  uint8_t changedVolume =', 1)[0]
    (OUT / 'test.cpp').write_text(TEST.replace('INTEGRATION', '  const bool connectionAudioBlocked =' + integration), encoding='utf-8')
    mount = ['docker', 'run', '--rm', '--network', 'none', '-v', f'{OUT}:/work', '-w', '/work', '--entrypoint']
    result = subprocess.run(mount + ['g++', IMAGE, '-std=c++17', '-O2', '-Wall', '-I.', 'test.cpp', 'sound_control.cpp', '-o', 'test'], capture_output=True, text=True)
    (OUT / 'compile.log').write_text(result.stdout+result.stderr, encoding='utf-8')
    if result.returncode:
        raise RuntimeError(result.stderr[-4000:])
    result = subprocess.run(mount + ['/work/test', IMAGE], capture_output=True, text=True)
    (OUT / 'result.log').write_text(result.stdout+result.stderr, encoding='utf-8')
    print(result.stdout+result.stderr)
    if result.returncode:
        raise RuntimeError('Production connection cue regression failed')
    # Check baked samples against the original cloud WAV and declared gain.
    entries = json.loads((FW / 'assets/connection-voice/source.json').read_text(encoding='utf-8'))
    header = (FW / 'src/connection_voice.h').read_text(encoding='utf-8')
    for entry, name in zip(entries, ('Wifi', 'Ble')):
        with wave.open(str(FW / 'assets/connection-voice' / entry['source']), 'rb') as wav:
            assert (wav.getnchannels(), wav.getsampwidth(), wav.getframerate()) == (1, 2, 16000)
            raw = wav.readframes(wav.getnframes())
        original = struct.unpack('<'+'h'*(len(raw)//2), raw)
        pcm = list(map(int, re.search(r'k'+name+r'\[\] = \{(.*?)\};', header, re.S).group(1).replace('\n','').split(',')))
        assert len(pcm) == len(original) == entry['samples']
        gain = min(3., 30000 / max(abs(v) for v in original))
        assert pcm == [round(v*gain) for v in original] and max(abs(v) for v in pcm) <= 30000
    print('PASS Qwen source WAV/header exact samples, PCM16/16k/mono, peak <=30000; no new cloud request')


if __name__ == '__main__':
    main()
