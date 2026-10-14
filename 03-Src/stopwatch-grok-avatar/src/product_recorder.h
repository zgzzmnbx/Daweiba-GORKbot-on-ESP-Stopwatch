// SPDX-License-Identifier: AGPL-3.0-or-later
#pragma once
#include <stdint.h>
namespace gorkaudio {
// Product-only short-click intent. Audio-test push-to-talk stays independent.
class ProductRecorder {
 public:
  enum class Action { None, Begin, Cancel, Finish };
  Action click(uint32_t now) {
    switch (stage_) {
      case Stage::Idle: stage_=Stage::Waiting; requestedAt_=now; return Action::Begin;
      case Stage::Waiting: reset(); return Action::Cancel;
      case Stage::Recording: stage_=Stage::Finishing; return Action::Finish;
      case Stage::Finishing: return Action::None;
    }
    return Action::None;
  }
  bool pending(uint32_t now) const { return stage_==Stage::Waiting && now-requestedAt_<6000; }
  bool arm(uint32_t now) { if(!pending(now))return false;stage_=Stage::Recording;return true; }
  bool finishRequested() const { return stage_==Stage::Finishing; }
  bool expire(uint32_t now) {
    if(stage_!=Stage::Waiting || pending(now))return false;
    reset();return true;
  }
  void reset() { stage_=Stage::Idle; }
  // Cancel/Hello for the preceding audio session must preserve a new click.
  void audioStopped() { if(stage_!=Stage::Waiting)reset(); }
 private:
  enum class Stage { Idle, Waiting, Recording, Finishing };
  Stage stage_=Stage::Idle;
  uint32_t requestedAt_=0;
};
}
