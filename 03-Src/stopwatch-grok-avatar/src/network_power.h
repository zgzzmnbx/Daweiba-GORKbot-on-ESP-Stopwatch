// SPDX-License-Identifier: AGPL-3.0-or-later
#pragma once
#include <cstdint>
namespace gorknet {
// The coexistence controller requires modem sleep while Bluetooth is enabled.
// Performance may disable sleep only when the Bluetooth controller is off.
inline bool modemSleep(uint8_t power,bool bluetoothEnabled){return power!=1||bluetoothEnabled;}
}
