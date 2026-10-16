// SPDX-License-Identifier: AGPL-3.0-or-later
#pragma once
#include <stdint.h>

namespace gorkorientation {
class Direction {
 public:
  void setInverted(bool value) { inverted_ = value; }
  bool inverted() const { return inverted_; }
  uint8_t rotation() const { return inverted_ ? 2 : 0; }
  float axis(float value) const { return inverted_ ? -value : value; }
 private:
  bool inverted_ = false;
};

// Releases, not presses: cancellation stays on the original immediate B path.
// Idle single/double browse actions wait briefly to distinguish a triple.
class TripleB {
 public:
  static constexpr uint32_t GapMs = 350;
  struct Result { bool flip = false; uint8_t browse = 0; };
  Result update(uint32_t now, bool idle, bool clicked, bool browseAllowed) {
    Result result;
    if (!idle) {
      clear(); blocked_ = true; blockedAt_ = now;
      result.browse = clicked && browseAllowed ? 1 : 0;
      return result;
    }
    if (blocked_) {
      if (now - blockedAt_ <= GapMs) {
        if (clicked) blockedAt_ = now;  // Swallow the rest of a cancel burst.
        result.browse = clicked && browseAllowed ? 1 : 0;
        return result;
      }
      blocked_ = false;
    }
    if (count_ && now - lastClick_ > GapMs) {
      result.browse = browse_; clear();
    }
    if (!clicked) return result;
    lastClick_ = now; ++count_;
    if (browseAllowed) ++browse_;
    if (count_ == 3) {
      result.flip = true; result.browse = 0;
      clear(); blocked_ = true; blockedAt_ = now;
    }
    return result;
  }
  void reset(uint32_t now) { clear(); blocked_ = true; blockedAt_ = now; }
 private:
  void clear() { count_ = browse_ = 0; }
  uint32_t lastClick_ = 0, blockedAt_ = 0;
  uint8_t count_ = 0, browse_ = 0;
  bool blocked_ = false;
};
}
