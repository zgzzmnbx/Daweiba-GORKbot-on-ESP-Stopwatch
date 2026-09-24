#pragma once
#include <stdint.h>

// Intervals are below 2^31 ms. A stale loop timestamp must not time out a
// block started later in that iteration; subtraction also supports rollover.
constexpr bool audioBlockTimedOut(uint32_t now, uint32_t started) {
  return uint32_t(now-started)<0x80000000U && uint32_t(now-started)>1000U;
}
static_assert(!audioBlockTimedOut(1000,1005), "stale loop clock");
static_assert(!audioBlockTimedOut(1005,1005), "just queued");
static_assert(!audioBlockTimedOut(2005,1005), "timeout boundary");
static_assert(audioBlockTimedOut(2006,1005), "real stalled capture");
static_assert(!audioBlockTimedOut(10,0xfffffff0U), "clock rollover");
static_assert(audioBlockTimedOut(1000,0xfffffff0U), "timeout across rollover");
