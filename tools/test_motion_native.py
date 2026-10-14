"""Compile and run actual portable Watch C++ with a bounded display raster substitute."""
import json
import os
from pathlib import Path
import shutil
import subprocess

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'Codex-Temp/motion-native'
IMAGE=os.environ.get('GORK_NATIVE_IMAGE','weknora-bundle/docreader:v0.8.2-3c36e7e7')
FW=ROOT/'03-Src/stopwatch-grok-avatar/src'

STUB=r'''
#pragma once
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <vector>
#define TFT_WHITE 65535
#define TFT_BLACK 0
struct DisplayStub {
 std::vector<uint16_t> data=std::vector<uint16_t>(466*466,0);
 int width(){return 466;}int height(){return 466;}
 uint16_t color565(int r,int g,int b){return ((r>>3)<<11)|((g>>2)<<5)|(b>>3);}
 void pixel(int x,int y,uint16_t c){if(x>=0&&x<466&&y>=0&&y<466)data[y*466+x]=c;}
 void drawFastHLine(int x,int y,int w,uint16_t c){for(int i=0;i<w;i++)pixel(x+i,y,c);}
 void fillCircle(int x,int y,int r,uint16_t c){for(int yy=y-r;yy<=y+r;yy++)for(int xx=x-r;xx<=x+r;xx++)if((xx-x)*(xx-x)+(yy-y)*(yy-y)<=r*r)pixel(xx,yy,c);}
 void drawWideLine(float x0,float y0,float x1,float y1,float r,uint16_t c){float dx=x1-x0,dy=y1-y0,l=dx*dx+dy*dy;int xmin=floorf(std::min(x0,x1)-r),xmax=ceilf(std::max(x0,x1)+r),ymin=floorf(std::min(y0,y1)-r),ymax=ceilf(std::max(y0,y1)+r);
  for(int y=ymin;y<=ymax;y++)for(int x=xmin;x<=xmax;x++){float t=l?std::max(0.f,std::min(1.f,((x-x0)*dx+(y-y0)*dy)/l)):0;if(std::hypot(x-x0-t*dx,y-y0-t*dy)<=r)pixel(x,y,c);}}
};
struct M5Stub {DisplayStub Display;};
inline M5Stub M5;
'''

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    for name in ('motion_scene.h','motion_scene.cpp','motion_config.h','motion_draw.h','motion_draw.cpp','grok_renderer.h','grok_geometry.h'):
        shutil.copyfile(FW/name,OUT/name)
    (OUT/'M5Unified.h').write_text(STUB,encoding='utf-8')
    names=['eyeAlpha','spinner','paper','question','pen','ink','bob','questionScale','questionY','penX','penY','penRotation','leftAngle','rightAngle','spinAngle','spinX','spinY','spinScale','writeX','writeY','writeScale','penSize','strokeWidth','qX','qY','qSize','penStyle']
    printing='for(int i=0;i<10;i++)std::cout<<p.eyes[i]<<",";'+''.join(f'std::cout<<p.{name}<<",";' for name in names)
    source=r'''
#include "motion_draw.h"
#include "motion_config.h"
#include <cassert>
#include <chrono>
#include <cstring>
#include <fstream>
#include <iostream>
#include <limits>
int main(){
 MotionScene model;assert(model.configure(gork_motion_config::scenes,1,2,1));
 assert(!model.configure(gork_motion_config::scenes,2,2,1));assert(!model.configure(gork_motion_config::scenes,1,1,1));
 MotionParams bad[4];memcpy(bad,gork_motion_config::scenes,sizeof(bad));bad[0].eyes[0]=std::numeric_limits<float>::quiet_NaN();assert(!model.configure(bad,1,2,2));
 memcpy(bad,gork_motion_config::scenes,sizeof(bad));bad[2].props[5]=1.5f;assert(!model.configure(bad,1,2,2));
 assert(!model.set(4,0));MotionDraw draw;int frames=0;double maxRadius=0;auto start=std::chrono::steady_clock::now();
 for(int mode=0;mode<4;mode++)for(int pen=0;pen<4;pen++){
  MotionParams config[4];memcpy(config,mode==1?gork_motion_config::minimum:mode==2?gork_motion_config::maximum:gork_motion_config::scenes,sizeof(config));
  if(mode==3)for(int n=0;n<4;n++){for(int k=0;k<10;k++)config[n].eyes[k]=k%2?gork_motion_config::minimum[n].eyes[k]:gork_motion_config::maximum[n].eyes[k];}
  config[2].props[5]=pen;MotionScene c;assert(c.configure(config,1,2,1));uint32_t now=0;
  for(int scene=0;scene<4;scene++){assert(c.set(scene,now));
   for(int t:{0,80,200,450,900,1250,1800,3000,5300,8200}){
    MotionPose p=c.sample(now+t);std::fill(M5.Display.data.begin(),M5.Display.data.end(),0);auto bounds=draw.bounds(p);draw.draw(p);
    for(int y=0;y<466;y++)for(int x=0;x<466;x++)if(M5.Display.data[y*466+x]){double r=std::hypot(x-233,y-233);if(r>216.8){std::cerr<<"OUTSIDE "<<mode<<" "<<pen<<" "<<scene<<" "<<t<<" "<<r;return 2;}maxRadius=std::max(maxRadius,r);assert(bounds.valid&&x>=bounds.x&&y>=bounds.y&&x<bounds.x+bounds.width&&y<bounds.y+bounds.height);}
    if(mode==0&&pen==0){std::cout<<scene<<","<<now+t<<",";PRINT_POSE;std::cout<<"\n";}
    if(mode==0&&t==3000){std::ofstream out("native-"+std::to_string(scene)+"-"+std::to_string(pen)+".ppm",std::ios::binary);out<<"P6\n466 466\n255\n";for(uint16_t v:M5.Display.data){unsigned char rgb[]={static_cast<unsigned char>((v>>11)*255/31),static_cast<unsigned char>(((v>>5)&63)*255/63),static_cast<unsigned char>((v&31)*255/31)};out.write(reinterpret_cast<char*>(rgb),3);}}
    frames++;
   }now+=8500;c.complete(now);assert(c.scene()==0);c.sample(now+3000);now+=2000;
  }
 }
 for(int i=0;i<1000;i++){assert(model.set(i%4,i*12,i%2));model.sample(i*12+1);}model.complete(14000,true);assert(model.scene()==0);
 auto finish=std::chrono::steady_clock::now();std::cerr<<"PASS actual C++ "<<frames<<" raster frames; 4 pens, user/min/max/mixed, 1000 switches, cancel, invalid versions/ranges; radius="<<maxRadius<<"; host_elapsed_ms="<<std::chrono::duration<double,std::milli>(finish-start).count()<<"; Params="<<sizeof(MotionParams)*4<<"; Pose="<<sizeof(MotionPose)<<"\n";
}
'''.replace('PRINT_POSE',printing)
    (OUT/'test.cpp').write_text(source,encoding='utf-8')
    mount=['docker','run','--rm','--network','none','-v',f'{OUT}:/work','-w','/work','--entrypoint']
    compile=subprocess.run(mount+['g++',IMAGE,'-std=c++17','-O2','-I.','test.cpp','motion_scene.cpp','motion_draw.cpp','-o','test'],capture_output=True,text=True)
    (OUT/'compile.log').write_text(compile.stdout+compile.stderr,encoding='utf-8')
    if compile.returncode:raise RuntimeError(compile.stderr[-3000:])
    result=subprocess.run(mount+['/work/test',IMAGE],capture_output=True,text=True)
    (OUT/'samples.csv').write_text(result.stdout,encoding='utf-8')
    (OUT/'result.log').write_text(result.stderr,encoding='utf-8')
    print(result.stderr)
    if result.returncode:raise RuntimeError('native raster acceptance failed')
    # Compare the actual compiled C++ choreography with the production JS controller.
    js="""const fs=require('fs'),Config=require(process.argv[1]+'/gork-config'),{SceneController}=require(process.argv[1]+'/scene-controller');const config=Config.parse(fs.readFileSync(process.argv[1]+'/initial-config.gork.json','utf8'));const c=new SceneController({config});const rows=fs.readFileSync(process.argv[2],'utf8').trim().split('\\n');const fields=JSON.parse(process.argv[3]);let current=-1;let errors=[];for(const row of rows){const nums=row.split(',').filter(x=>x!=='').map(Number),scene=nums[0],now=nums[1];if(scene!==current){if(current>=0){c.complete((current+1)*10500-2000);c.sample((current+1)*10500+1000);}c.set(Config.sceneNames[scene],scene*10500);current=scene;}const p=c.sample(now),values=['positionXLeft','positionYLeft','spacing','widthLeft','heightLeft','widthRight','heightRight','headX','headY','headZ',...fields].map(k=>p[k]);for(let i=0;i<values.length;i++)if(Math.abs(values[i]-nums[i+2])>.004)errors.push({scene,now,field:i,js:values[i],cpp:nums[i+2]});}if(errors.length){console.error(JSON.stringify(errors.slice(0,10)));process.exit(1);}console.log('PASS actual C++/JS all pose fields across user scene entry/loop, tolerance 0.004');"""
    result=subprocess.run(['node','-e',js,str(ROOT/'03-Src/stopwatch-voice-companion/static/motion'),str(OUT/'samples.csv'),json.dumps(names)],capture_output=True,text=True)
    print(result.stdout+result.stderr)
    if result.returncode:raise RuntimeError('C++/JS timing comparison failed')

if __name__=='__main__':main()
