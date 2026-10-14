// SPDX-License-Identifier: AGPL-3.0-or-later
#pragma once
#include <stdint.h>
#include <stddef.h>
#include <cstring>
namespace gorkaudio {
enum class State { Off, Ready, Armed, Recording, Captured, Receiving, Loaded, Playing };
enum class DataDecision { Reject, Append, Duplicate };
inline DataDecision dataDecision(State state,bool opus,const uint8_t* buffer,
    uint32_t used,uint32_t total,uint32_t offset,const uint8_t* data,size_t size,
    size_t packet,size_t limit){
  if(state!=State::Receiving||!size||(!opus&&size%2)||packet>limit||used>total)return DataDecision::Reject;
  if(offset<used&&size<=used-offset&&buffer&&!memcmp(buffer+offset,data,size))return DataDecision::Duplicate;
  if(offset!=used||size>total-used)return DataDecision::Reject;
  return DataDecision::Append;
}
inline bool commitAllowed(State state,uint32_t used,uint32_t total,uint32_t value,size_t size){
  return !size&&value==total&&((state==State::Receiving&&used==total)||state==State::Loaded);
}
inline bool cancelMatches(uint16_t current,uint32_t epoch,uint16_t id,uint32_t supplied){
  return current&&epoch&&current==id&&epoch==supplied;
}
enum class PlayDecision { Reject, Start, Playing, Played, Cancelled };
inline PlayDecision playDecision(State state,uint16_t current,uint16_t played,bool cancelled,size_t size,uint32_t value){
  if(size||value)return PlayDecision::Reject;
  if(current&&played==current)return cancelled?PlayDecision::Cancelled:state==State::Playing?PlayDecision::Playing:PlayDecision::Played;
  return state==State::Loaded||state==State::Captured?PlayDecision::Start:PlayDecision::Reject;
}
}
