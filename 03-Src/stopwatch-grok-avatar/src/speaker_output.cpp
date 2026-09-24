// SPDX-License-Identifier: AGPL-3.0-or-later
#include "speaker_output.h"

#include <M5Unified.h>
#include <driver/gpio.h>
#include <utility/M5IOE1_Class.hpp>

namespace {
constexpr uint8_t kCodecAddress = 0x18;
constexpr uint8_t kCodecResetRegister = 0x00;
constexpr uint8_t kCodecPoweredValue = 0x80;
constexpr uint32_t kI2cFrequency = 100000;
constexpr gpio_num_t kSpeakerPaGate = GPIO_NUM_14;
constexpr uint8_t kCodecUnityVolume = 0xBF;
// ES8311 REG32 uses 0.5 dB steps above 0xBF (0 dB). 0xD2 is +9.5 dB,
// equivalent to a nominal voltage gain of 2.99x.
constexpr uint8_t kCodecBuiltInLoudVolume = 0xD2;

struct CodecRegister {
  uint8_t address;
  uint8_t value;
};

// Register sequence produced by the official M5StopWatch-UserDemo's
// esp_codec_dev 1.5.4 setup for ES8311, 44.1 kHz MCLK, 16-bit Philips I2S.
// M5Unified's StopWatch callback configures only a small subset of this list.
constexpr CodecRegister kOfficialEs8311PlaybackRegisters[] = {
    {0x44, 0x08}, {0x44, 0x08}, {0x01, 0x30}, {0x02, 0x00},
    {0x03, 0x10}, {0x16, 0x24}, {0x04, 0x10}, {0x05, 0x00},
    {0x0B, 0x00}, {0x0C, 0x00}, {0x10, 0x1F}, {0x11, 0x7F},
    {0x00, 0x80}, {0x00, 0x80}, {0x01, 0x3F}, {0x06, 0x00},
    {0x13, 0x10}, {0x1B, 0x0A}, {0x1C, 0x6A}, {0x44, 0x58},
    {0x09, 0x0C}, {0x0A, 0x0C}, {0x02, 0x00}, {0x05, 0x00},
    {0x03, 0x10}, {0x04, 0x10}, {0x07, 0x00}, {0x08, 0xFF},
    {0x06, 0x03}, {0x00, 0x80}, {0x01, 0x3F}, {0x09, 0x0C},
    {0x0A, 0x0C}, {0x17, 0xBF}, {0x0E, 0x02}, {0x12, 0x00},
    {0x14, 0x1A}, {0x0D, 0x01}, {0x15, 0x40}, {0x37, 0x08},
    {0x45, 0x00}, {0x32, kCodecUnityVolume},
};

constexpr CodecRegister kCodecReadbackRegisters[] = {
    {0x00, 0x80}, {0x01, 0x3F}, {0x02, 0x00}, {0x03, 0x10},
    {0x04, 0x10}, {0x05, 0x00}, {0x06, 0x03}, {0x08, 0xFF},
    {0x09, 0x0C}, {0x0D, 0x01}, {0x0E, 0x02}, {0x12, 0x00},
    {0x13, 0x10}, {0x14, 0x1A}, {0x37, 0x08},
    {0x44, 0x58},
};

bool writeCodecRegister(uint8_t address, uint8_t value) {
  for (uint8_t retries = 0; retries < 3; ++retries) {
    if (M5.In_I2C.writeRegister8(kCodecAddress, address, value,
                                 kI2cFrequency)) {
      return true;
    }
    M5.delay(1);
  }
  return false;
}

bool configureOfficialEs8311Playback(uint8_t dacVolume) {
  for (const auto& item : kOfficialEs8311PlaybackRegisters) {
    if (!writeCodecRegister(item.address, item.value)) {
      Serial.printf("Speaker diagnostic: codec write 0x%02X failed\n",
                    item.address);
      return false;
    }
  }

  if (!writeCodecRegister(0x32, dacVolume)) {
    Serial.println("Speaker diagnostic: codec DAC volume write failed");
    return false;
  }

  uint8_t mute = 0;
  if (!M5.In_I2C.readRegister(kCodecAddress, 0x31, &mute, sizeof(mute),
                              kI2cFrequency) ||
      !writeCodecRegister(0x31, mute & 0x9F)) {
    Serial.println("Speaker diagnostic: codec unmute failed");
    return false;
  }

  for (const auto& item : kCodecReadbackRegisters) {
    uint8_t actual = 0;
    if (!M5.In_I2C.readRegister(kCodecAddress, item.address, &actual,
                                sizeof(actual), kI2cFrequency) ||
        actual != item.value) {
      Serial.printf(
          "Speaker diagnostic: codec verify 0x%02X expected=0x%02X actual=0x%02X\n",
          item.address, item.value, actual);
      return false;
    }
  }
  uint8_t actualVolume = 0;
  if (!M5.In_I2C.readRegister(kCodecAddress, 0x32, &actualVolume,
                              sizeof(actualVolume), kI2cFrequency) ||
      actualVolume != dacVolume) {
    Serial.printf(
        "Speaker diagnostic: codec verify 0x32 expected=0x%02X actual=0x%02X\n",
        dacVolume, actualVolume);
    return false;
  }
  if (!M5.In_I2C.readRegister(kCodecAddress, 0x31, &mute, sizeof(mute),
                              kI2cFrequency) ||
      (mute & 0x60) != 0) {
    Serial.printf("Speaker diagnostic: codec mute bits=0x%02X\n", mute);
    return false;
  }
  Serial.printf("Speaker diagnostic: official ES8311 config verified, DAC=0x%02X\n",
                dacVolume);
  return true;
}

bool setSpeakerPaGate(bool enabled) {
  // Input remains enabled so gpio_get_level() can validate the driven level.
  return gpio_set_direction(kSpeakerPaGate, GPIO_MODE_INPUT_OUTPUT) == ESP_OK &&
         gpio_set_level(kSpeakerPaGate, enabled ? 1 : 0) == ESP_OK &&
         gpio_get_level(kSpeakerPaGate) == (enabled ? 1 : 0);
}
}  // namespace

