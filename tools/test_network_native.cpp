#include "network_frame.h"
#include "audio_task_core.h"
#include <cassert>
#include <cstring>
#include <cstdio>
int main(){
  using namespace gorknet;
  const uint8_t data[]={'a','b','c'};uint8_t h[Header];header(h,5,3,0x12345678,0x10203040,1,data);
  const uint8_t expected[]={0x47,0x57,1,5,3,0,0,0,0x78,0x56,0x34,0x12,0x40,0x30,0x20,0x10,1,0,0,0,0xc2,0x41,0x24,0x35};
  assert(!memcmp(h,expected,24));assert(validHeader(h));p16(h+4,4097);assert(!validHeader(h));
  assert(crc(data,3)==0x352441c2);Recent recent;
  for(uint32_t i=1;i<=40;++i){assert(recent.fresh(i));recent.add(i,i,5);}
  assert(!recent.find(1));assert(!recent.fresh(1));assert(recent.find(40));assert(!recent.fresh(40));
  puts("C++ production frame/CRC/recent-state eviction: PASS");
  using namespace gorkaudio;
  const uint8_t pcm[]={1,0,2,0};
  assert(dataDecision(State::Receiving,false,pcm,4,8,0,pcm,4,16,244)==DataDecision::Duplicate);
  assert(dataDecision(State::Receiving,false,pcm,4,8,4,pcm,4,16,244)==DataDecision::Append);
  assert(dataDecision(State::Receiving,false,pcm,4,8,6,pcm,4,16,244)==DataDecision::Reject);
  assert(dataDecision(State::Receiving,false,pcm,4,8,4,pcm,3,15,244)==DataDecision::Reject);
  assert(dataDecision(State::Receiving,false,pcm,9,8,9,pcm,4,16,244)==DataDecision::Reject);
  assert(dataDecision(State::Receiving,false,pcm,4,8,4,pcm,4,256,244)==DataDecision::Reject);
  assert(!commitAllowed(State::Receiving,4,8,8,0));
  assert(commitAllowed(State::Loaded,8,8,8,0));
  assert(!cancelMatches(5,10,5,11));assert(!cancelMatches(5,10,6,10));assert(cancelMatches(5,10,5,10));
  assert(playDecision(State::Loaded,5,0,false,0,0)==PlayDecision::Start);
  assert(playDecision(State::Playing,5,5,false,0,0)==PlayDecision::Playing);
  assert(playDecision(State::Ready,5,5,false,0,0)==PlayDecision::Played);
  assert(playDecision(State::Ready,5,5,true,0,0)==PlayDecision::Cancelled);
  assert(playDecision(State::Receiving,5,0,false,0,0)==PlayDecision::Reject);
  puts("C++ production audio task decisions: PASS");
}
