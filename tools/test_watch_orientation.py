"""Run the production direction gesture, settings handler and pinned touch transform."""
from pathlib import Path
import shutil
import subprocess
from test_motion_native import IMAGE
from test_motion_refresh import function

ROOT=Path(__file__).resolve().parents[1]
FW=ROOT/'03-Src/stopwatch-grok-avatar/src'
OUT=ROOT/'Codex-Temp/watch-orientation-native'

TEST=r'''
#include <cassert>
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <iostream>
#include "watch_orientation.h"
#include "Button_Class.hpp"
struct touch_point_t{int16_t x=0,y=0;};
struct Panel_Device {
 int _internal_rotation=0,_width=466,_height=466;
 float _affine[6]={1,0,0,0,1,0};
 struct Touch {struct Config{int offset_rotation=0;};Config config(){return {};}};
 Touch* _touch=nullptr;
 void convertRawXY(touch_point_t* tp,uint_fast8_t count);
};
void Panel_Device::convertRawXY(touch_point_t* tp,uint_fast8_t count) TOUCH_TRANSFORM
Panel_Device panel;
struct Detail:touch_point_t{bool down=false,clicked=false;bool isPressed()const{return down;}bool wasPressed()const{return clicked;}};
struct DisplayStub {int rotation=0,clears=0;void setRotation(int r){rotation=r;panel._internal_rotation=r;}void fillScreen(int){++clears;}};
struct TouchStub {Detail raw;Detail getDetail(int){auto result=raw;panel.convertRawXY(&result,1);return result;}};
struct Device {DisplayStub Display;TouchStub Touch;} M5;
struct Settings {
 bool saved=false,fail=false;int writes=0;
 size_t putBool(const char* key,bool value){assert(!strcmp(key,"inverted"));++writes;if(fail)return 0;saved=value;return 1;}
 bool getBool(const char*,bool){return saved;}
}settings;
struct Avatar {
 int invalidations=0,releases=0,tiltClears=0,shakeClears=0;
 void releaseTouch(){++releases;}void releaseSwipe(){++releases;}
 void setTiltTarget(float x,float y){assert(x==0&&y==0);++tiltClears;}
 void setShakeTarget(float x,float y,float z){assert(x==0&&y==0&&z==0);++shakeClears;}
 int baseExpression(){return 0;}void show(int,uint32_t,bool){}
 void invalidate(){++invalidations;}
}avatar;
struct SerialStub{void println(const char*){}}Serial;
gorkorientation::Direction orientation;
gorkorientation::TripleB orientationGesture;
constexpr char kInvertedKey[]="inverted";
constexpr int TFT_BLACK=0,TFT_RED=1;
bool settingsReady=true,menuOpen=false,orientationTouchNeedsRelease=false,orientationSaveFailed=false;
uint32_t orientationTouchUntil=0,orientationHintUntil=0,shakeQuietStartedMs=0,lastBatteryRefreshMs=0;
constexpr uint32_t kBatteryRefreshIntervalMs=5000;
int imuCalibrationCount=30;
float neutralAccelX=1,neutralAccelY=2,filteredAccelX=3,filteredAccelY=4;
float previousAccelX=5,previousAccelY=6,previousAccelZ=7,shakeEnergy=8;
bool shakeReactionActive=true,gestureCommitted=true,forgetNetworkConfirm=false,clearBleBindingConfirm=false;
enum class GestureAxis{None,Horizontal};GestureAxis gestureAxis=GestureAxis::Horizontal;
enum class PanelPage{Settings,Network,Sound,Bluetooth,Hardware,Audio};PanelPage panelPage=PanelPage::Settings;
int redraws=0,vibrations=0,shakeResets=0,brightnessDelta=0;
bool reached(uint32_t now,uint32_t deadline){return deadline&&int32_t(now-deadline)>=0;}
void resetShakeSequence(){++shakeResets;}void startVibration(int,int){++vibrations;}
void drawSettingsFrame(){++redraws;}void drawDiagnosticLine(int,const char*,const char*,int){}
void adjustBrightness(int delta){brightnessDelta+=delta;}void toggleDebugMode(){}
void drawNetworkFrame(){}void drawSoundFrame(){}void drawBluetoothFrame(){}void drawDiagnosticFrame(){}
void drawPanelFrame(const char*){}void drawPanelButton(int,int,int,const char*){}void drawBatteryLine(){}
struct AudioProbe{void enter(){}}audioProbe;
bool orientationTouchBlocked(uint32_t nowMs) TOUCH_BLOCK
bool setInverted(bool inverted,uint32_t nowMs) SET_DIRECTION
void handleSettingsInput(uint32_t nowMs) SETTINGS_INPUT

int main(){
 using gorkorientation::TripleB;
 // Three releases; never browse halfway through a valid triple.
 TripleB triple;assert(!triple.update(100,true,true,true).flip);
 assert(!triple.update(240,true,true,true).flip);auto result=triple.update(380,true,true,true);
 assert(result.flip&&result.browse==0);assert(!triple.update(420,true,true,true).flip);
 TripleB single;single.update(100,true,true,true);assert(single.update(450,true,false,true).browse==0);
 assert(single.update(451,true,false,true).browse==1);
 TripleB two;two.update(100,true,true,true);two.update(200,true,true,true);
 assert(two.update(551,true,false,true).browse==2);
 TripleB delegated;delegated.update(100,true,true,false);delegated.update(200,true,true,false);
 result=delegated.update(300,true,true,false);assert(result.flip&&result.browse==0);
 // Every disqualifying activity clears prior clicks and absorbs a cancel burst.
 for(int activity=0;activity<7;activity++){
  TripleB blocked;blocked.update(100,true,true,true);blocked.update(200,false,false,false);
  for(unsigned time:{230,350,470})assert(!blocked.update(time,true,true,false).flip);
  assert(!blocked.update(900,true,true,false).flip);assert(!blocked.update(1000,true,true,false).flip);
  assert(blocked.update(1100,true,true,false).flip);
 }
 TripleB wrap;wrap.update(UINT32_MAX-100,true,true,true);wrap.update(UINT32_MAX-10,true,true,true);
 assert(wrap.update(90,true,true,true).flip);
 TripleB slow;slow.update(100,true,true,true);assert(slow.update(500,true,true,true).browse==1);
 assert(!slow.update(600,true,true,true).flip);
 TripleB nonidle;assert(nonidle.update(1,false,true,true).browse==1);

 // Exercise the actual pinned M5 button debounce/release implementation too.
 m5::Button_Class physical;TripleB physicalGesture;unsigned presses=0,flips=0;
 for(uint32_t t=0;t<=800;t+=5){
  bool down=(t>=100&&t<160)||(t>=230&&t<290)||(t>=360&&t<420);
  physical.setRawState(t,down);if(physical.wasPressed())++presses;
  if(physicalGesture.update(t,true,physical.wasClicked(),false).flip)++flips;
 }
 assert(presses==3&&flips==1);
 // Production setter writes only its own preference, resets IMU history,
 // applies the full display rotation and refuses a failed persistence write.
 assert(setInverted(true,100));assert(orientation.inverted()&&M5.Display.rotation==2&&settings.saved);
 assert(imuCalibrationCount==0&&neutralAccelX==0&&neutralAccelY==0&&shakeEnergy==0&&!shakeReactionActive);
 assert(previousAccelZ==0&&avatar.tiltClears==1&&avatar.shakeClears==1&&shakeResets==1);
 assert(vibrations==1&&M5.Display.clears==1&&orientationHintUntil==1300);
 gorkorientation::Direction reboot;reboot.setInverted(settings.getBool(kInvertedKey,false));assert(reboot.rotation()==2);
 assert(orientation.axis(.25f)==-.25f&&orientation.axis(-.75f)==.75f);
 for(auto point:{touch_point_t{0,0},touch_point_t{465,465},touch_point_t{325,164},touch_point_t{120,300}}){
  auto mapped=point;panel.convertRawXY(&mapped,1);assert(mapped.x==465-point.x&&mapped.y==465-point.y);
 }
 settings.fail=true;assert(!setInverted(false,300));assert(orientation.inverted()&&M5.Display.rotation==2&&settings.saved&&orientationSaveFailed);
 settings.fail=false;menuOpen=true;assert(setInverted(false,500));assert(redraws==1&&orientationHintUntil==0);
 // Click the real settings hitbox, keep the finger held across the rotation,
 // then release and hit the same control in inverted physical coordinates.
 M5.Touch.raw={};orientationTouchBlocked(800);
 M5.Touch.raw.x=325;M5.Touch.raw.y=164;M5.Touch.raw.down=M5.Touch.raw.clicked=true;
 handleSettingsInput(900);assert(orientation.inverted());auto writes=settings.writes;
 handleSettingsInput(1200);assert(settings.writes==writes);
 M5.Touch.raw.down=M5.Touch.raw.clicked=false;handleSettingsInput(1300);
 M5.Touch.raw.x=140;M5.Touch.raw.y=301;M5.Touch.raw.down=M5.Touch.raw.clicked=true;
 handleSettingsInput(1400);assert(!orientation.inverted()&&!settings.saved&&M5.Display.rotation==0);
 M5.Touch.raw.down=M5.Touch.raw.clicked=false;handleSettingsInput(1700);
 M5.Touch.raw.x=280;M5.Touch.raw.y=200;M5.Touch.raw.down=M5.Touch.raw.clicked=true;
 handleSettingsInput(1800);assert(brightnessDelta==-1);
 std::cout<<"PASS triple/single/double, consumed B, cancel/activity cooldown, slow and wraparound; production settings/persistence failure, rotation, IMU reset, pinned touch transform, held-finger guard and original brightness hitbox\n";
}
'''

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(FW/'watch_orientation.h',OUT/'watch_orientation.h')
    for name in ['Button_Class.hpp','Button_Class.cpp']:
        shutil.copyfile(FW.parent/'.pio/libdeps/m5stack-stopwatch/M5Unified/src/utility'/name,OUT/name)
    source=(FW/'main.cpp').read_text(encoding='utf-8')
    gfx=FW.parent/'.pio/libdeps/m5stack-stopwatch/M5GFX/src/lgfx/v1/panel/Panel_Device.cpp'
    code=TEST.replace('TOUCH_TRANSFORM',function(gfx.read_text(encoding='utf-8'),'void Panel_Device::convertRawXY('))
    for placeholder,name in [('TOUCH_BLOCK','bool orientationTouchBlocked('),('SET_DIRECTION','bool setInverted('),('SETTINGS_INPUT','void handleSettingsInput(')]:
        code=code.replace(placeholder,function(source,name))
    (OUT/'test.cpp').write_text(code,encoding='utf-8')
    mount=['docker','run','--rm','--network','none','-v',f'{OUT}:/work','-w','/work','--entrypoint']
    for name,command in [('compile',mount+['g++',IMAGE,'-std=c++17','-O2','test.cpp','Button_Class.cpp','-o','test']),('result',mount+['/work/test',IMAGE])]:
        result=subprocess.run(command,capture_output=True,text=True,encoding='utf-8',errors='replace')
        (OUT/f'{name}.log').write_text(result.stdout+result.stderr,encoding='utf-8')
        print(result.stdout+result.stderr)
        if result.returncode:raise RuntimeError(f'orientation {name} failed')

if __name__=='__main__':main()
