// SPDX-License-Identifier: AGPL-3.0-or-later
#pragma once

#include <stdint.h>

enum class SpeakerStartResult : uint8_t {
  Ok = 0,
  Driver = 1,
  Power = 2,
  Codec = 3,
  AmplifierGate = 4,
  CodecConfiguration = 5,
};

enum class SpeakerGainProfile : uint8_t {
  Unity = 0,
  BuiltInLoud = 1,
};

// Start the shared StopWatch codec/PA path from a known state. The board uses
// M5IOE1 G3 for codec power, and both G10 and ESP32 GPIO14 for the external
// power amplifier, matching the official M5Stack factory demo.
// BuiltInLoud adds +9.5 dB in the ES8311 DAC only for the short built-in
// sounds. Full-scale material may saturate at this deliberately aggressive
// setting, so streamed/recorded audio must keep the default Unity profile.
SpeakerStartResult startStopWatchSpeaker(
    uint8_t volume, SpeakerGainProfile gainProfile = SpeakerGainProfile::Unity);

// Disable both external amplifier gates before stopping the shared driver.
void stopStopWatchSpeaker();

const char* speakerStartResultText(SpeakerStartResult result);
