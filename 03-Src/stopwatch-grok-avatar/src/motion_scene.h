// SPDX-License-Identifier: AGPL-3.0-only
#pragma once
#include <cstdint>

struct MotionParams {float eyes[10]; float motion[3]; float props[6];};
struct MotionPose {
  float eyes[10]; float eyeAlpha=1, spinner=0, paper=0, question=0, pen=0;
  float ink=0, bob=0, questionScale=1, questionY=0, penX=0, penY=0, penRotation=0;
  float leftAngle=0, rightAngle=0, spinAngle=0;
  float spinX=0,spinY=0,spinScale=1,writeX=0,writeY=0,writeScale=1,penSize=1,strokeWidth=3;
  float qX=0,qY=0,qSize=1,penStyle=0;
};
class MotionScene {
 public:
  bool configure(const MotionParams* params, uint8_t version, uint8_t sourceVersion, uint32_t revision);
  bool set(uint8_t scene,uint32_t now,bool once=false);
  void complete(uint32_t now,bool cancel=false);
  MotionPose sample(uint32_t now);
  void disable(){enabled_=false;}
  bool enabled()const{return enabled_;}
  uint8_t scene()const{return scene_;}
  const char* name()const;
  uint32_t revision()const{return revision_;}
  bool returnedToIdle(uint32_t now)const{return completedOnce_&&scene_==0&&now-started_>=duration_;}
 private:
  MotionPose target(uint8_t scene,float age);
  MotionParams params_[4]{};
  MotionPose from_{};
  uint32_t started_=0,revision_=0;
  float duration_=0,onceAt_=0;
  uint8_t scene_=0;
  bool enabled_=false;
  bool completedOnce_=false;
};