void stopStopWatchSpeaker() {
  setSpeakerPaGate(false);
  M5.Speaker.end();
}

SpeakerStartResult startStopWatchSpeaker(uint8_t volume,
                                         SpeakerGainProfile gainProfile) {
  M5.Mic.end();
  if (!setSpeakerPaGate(false)) {
    Serial.println("Speaker diagnostic: GPIO14 PA gate setup failed");
    return SpeakerStartResult::AmplifierGate;
  }
  M5.Speaker.end();

  // Explicitly restore these shared-expander pins before every playback.
  auto& ioe1 = static_cast<m5::M5IOE1_Class&>(M5.getIOExpander(0));
  ioe1.setHighImpedance(m5::M5IOE1_Class::gpio3, false);
  ioe1.setHighImpedance(m5::M5IOE1_Class::gpio10, false);
  ioe1.setDirection(m5::M5IOE1_Class::gpio3, true);
  ioe1.setDirection(m5::M5IOE1_Class::gpio10, true);
  ioe1.digitalWrite(m5::M5IOE1_Class::gpio10, false);
  ioe1.digitalWrite(m5::M5IOE1_Class::gpio3, false);
  M5.delay(10);

  M5.Speaker.setVolume(volume);
  M5.Speaker.setAllChannelVolume(255);
  M5.Speaker.setChannelVolume(0, 255);
  if (!M5.Speaker.begin()) {
    Serial.println("Speaker diagnostic: driver begin failed");
    stopStopWatchSpeaker();
    return SpeakerStartResult::Driver;
  }
  M5.delay(10);

  const bool codecPower = ioe1.getWriteValue(m5::M5IOE1_Class::gpio3);
  const bool amplifierCallback =
      ioe1.getWriteValue(m5::M5IOE1_Class::gpio10);
  // The factory sequence configures the codec before enabling either PA gate.
  ioe1.digitalWrite(m5::M5IOE1_Class::gpio10, false);
  if (!codecPower || !amplifierCallback) {
    Serial.printf("Speaker diagnostic: power=%u pa=%u\n", codecPower,
                  amplifierCallback);
    stopStopWatchSpeaker();
    return SpeakerStartResult::Power;
  }

  uint8_t codecReset = 0;
  const bool codecResponding = M5.In_I2C.readRegister(
      kCodecAddress, kCodecResetRegister, &codecReset, sizeof(codecReset),
      kI2cFrequency);
  Serial.printf("Speaker diagnostic: power=%u pa=%u codec=%u reg00=0x%02X\n",
                codecPower, amplifierCallback, codecResponding, codecReset);
  if (!codecResponding || codecReset != kCodecPoweredValue) {
    stopStopWatchSpeaker();
    return SpeakerStartResult::Codec;
  }
  const uint8_t dacVolume = gainProfile == SpeakerGainProfile::BuiltInLoud
                                ? kCodecBuiltInLoudVolume
                                : kCodecUnityVolume;
  if (!configureOfficialEs8311Playback(dacVolume)) {
    stopStopWatchSpeaker();
    return SpeakerStartResult::CodecConfiguration;
  }
  ioe1.digitalWrite(m5::M5IOE1_Class::gpio10, true);
  if (!ioe1.getWriteValue(m5::M5IOE1_Class::gpio10)) {
    Serial.println("Speaker diagnostic: M5IOE1 G10 PA re-enable failed");
    stopStopWatchSpeaker();
    return SpeakerStartResult::Power;
  }
  if (!setSpeakerPaGate(true)) {
    Serial.println("Speaker diagnostic: GPIO14 PA gate enable failed");
    stopStopWatchSpeaker();
    return SpeakerStartResult::AmplifierGate;
  }
  M5.delay(10);
  Serial.println("Speaker diagnostic: GPIO14 PA gate=1");
  return SpeakerStartResult::Ok;
}

const char* speakerStartResultText(SpeakerStartResult result) {
  switch (result) {
    case SpeakerStartResult::Ok:
      return "output enabled";
    case SpeakerStartResult::Driver:
      return "driver failed";
    case SpeakerStartResult::Power:
      return "power/PA failed";
    case SpeakerStartResult::Codec:
      return "codec failed";
    case SpeakerStartResult::AmplifierGate:
      return "GPIO14 PA failed";
    case SpeakerStartResult::CodecConfiguration:
      return "codec config failed";
  }
  return "unknown";
}
