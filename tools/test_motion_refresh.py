"""Compare production partial-refresh frames with clean reference frames."""
from pathlib import Path
import importlib.util
import os
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
FW = ROOT / "03-Src/stopwatch-grok-avatar/src"
OUT = ROOT / "Codex-Temp/motion-refresh"


def function(source, name):
    start = source.index(name)
    start = source.index("{", start)
    depth = 1
    end = start + 1
    while depth:
        depth += (source[end] == "{") - (source[end] == "}")
        end += 1
    return source[start:end]


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    spec = importlib.util.spec_from_file_location("native", ROOT / "tools/test_motion_native.py")
    native = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(native)
    stub = native.STUB.replace("struct DisplayStub {", "struct DisplayStub {\n unsigned clears=0,hintRects=0;\n void fillRect(int x,int y,int w,int h,uint16_t c){if(x==60&&y==420&&w==346&&h==20)hintRects++;for(int yy=y;yy<y+h;yy++)for(int xx=x;xx<x+w;xx++)pixel(xx,yy,c);}\n void fillScreen(uint16_t c){clears++;std::fill(data.begin(),data.end(),c);}\n void startWrite(){} void endWrite(){} void setFont(const void*){} void setTextSize(int){} void setTextColor(int,int){} void setTextDatum(int){} void drawString(const char*,int,int){}\n")
    stub += "\nnamespace fonts { inline int Font0; }\nconstexpr int middle_center=0,top_left=1,TFT_RED=0xf800,TFT_LIGHTGREY=0xc618;\ninline unsigned micros(){return 0;}\n"
    stub = stub.replace("466", "GORK_EDGE")
    (OUT / "M5Unified.h").write_text(stub, encoding="utf-8")
    for name in ("motion_scene.h", "motion_scene.cpp", "motion_config.h", "motion_draw.h", "motion_draw.cpp", "grok_renderer.h", "grok_renderer.cpp", "grok_geometry.h"):
        shutil.copyfile(FW / name, OUT / name)
    engine = (FW / "avatar_engine.cpp").read_text(encoding="utf-8")
    clear = function(engine, "void AvatarEngine::clearDirtyRect(")
    merge = function(engine, "AvatarEngine::DirtyRect AvatarEngine::mergeRects(")
    invalidate = function(engine, "void AvatarEngine::invalidate(")
    main_source = (FW / "main.cpp").read_text(encoding="utf-8")
    hint = function(main_source, "void renderAvatarWithAudioHint(")
    render = engine[engine.index("void AvatarEngine::render("):]
    render = render[:render.index("  if(previousMotionBounds_.valid)")] + "}\n"
    source = r'''
#include "motion_draw.h"
#include "motion_config.h"
#include <cassert>
#include <iostream>
#include <cstdio>
constexpr uint16_t kBackground=0x2104;
struct AvatarEngine {
 using DirtyRect=GrokRenderer::Bounds;
 MotionScene motion_;MotionDraw motionDraw_;GrokRenderer grokRenderer_;
 DirtyRect previousMotionBounds_{},previousGrokBounds_{},previousLeftBounds_{},previousRightBounds_{},previousHappyWorkBounds_{},previousBubbleBounds_{};
 bool bubbleActive_=false,debugLabelEnabled_=false,requiresFullClear_=false,forceRender_=false;
 unsigned nextFrameUs_=0;
 void updateInteraction(unsigned){} void drawBubble(){} const char* activeName(){return "IDLE";}
 void recordRenderMetrics(unsigned,unsigned,unsigned,const DirtyRect&,int,bool){}
 static DirtyRect mergeRects(const DirtyRect& first,const DirtyRect& second) MERGE
 void clearDirtyRect(const DirtyRect& rect) CLEAR
 void render(uint32_t nowMs);
 void update(uint32_t nowMs){render(nowMs);}
 void invalidate() INVALIDATE
};
RENDER
AvatarEngine avatar;
struct ProbeStub {
  uint8_t left=0;bool active=false,pending=false;
  bool preparing(uint32_t){return pending;}
 uint8_t recordSecondsLeft(uint32_t){return left;}
 bool busy(){return active;}
 const char* message(){return "sending audio";}
} audioProbe;
uint32_t orientationHintUntil=0;bool orientationSaveFailed=false;
struct DirectionStub{bool inverted(){return false;}}orientation;
bool reached(uint32_t now,uint32_t deadline){return deadline&&int32_t(now-deadline)>=0;}
void renderAvatarWithAudioHint(uint32_t nowMs) HINT
int main(){
 AvatarEngine engine;engine.requiresFullClear_=true;engine.motion_.configure(gork_motion_config::scenes,1,2,1);engine.motion_.set(0,0);
 MotionDraw draw;int mismatches=0,switches=0;unsigned long stale=0;int frames=0;
 for(unsigned now=0;now<60000;now+=17){
  // A legacy expression can have larger eyes and a different position. The
  // following motion-idle frame must remove everything it left on screen.
  const bool boundary=now>=30000&&frames%17==0;
  if(boundary){
   GrokRenderer::Frame legacy{};legacy.centerX=M5.Display.width()/2;legacy.centerY=M5.Display.height()/2;legacy.blink=1;
   legacy.leftEye={-55.f,5.f,55.f,90.f,0,0,0,0,0,0,-12.f};
   legacy.rightEye={50.f,-25.f,45.f,105.f,0,0,0,0,0,0,8.f};
   M5.Display.fillScreen(kBackground);engine.grokRenderer_.drawBody();engine.grokRenderer_.draw(legacy);
   engine.previousGrokBounds_=engine.grokRenderer_.bounds(legacy);
   engine.previousLeftBounds_=engine.grokRenderer_.boundsForEye(legacy,true);
   engine.previousRightBounds_=engine.grokRenderer_.boundsForEye(legacy,false);
   engine.previousMotionBounds_={};engine.requiresFullClear_=false;switches++;
   engine.motion_.set((switches-1)%4,now);
  }
  auto pose=engine.motion_.sample(now);auto clears=M5.Display.clears;engine.render(now);
  assert(M5.Display.clears-clears==unsigned(boundary||frames==0));
  auto partial=M5.Display.data;M5.Display.fillScreen(kBackground);engine.grokRenderer_.drawBody();draw.draw(pose);
  unsigned extra=0;for(size_t i=0;i<partial.size();i++)if(partial[i]!=M5.Display.data[i])extra++;
  if(extra){mismatches++;stale+=extra;}
  M5.Display.data=partial;frames++;
 }
 std::cout<<"frames="<<frames<<" legacy_to_motion="<<switches<<" mismatched="<<mismatches<<" stale_pixels="<<stale<<"\n";
 // Run the actual main-loop overlay helper against production drawing and
 // invalidate code. Busy and REC both end; their first idle frame must equal
 // a clean scene, and later idle frames must keep partial refresh.
 avatar.requiresFullClear_=true;avatar.motion_.configure(gork_motion_config::scenes,1,2,1);avatar.motion_.set(2,0,true);
 unsigned hints=0,hiddenTransitions=0;
 for(unsigned now=0;now<4000;now+=20){
  audioProbe.active=now>=1000&&now<1400;
  audioProbe.pending=now>=1980&&now<2000;
  audioProbe.left=now>=2000&&now<2400?5:0;
  const bool active=audioProbe.active||audioProbe.pending||audioProbe.left;
  const bool ended=now==1400||now==2400;
  auto clears=M5.Display.clears;auto strips=M5.Display.hintRects;
  renderAvatarWithAudioHint(now);
  if(now==1980||now==2000)assert(M5.Display.hintRects==strips+1); // both transitions bypass the 200ms same-state throttle
  assert(M5.Display.clears-clears==unsigned(now==0||ended));
  if(!active)assert(M5.Display.hintRects==strips);
  else if(M5.Display.hintRects>strips){hints++;assert(M5.Display.data[430*GORK_EDGE+233]==TFT_BLACK);}
  auto partial=M5.Display.data;M5.Display.fillScreen(kBackground);avatar.grokRenderer_.drawBody();draw.draw(avatar.motion_.sample(now));
  if(!active){assert(partial==M5.Display.data);if(ended)hiddenTransitions++;}
  M5.Display.data=partial;
 }
 assert(hints==5&&hiddenTransitions==2);
 std::cout<<"audio_hint_frames=200 active_rects="<<hints<<" restored_transitions="<<hiddenTransitions<<" idle_strip_writes=0\n";
 return mismatches?1:0;
}
'''.replace("MERGE", merge).replace("CLEAR", clear).replace("RENDER", render).replace("INVALIDATE", invalidate).replace("HINT", hint)
    (OUT / "test.cpp").write_text(source, encoding="utf-8")
    image = os.environ.get("GORK_NATIVE_IMAGE", native.IMAGE)
    command = ["docker", "run", "--rm", "--network", "none", "-v", f"{OUT}:/work", "-w", "/work", "--entrypoint"]
    logs = []
    for edge in (466, 468):
        compiled = subprocess.run(command + ["g++", image, "-std=c++17", "-O2", f"-DGORK_EDGE={edge}", "-I.", "test.cpp", "motion_scene.cpp", "motion_draw.cpp", "grok_renderer.cpp", "-o", "test"], capture_output=True, text=True)
        if compiled.returncode:
            raise RuntimeError(compiled.stderr)
        result = subprocess.run(command + ["/work/test", image], capture_output=True, text=True)
        log = f"{edge}px: " + result.stdout + result.stderr
        print(log)
        logs.append(log)
        (OUT / "result.log").write_text("".join(logs), encoding="utf-8")
        if result.returncode:
            raise RuntimeError("production partial-refresh residual pixels")


if __name__ == "__main__":
    main()
