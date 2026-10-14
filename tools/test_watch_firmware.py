"""Run production avatar and recorder C++ with bounded hardware substitutes."""
from pathlib import Path
import shutil
import subprocess
from test_motion_native import STUB, IMAGE
from test_motion_refresh import function

ROOT=Path(__file__).resolve().parents[1]
FW=ROOT/'03-Src/stopwatch-grok-avatar/src'
OUT=ROOT/'Codex-Temp/watch-v0116/native'

EXTRA=r'''
#include <string>
#include <cstring>
#include <cstdio>
#include <cstdlib>
inline uint32_t clockNow=0;
inline uint32_t millis(){return clockNow;}
inline uint32_t micros(){return clockNow*1000;}
inline long random(long a,long){return a;}
inline uint32_t esp_random(){return 123;}
struct SerialStub {template<class... T>void printf(const char*,T...){}void println(const char*){}};
inline SerialStub Serial;
class String:public std::string {public:using std::string::string;String(const std::string& v):std::string(v){}void trim(){auto a=find_first_not_of(" \t\r\n");if(a==npos){clear();return;}*this=substr(a,find_last_not_of(" \t\r\n")-a+1);}void toLowerCase(){for(auto&c:*this)c=tolower(c);}bool startsWith(const char*s)const{return rfind(s,0)==0;}void remove(size_t a,size_t n){erase(a,n);}};
namespace fonts {inline int Font0,efontCN_16;}
constexpr int middle_center=0,top_left=1,TFT_RED=0xf800,TFT_LIGHTGREY=0xc618;
struct ButtonStub {bool pressed=false,clicked=false,released=false,down=false;bool isPressed(){return pressed;}bool wasClicked(){return clicked;}bool wasReleased(){return released;}bool wasPressed(){return down;}bool pressedFor(unsigned){return pressed;}void clear(){clicked=released=down=false;}};
struct MicStub {
 bool running=false,beginOk=true,recordOk=true;unsigned rate=16000,sequence=0,failedCall=0,calls=0;
 struct Slot{int16_t* data;size_t size;};std::vector<Slot> slots;
 bool isEnabled(){return true;}bool isRunning(){return running;}size_t isRecording(){return slots.size();}
 void setSampleRate(unsigned r){rate=r;}bool begin(){running=beginOk;sequence=calls=0;return running;}
 void end(){running=false;slots.clear();}
 bool record(int16_t*b,size_t n,int r,bool){++calls;if(!recordOk||calls==failedCall||slots.size()>=2||r!=int(rate))return false;slots.push_back({b,n});return true;}
 void complete(){if(slots.empty())return;auto s=slots.front();slots.erase(slots.begin());for(size_t i=0;i<s.size;i++)s.data[i]=int16_t(sequence++%30000);}
};
struct SpeakerStub {bool isEnabled(){return true;}bool isPlaying(){return false;}bool playRaw(int16_t*,unsigned,unsigned,bool,int,int,bool){return true;}};
'''

