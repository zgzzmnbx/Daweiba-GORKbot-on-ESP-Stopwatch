// SPDX-License-Identifier: AGPL-3.0-or-later
#pragma once
#include <BLEDevice.h>
#include <atomic>
#include <stdint.h>

class BLEControl;

class SoundControl : public BLECharacteristicCallbacks {
 public:
  explicit SoundControl(BLEControl& control) : control_(control) {}
  bool attach(BLEServer* server);
  void update(uint32_t now, bool blocked);
  void onWrite(BLECharacteristic*, esp_ble_gatts_cb_param_t* param) override;
  void setInitialVolume(uint8_t value);
  void setLocalVolume(uint8_t value);
  void toggleMute();
  bool preview(uint8_t soundId);
  uint8_t volume() const { return volume_; }
  bool isPlaying() const { return playing_; }
  const char* hardwareStatus() const { return hardwareStatus_; }
  bool takeVolumeChanged(uint8_t* value);
  bool takeButtonBConsumed();
  void stopNow();

 private:
  static constexpr size_t kFrameSize = 9;
  static constexpr uint8_t kVersion = 1;
  enum Op : uint8_t { Caps=1, Catalog=2, Play=3, Stop=4, SetVolume=5, GetStatus=6 };
  enum Event : uint8_t { Accepted=0x80, Started=0x81, Completed=0x82, Stopped=0x83, Status=0x84, Failed=0xff };
  enum Error : uint32_t { BadFrame=1, UnknownSound=2, Busy=3, Blocked=4, Speaker=5 };
  struct Frame { uint8_t bytes[kFrameSize]{}; uint32_t link=0; };
  struct Terminal { uint16_t id=0; uint8_t op=0, arg=0; uint32_t value=0, link=0; };
  void process(const Frame&, uint32_t now);
  void reply(uint8_t op, uint16_t id, uint32_t value=0, uint8_t arg=0, bool terminal=false);
  void fail(uint16_t id, Error error);
  bool replayTerminal(uint16_t id);
  bool startPlayback(const int16_t* pcm, size_t samples);
  const int16_t* sound(uint8_t id, size_t* samples) const;
  BLEControl& control_;
  BLECharacteristic* events_=nullptr;
  Frame queue_[8]{};
  Terminal terminal_[8]{};
  uint8_t head_=0, count_=0;
  uint8_t terminalHead_=0;
  std::atomic<bool> stopRequested_{false};
  std::atomic<uint16_t> stopRequestId_{0};
  portMUX_TYPE mux_=portMUX_INITIALIZER_UNLOCKED;
  uint32_t link_=0, drainedAt_=0;
  uint16_t activeRequest_=0;
  uint8_t activeSound_=0, volume_=20, lastNonZeroVolume_=20;
  bool playing_=false, volumeChanged_=false;
  bool buttonBConsumed_=false;
  const char* hardwareStatus_="not tested";
};
