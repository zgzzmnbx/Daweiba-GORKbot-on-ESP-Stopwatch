// Four-scene choreography matching scene-controller.js. SPDX-License-Identifier: AGPL-3.0-only
#include "motion_scene.h"
#include "motion_config.h"
#include <algorithm>
#include <cmath>
#include <cstring>
namespace {
float smooth(float v){v=std::max(0.f,std::min(1.f,v));return v*v*(3-2*v);}
float mix(float a,float b,float t){return a+(b-a)*t;}
void inkPoint(int line,float x,float& y){y=34+line*30+sinf((x+90)*.12f)*3.5f+sinf((x+90)*.34f)*1.8f;}
void trace(float p,float& x,float& y){
 float cursor=std::min(2.999999f,std::max(0.f,std::min(1.f,p))*3),phase=cursor-floorf(cursor);
 int line=static_cast<int>(floorf(cursor));x=-90+170*std::min(1.f,phase/.83f);inkPoint(line,x,y);
 if(phase>.83f){float a=(phase-.83f)/.17f,ny;inkPoint((line+1)%3,-90,ny);x=mix(x,-90,a);y=mix(y,ny,a)-sinf(a*3.14159265359f)*23;}
}
}
bool MotionScene::configure(const MotionParams* p,uint8_t version,uint8_t sourceVersion,uint32_t revision){
 if(!p||version!=1||sourceVersion!=2||revision==0||revision<revision_)return false;
 for(int n=0;n<4;n++){
  for(int group=0;group<3;group++){
   const float* values=group==0?p[n].eyes:group==1?p[n].motion:p[n].props;
   const auto& lo=gork_motion_config::minimum[n];const auto& hi=gork_motion_config::maximum[n];
   const float* low=group==0?lo.eyes:group==1?lo.motion:lo.props;
   const float* high=group==0?hi.eyes:group==1?hi.motion:hi.props;
   int count=group==0?10:group==1?3:6;
   for(int k=0;k<count;k++)if(!std::isfinite(values[k])||values[k]<low[k]||values[k]>high[k])return false;
  }
  if(n==2&&floorf(p[n].props[5])!=p[n].props[5])return false;
 }
 memcpy(params_,p,sizeof(params_));revision_=revision;from_=target(0,0);return true;
}
bool MotionScene::set(uint8_t scene,uint32_t now,bool once){
 if(scene>3||!revision_)return false;
 const float outgoing=params_[scene_].motion[2];
 from_=enabled_?sample(now):target(0,0);scene_=scene;started_=now;enabled_=true;completedOnce_=false;
 duration_=scene==0?outgoing:params_[scene].motion[1];
 const float cycles[]={5600,2000,7199,3200};onceAt_=once?duration_+cycles[scene]/params_[scene].motion[0]:0;
 return true;
}
void MotionScene::complete(uint32_t now,bool cancel){
 completedOnce_=true;
 if(!enabled_||scene_==0)return;
 float exit=params_[scene_].motion[2];from_=sample(now);scene_=0;started_=now;onceAt_=0;
 duration_=cancel?std::min(400.f,exit):exit;
}
const char* MotionScene::name()const{static const char* names[]={"IDLE","LOADING","WRITING","QUESTION"};return names[scene_];}
MotionPose MotionScene::target(uint8_t scene,float age){
 MotionPose p;memcpy(p.eyes,params_[scene].eyes,sizeof(p.eyes));
 const float *l=params_[1].props,*w=params_[2].props,*q=params_[3].props;
 p.spinX=l[0];p.spinY=l[1];p.spinScale=l[2];p.writeX=w[0];p.writeY=w[1];p.writeScale=w[2];p.penSize=w[3];p.strokeWidth=w[4];p.penStyle=w[5];p.qX=q[0];p.qY=q[1];p.qSize=q[2];
 float t=age/1000.f;p.spinAngle=t*3.3f;
 if(scene==0){float look=sinf(t*.52f)*3;p.eyes[8]+=look;p.eyes[9]+=look*.3f;p.bob=sinf(t*1.5f)*2;
  float blink=fmodf(age,5600);if(blink>4600&&blink<4850){float b=fabsf((blink-4600)/125-1);p.eyes[3+1]=5+(p.eyes[4]-5)*b;p.eyes[6]=5+(p.eyes[6]-5)*b;}}
 else if(scene==1){p.eyeAlpha=0;p.eyes[3]=p.eyes[4]=p.eyes[5]=p.eyes[6]=5;p.eyes[2]=3;p.spinner=1;}
 else if(scene==2){p.paper=p.pen=1;float active=std::max(0.f,t-params_[2].motion[1]*params_[2].motion[0]/1000);p.ink=fmodf(active,7.2f)/7.2f;trace(p.ink,p.penX,p.penY);p.penRotation=.35f+sinf(active*2)*.025f;}
 else {p.leftAngle=-5;p.rightAngle=-12;p.question=1;p.questionY=sinf(t*2.7f)*q[3];p.eyes[9]+=sinf(t*1.6f)*1.8f;}
 return p;
}
MotionPose MotionScene::sample(uint32_t now){
 float age=static_cast<float>(now-started_);
 if(onceAt_>0&&age>=onceAt_){onceAt_=0;complete(now);age=0;}
 MotionPose p=target(scene_,age*params_[scene_].motion[0]);float raw=duration_?std::min(1.f,age/duration_):1,t=smooth(raw);
 MotionPose out;
 for(int i=0;i<10;i++)out.eyes[i]=mix(from_.eyes[i],p.eyes[i],t);
#define BLEND(k) out.k=mix(from_.k,p.k,t)
 BLEND(eyeAlpha);BLEND(spinner);BLEND(paper);BLEND(question);BLEND(pen);BLEND(ink);BLEND(bob);BLEND(questionScale);BLEND(questionY);BLEND(penX);BLEND(penY);BLEND(penRotation);BLEND(leftAngle);BLEND(rightAngle);BLEND(spinAngle);
 BLEND(spinX);BLEND(spinY);BLEND(spinScale);BLEND(writeX);BLEND(writeY);BLEND(writeScale);BLEND(penSize);BLEND(strokeWidth);BLEND(qX);BLEND(qY);BLEND(qSize);
#undef BLEND
 out.penStyle=p.penStyle;
 if(scene_==1&&raw<1){float collapse=smooth((raw-.2f)/.7f),opening=smooth(raw/.2f);
  for(int k:{3,4,5,6})out.eyes[k]=mix(mix(from_.eyes[k],params_[1].eyes[k],opening),5,collapse);
  out.eyes[2]=mix(mix(from_.eyes[2],params_[1].eyes[2],opening),3,collapse);out.eyeAlpha=1-collapse;out.spinner=collapse;}
 if(scene_==2&&raw<1){float x,y;trace(0,x,y);out.paper=mix(from_.paper,1,t);out.pen=mix(from_.pen,1,t);out.penX=mix(from_.pen>.01f?from_.penX:x+25,x,t);out.penY=mix(from_.pen>.01f?from_.penY:y-30,y,t);out.penRotation=mix(from_.pen>.01f?from_.penRotation:.55f,p.penRotation,t);out.ink=0;}
 if(scene_!=2&&from_.pen>.001f&&raw<1){out.ink=from_.ink;out.penX=from_.penX;out.penY=from_.penY-t*30;out.penRotation=from_.penRotation+t*.18f;}
 if(scene_==3&&raw<1)out.questionScale=1+sinf(raw*3.14159265359f)*.2f;
 return out;
}