AVATAR=r'''
#include <algorithm>
#include <vector>
#include <string>
#include <cassert>
#include <iostream>
#include "M5Unified.h"
#define private public
#include "avatar_engine.h"
#undef private
#include "custom_expressions.h"
RECEIPT_FUNCTION
int main(){
 AvatarEngine boot,reference;assert(boot.begin());assert(reference.begin());
 assert(!boot.customIdleEnabled_&&!boot.motion_.enabled());
 reference.showFromCommand("legacy idle",0);
 boot.play(ExpressionId::Idle,0,AvatarEngine::PlaybackMode::Loop);
 for(unsigned now=0;now<7000;now+=33){clockNow=now;boot.update(now);auto frame=M5.Display.data;std::fill(M5.Display.data.begin(),M5.Display.data.end(),0);reference.requiresFullClear_=true;reference.update(now);assert(frame==M5.Display.data);M5.Display.data=frame;}
 assert(gork_custom_motion::kCount==3);
 for(size_t i=0;i<gork_custom_motion::kCount;i++){
  auto&e=gork_custom_motion::entries[i];unsigned start=10000+i*20000;
  assert(boot.showFromCommand(e.token,start));assert(boot.motion_.scene()==e.scene);assert(!strcmp(boot.activeName(),e.name));
  assert(!strcmp(boot.activeProtocolName(),e.token));
  char receipt[21];formatBleExpressionReceipt(boot,receipt,sizeof(receipt));
  std::string expected=std::string("OK:")+e.token;for(auto&c:expected)if(c>='a'&&c<='z')c-='a'-'A';
  assert(receipt==expected);assert(expected.size()<=20);
  for(auto c:expected)assert(static_cast<unsigned char>(c)<128);
  assert(!memcmp(boot.motion_.params_,e.scenes,sizeof(e.scenes)));
  for(unsigned now=start;now<start+12000;now+=33){clockNow=now;boot.update(now);}
  assert(!boot.motion_.enabled()&&boot.activeExpression()==ExpressionId::Idle&&!boot.customIdleEnabled_);
  assert(boot.showFromCommand(String("loop ")+e.token,start+13000));
  formatBleExpressionReceipt(boot,receipt,sizeof(receipt));assert(receipt==expected);
  clockNow=start+70000;boot.update(clockNow);assert(boot.motion_.enabled()&&boot.motion_.scene()==e.scene);
  assert(boot.showFromCommand("motion cancel",clockNow));clockNow+=1000;boot.update(clockNow);assert(!boot.motion_.enabled());
 }
 boot.show(ExpressionId::HappyWork,100000);boot.commitSwipe(1,100001);assert(boot.customBrowseIndex_==0);
 boot.next(100002);assert(boot.customBrowseIndex_==1);boot.commitSwipe(1,100003);assert(boot.customBrowseIndex_==2);
 boot.next(100004);assert(boot.customBrowseIndex_==-1&&boot.activeExpression()==ExpressionId::Listening);
 boot.commitSwipe(-1,100005);assert(boot.customBrowseIndex_==2);boot.previous(100006);assert(boot.customBrowseIndex_==1);
 boot.previous(100007);assert(boot.customBrowseIndex_==0);boot.previous(100008);assert(boot.customBrowseIndex_==-1&&boot.activeExpression()==ExpressionId::HappyWork);
 assert(!boot.showFromCommand("cxaaaaaaaaaaaa",110000));assert(!boot.showFromCommand(String("pingpong ")+gork_custom_motion::entries[0].token,110001));
 assert(boot.showFromCommand("idle",110002));char idleReceipt[21];formatBleExpressionReceipt(boot,idleReceipt,sizeof(idleReceipt));assert(!strcmp(idleReceipt,"OK:IDLE"));
 AvatarEngine restarted;assert(restarted.begin());assert(!restarted.motion_.enabled());
 std::cout<<"PASS production AvatarEngine: original idle raster parity, three independent snapshots, once/loop/cancel, swipe and button browsing, unknown token, original restart\n";
}
'''

