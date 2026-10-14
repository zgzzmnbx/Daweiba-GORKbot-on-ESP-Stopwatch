// SPDX-License-Identifier: AGPL-3.0-or-later
#pragma once
#include <stdint.h>

// Main-loop-only connection edge tracking; no network callbacks or heap use.
// Each real connection gets one bounded opportunity to announce. Muting or
// cancellation consumes it, so an old success is never spoken later.
class ConnectionAnnouncements {
 public:
  enum Cue : uint8_t { None, Wifi, Ble };
  Cue update(uint32_t now, bool wifiJoined, bool bleTrusted,
             uint32_t bleEpoch, bool blocked, bool muted, bool playing,
             bool cancel) {
    observe(wifi_, now, wifiJoined, 0);
    observe(ble_, now, bleTrusted, bleEpoch);
    if (cancel || muted) {
      wifi_.pending = ble_.pending = false;
      return None;
    }
    expire(wifi_, now);
    expire(ble_, now);
    if (blocked || playing) return None;
    if (ready(wifi_, now)) { wifi_.pending = false; return Wifi; }
    if (ready(ble_, now)) { ble_.pending = false; return Ble; }
    return None;
  }

 private:
  static constexpr uint32_t kStableMs = 300;
  static constexpr uint32_t kPendingMs = 10000;
  struct Link { bool connected=false, pending=false; uint32_t since=0, epoch=0; };
  Link wifi_, ble_;
  static void observe(Link& link, uint32_t now, bool connected, uint32_t epoch) {
    if (!connected) { link.connected = link.pending = false; return; }
    if (!link.connected || link.epoch != epoch) {
      link.since = now;
      link.pending = true;
      link.epoch = epoch;
    }
    link.connected = true;
  }
  static void expire(Link& link, uint32_t now) {
    if (link.pending && now-link.since >= kPendingMs) link.pending = false;
  }
  static bool ready(const Link& link, uint32_t now) {
    return link.pending && now-link.since >= kStableMs;
  }
};