AUDIO=r'''
#include <algorithm>
#include <vector>
#include <string>
#include <cassert>
#include <iostream>
#include "M5Unified.h"
class BLEControl {public:bool allowed=true;uint32_t linkEpoch(){return 1;}bool audioPeerAllowed(int){return allowed;}int connectionId(){return 1;}};
class NetworkControl {public:bool on=true,connected=true;std::vector<int> events;bool delegated(){return on&&connected;}bool ready(){return connected;}unsigned link(){return 1;}void voiceEvent(int v){events.push_back(v);}};
class SoundControl {public:bool playing=false,announcing=false;unsigned stops=0;bool isPlaying(){return playing;}bool isAnnouncing(){return announcing;}int volume(){return 75;}void stopNow(){playing=announcing=false;++stops;}};
enum class SpeakerGainProfile {BuiltInLoud};enum class SpeakerStartResult{Ok};
inline void stopStopWatchSpeaker(){}inline SpeakerStartResult startStopWatchSpeaker(int,SpeakerGainProfile){return SpeakerStartResult::Ok;}
constexpr int MALLOC_CAP_SPIRAM=0,MALLOC_CAP_8BIT=0;
inline void*heap_caps_calloc(size_t n,size_t s,int){return calloc(n,s);}inline void heap_caps_free(void*p){free(p);}
#define private public
#include "audio_probe.h"
#undef private
#include "audio_timing.h"
constexpr uint32_t kLeaseMs=15000,kBlockSamples=320,kRecordBytes=320000;
constexpr uint16_t kOpusHelloId=0xf00d;
uint16_t get16(const uint8_t*p){return p[0]|uint16_t(p[1])<<8;}uint32_t get32(const uint8_t*p){return get16(p)|uint32_t(get16(p+2))<<16;}
void put16(uint8_t*p,uint16_t v){p[0]=v;p[1]=v>>8;}void put32(uint8_t*p,uint32_t v){put16(p,v);put16(p+2,v>>16);}
struct Event{int op;unsigned value;int flag;};std::vector<Event> replies;
void AudioProbe::reply(uint8_t op,uint16_t,uint32_t v,const uint8_t*p,size_t n){replies.push_back({op,v,n?int(p[0]):-1});}
void AudioProbe::draw(){}bool AudioProbe::decodeOpus(){return false;}
void AudioProbe::onWrite(BLECharacteristic*,esp_ble_gatts_cb_param_t*){}
METHODS
void tick(AudioProbe&a,unsigned now,bool done=true){clockNow=now;if(done)M5.Mic.complete();a.update(now);M5.BtnA.clear();M5.BtnB.clear();}
void click(AudioProbe&a,unsigned now){M5.BtnA.clicked=M5.BtnA.released=true;tick(a,now);assert(a.takeAConsumed());}
void packet(AudioProbe&a,int op,unsigned id,unsigned now){AudioProbe::Packet p;p.link=1;p.size=12;p.bytes[1]=op;put16(p.bytes+2,id);put32(p.bytes+4,op==AudioProbe::Hello?0:a.epoch_);put32(p.bytes+8,op==AudioProbe::Hello?4096:0);clockNow=now;a.process(p,now);}
void begin(AudioProbe&a,unsigned now){click(a,now);packet(a,AudioProbe::Hello,1,now+1);packet(a,AudioProbe::ProductArm,2,now+2);assert(a.state_==gorkaudio::State::Recording&&M5.Mic.running);}
int count(int op){return std::count_if(replies.begin(),replies.end(),[op](auto&e){return e.op==op;});}
int main(){
 BLEControl control;NetworkControl net;AudioProbe a(control);a.setNetworkControl(&net);a.enter(false);a.networkRoute_=true;
 begin(a,10);
 assert(a.recordSecondsLeft(12)==0&&count(AudioProbe::Recording)==0&&M5.Mic.isRecording()==2);
 // Delayed microphone task must never advertise red REC on a queued request.
 tick(a,312,false);assert(a.recordSecondsLeft(312)==0&&count(AudioProbe::Recording)==0);
 tick(a,332);assert(a.recordSecondsLeft(332)==0&&count(AudioProbe::Recording)==0&&M5.Mic.isRecording()==2);
 for(int i=1;i<=23;i++)tick(a,332+i*20);
 assert(a.used_==15360&&a.recordSecondsLeft(792)==0&&count(AudioProbe::Recording)==0);
 tick(a,812);assert(a.used_==16000&&a.recordSecondsLeft(812)>0&&count(AudioProbe::Recording)==1);
 for(int i=1;i<=12;i++)tick(a,812+i*20);assert(a.state_==gorkaudio::State::Recording&&!M5.BtnA.isPressed());
 assert(net.events==std::vector<int>{1});click(a,1080);tick(a,1100);
 assert(a.state_==gorkaudio::State::Captured&&!M5.Mic.running&&count(AudioProbe::Recorded)==1);assert(net.events==std::vector<int>{1});
 for(unsigned i=0;i<a.used_/2;i++)assert(reinterpret_cast<int16_t*>(a.buffer_)[i]==int16_t(i%30000));
 a.leave();a.enter(false);click(a,1000);click(a,1001);packet(a,AudioProbe::Hello,1,1002);packet(a,AudioProbe::ProductArm,2,1003);assert(!M5.Mic.running&&count(AudioProbe::Recorded)==1);
 a.enter(false);click(a,2000);tick(a,8000);packet(a,AudioProbe::Hello,1,8001);packet(a,AudioProbe::ProductArm,2,8002);assert(!M5.Mic.running);
 a.enter(false);begin(a,9000);M5.BtnB.down=true;tick(a,9010);assert(!M5.Mic.running&&count(AudioProbe::Recorded)==1);
 a.enter(false);begin(a,10000);M5.BtnA.pressed=M5.BtnB.pressed=true;tick(a,10010);assert(!M5.Mic.running);M5.BtnA.pressed=M5.BtnB.pressed=false;M5.BtnA.released=M5.BtnB.released=true;tick(a,10011);
 a.enter(false);begin(a,11000);a.leave();assert(!M5.Mic.running&&a.state_==gorkaudio::State::Off);
 a.enter(false);begin(a,12000);net.connected=false;tick(a,12010);assert(!M5.Mic.running);net.connected=true;
 a.enter(false);begin(a,13000);net.on=false;tick(a,13010);assert(!M5.Mic.running);net.on=true;
 a.enter(false);begin(a,14000);tick(a,15003,false);assert(!M5.Mic.running&&a.lastError_==11);
 a.enter(false);begin(a,16000);for(int i=1;i<=500;i++)tick(a,16002+i*20);assert(a.state_==gorkaudio::State::Captured&&a.used_==320000&&!M5.Mic.running&&replies.back().flag==1);
 a.enter(false);begin(a,27000);click(a,27003);tick(a,27023);assert(a.lastError_==6&&!M5.Mic.running);
 a.enter(false);M5.Mic.beginOk=false;click(a,28000);packet(a,AudioProbe::Hello,1,28001);packet(a,AudioProbe::ProductArm,2,28002);assert(a.lastError_==9&&!M5.Mic.running);M5.Mic.beginOk=true;
 a.enter(true);packet(a,AudioProbe::Hello,1,29000);packet(a,AudioProbe::Arm,2,29001);assert(a.state_==gorkaudio::State::Armed);M5.BtnA.pressed=true;tick(a,29002);assert(M5.Mic.running);for(int i=1;i<=6;i++)tick(a,29002+i*20);M5.BtnA.pressed=false;tick(a,29142);tick(a,29162);assert(a.state_==gorkaudio::State::Captured);a.leave();
 // A warm idle HELLO must survive the physical click; no implicit mic start.
 a.enter(false);M5.BtnA.released=true;tick(a,29999);packet(a,AudioProbe::Hello,1,30000);auto warmEpoch=a.epoch_;auto replyCount=replies.size();
 assert(!M5.Mic.running&&!a.buffer_);click(a,30001);
 assert(a.epoch_==warmEpoch&&replies.size()==replyCount&&a.preparing(30001)&&!M5.Mic.running);
 packet(a,AudioProbe::ProductArm,2,30002);assert(M5.Mic.running&&a.state_==gorkaudio::State::Recording);
 M5.BtnB.down=true;tick(a,30003);assert(!M5.Mic.running&&replies.back().flag==AudioProbe::Cancel);
 a.enter(false);packet(a,AudioProbe::Hello,1,31000);click(a,31001);click(a,31002);
 assert(!a.preparing(31002)&&!M5.Mic.running&&replies.back().flag==AudioProbe::Cancel);
 packet(a,AudioProbe::ProductArm,2,31003);assert(!M5.Mic.running);a.leave();
 a.enter(false);packet(a,AudioProbe::Hello,1,32000);a.state_=gorkaudio::State::Playing;a.product_=false;
 click(a,32001);assert(a.state_==gorkaudio::State::Ready&&a.preparing(32001)&&replies.back().flag==AudioProbe::Cancel);
 packet(a,AudioProbe::Hello,1,32002);packet(a,AudioProbe::ProductArm,2,32003);assert(M5.Mic.running);a.leave();
 // Neither a failed second queue nor a stuck cold microphone may show REC.
 a.enter(false);auto before=count(AudioProbe::Recording);M5.Mic.failedCall=2;
 click(a,33000);packet(a,AudioProbe::Hello,1,33001);packet(a,AudioProbe::ProductArm,2,33002);
 assert(a.lastError_==10&&!M5.Mic.running&&count(AudioProbe::Recording)==before);M5.Mic.failedCall=0;
 a.enter(false);begin(a,34000);M5.BtnB.down=true;tick(a,34003,false);
 assert(!M5.Mic.running&&a.recordSecondsLeft(34003)==0&&count(AudioProbe::Recording)==before);
 // Both slots may complete between UI frames: count both, refill without overlap.
 a.enter(false);begin(a,35000);M5.Mic.complete();M5.Mic.complete();tick(a,35042,false);
 assert(a.used_==1280&&M5.Mic.isRecording()==2&&count(AudioProbe::Recording)==before);
 for(unsigned i=0;i<a.used_/2;i++)assert(reinterpret_cast<int16_t*>(a.buffer_)[i]==int16_t(i));a.leave();
 // New answers preempt only connection speech; ordinary short sounds keep
 // their prior busy contract. Cover PCM and Opus BEGIN against production code.
 SoundControl sounds;a.setSoundControl(&sounds);
 for(auto op:{AudioProbe::Begin,AudioProbe::BeginOpus}){
   a.enter(false);packet(a,AudioProbe::Hello,1,36000);sounds.playing=sounds.announcing=true;
   AudioProbe::Packet p;p.link=1;p.size=op==AudioProbe::Begin?16:24;
   p.bytes[1]=op;put16(p.bytes+2,2);put32(p.bytes+4,a.epoch_);put32(p.bytes+8,16000);
   put32(p.bytes+12,3200);if(op==AudioProbe::BeginOpus)put32(p.bytes+16,3200);
   auto stops=sounds.stops;a.process(p,36001);
   assert(!sounds.playing&&sounds.stops==stops+1&&a.state_==gorkaudio::State::Receiving);a.leave();
   a.enter(false);packet(a,AudioProbe::Hello,1,37000);sounds.playing=true;sounds.announcing=false;
   put32(p.bytes+4,a.epoch_);a.process(p,37001);assert(a.lastError_==2&&sounds.playing);sounds.stopNow();a.leave();
 }
 std::cout<<"PASS production AudioProbe: REC waits for 500ms completed PCM, all prefix samples retained, two-slot sample continuity and drain, cold-task delay/failure/cancel, click/start, released capture, click/send, pending cancel/expiry and late Arm, blue/combo/settings, drop/revoke, watchdog, 10s limit, short audio, mic failure, diagnostic hold/release, warm HELLO, PCM/Opus preempt connection speech only\n";
}
'''

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    for name in ('avatar_engine.h','avatar_engine.cpp','grok_bot_catalog.inc','grok_renderer.h','grok_renderer.cpp','grok_geometry.h','motion_scene.h','motion_scene.cpp','motion_config.h','custom_expressions.h','motion_draw.h','motion_draw.cpp','audio_probe.h','product_recorder.h','audio_task_core.h','audio_timing.h'):
        shutil.copyfile(FW/name,OUT/name)
    stub=STUB.replace('struct DisplayStub {',r'''struct DisplayStub {
 void fillRect(int x,int y,int w,int h,uint16_t c){for(int yy=y;yy<y+h;yy++)for(int xx=x;xx<x+w;xx++)pixel(xx,yy,c);}
 void fillScreen(uint16_t c){std::fill(data.begin(),data.end(),c);}
 void drawLine(int x,int y,int a,int b,uint16_t c){drawWideLine(x,y,a,b,1,c);}
 void fillTriangle(int,int,int,int,int,int,uint16_t){}
 void fillRoundRect(int x,int y,int w,int h,int,uint16_t c){fillRect(x,y,w,h,c);}
 void drawRoundRect(int,int,int,int,int,uint16_t){}
 void startWrite(){}void endWrite(){}void setFont(const void*){}void setTextSize(int){}void setTextColor(int,int){}void setTextDatum(int){}void drawString(const char*,int,int){}
''')
    stub=stub.replace('struct M5Stub {DisplayStub Display;};',EXTRA+'\nstruct M5Stub {DisplayStub Display;ButtonStub BtnA,BtnB;MicStub Mic;SpeakerStub Speaker;};')
    (OUT/'M5Unified.h').write_text(stub,encoding='utf-8')
    (OUT/'BLEDevice.h').write_text('''#pragma once
#include <cstdint>
#include <cstddef>
struct esp_ble_gatts_cb_param_t{};
struct BLECharacteristic{};
struct BLEServer{int getPeerMTU(int){return 517;}};
struct BLECharacteristicCallbacks{virtual void onWrite(BLECharacteristic*,esp_ble_gatts_cb_param_t*){}};
using portMUX_TYPE=int;
#define portMUX_INITIALIZER_UNLOCKED 0
#define portENTER_CRITICAL(p) ((void)0)
#define portEXIT_CRITICAL(p) ((void)0)
''',encoding='utf-8')
    source=(FW/'audio_probe.cpp').read_text(encoding='utf-8')
    methods=[]
    for name,signature in (('stop','void AudioProbe::stop()'),('resetQueue','void AudioProbe::resetQueue()'),('allocate','bool AudioProbe::allocate()'),('enter','void AudioProbe::enter(bool testPage)'),('leave','void AudioProbe::leave()'),('ack','void AudioProbe::ack(uint8_t request,uint32_t value)'),('fail','void AudioProbe::fail(uint32_t code)'),('process','void AudioProbe::process(const Packet& packet,uint32_t now)'),('queueRecordBlock','bool AudioProbe::queueRecordBlock()'),('startRecording','void AudioProbe::startRecording()'),('finishRecording','void AudioProbe::finishRecording(bool limited)'),('update','void AudioProbe::update(uint32_t now)')):
        methods.append(signature+function(source,'AudioProbe::'+name+'('))
    receipt='void formatBleExpressionReceipt(const AvatarEngine& avatar, char* status, size_t capacity)'+function((FW/'main.cpp').read_text(encoding='utf-8'),'formatBleExpressionReceipt(')
    (OUT/'avatar_test.cpp').write_text(AVATAR.replace('RECEIPT_FUNCTION',receipt),encoding='utf-8')
    (OUT/'audio_test.cpp').write_text(AUDIO.replace('METHODS','\n'.join(methods)),encoding='utf-8')
    mount=['docker','run','--rm','--network','none','-v',f'{OUT}:/work','-w','/work','--entrypoint']
    logs=[]
    for name,files in (('avatar',['avatar_test.cpp','avatar_engine.cpp','grok_renderer.cpp','motion_scene.cpp','motion_draw.cpp']),('audio',['audio_test.cpp'])):
        compiled=subprocess.run(mount+['g++',IMAGE,'-std=c++17','-O2','-I.',*files,'-o',name],capture_output=True,text=True)
        (OUT/f'{name}-compile.log').write_text(compiled.stdout+compiled.stderr,encoding='utf-8')
        if compiled.returncode:raise RuntimeError(compiled.stderr[-4000:])
        result=subprocess.run(mount+['/work/'+name,IMAGE],capture_output=True,text=True)
        logs.append(result.stdout+result.stderr)
        (OUT/'result.log').write_text(''.join(logs),encoding='utf-8')
        print(logs[-1])
        if result.returncode:raise RuntimeError(f'{name} production regression failed')

if __name__=='__main__':main()
