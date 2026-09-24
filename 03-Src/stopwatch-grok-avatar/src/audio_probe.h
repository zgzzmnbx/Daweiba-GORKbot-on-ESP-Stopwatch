// SPDX-License-Identifier: AGPL-3.0-or-later
#pragma once
#include <BLEDevice.h>
#include <atomic>

class BLEControl;
class SoundControl;

// P0/P1 diagnostic endpoint, deliberately separate from the voice service and
// product gestures. All allocation/I2S work belongs to the main loop.
class AudioProbe : public BLECharacteristicCallbacks {
 public:
  explicit AudioProbe(BLEControl& control) : control_(control) {}
  bool attach(BLEServer* server);
  void enter(bool testPage = true);
  void leave();
  void update(uint32_t now);
  void setSoundControl(SoundControl* sound) { soundControl_ = sound; }
  bool busy() const { return state_ == State::Receiving || state_ == State::Loaded || state_ == State::Playing; }
  void onWrite(BLECharacteristic*, esp_ble_gatts_cb_param_t* param) override;
  static constexpr size_t kMaxBytes = 480000;
  static constexpr size_t kMaxPacket = 244;
  static constexpr size_t kHeader = 12;
  static constexpr uint8_t kVersion = 1;
  enum Op : uint8_t { Hello=1, Arm=2, Ping=3, Begin=4, Data=5,
    Commit=6, Play=7, Cancel=8, Pull=9, BeginOpus=10,
    Caps=128, Ack=129, Recording=130, Recorded=131, Audio=132,
    Playing=133, Played=134, Error=255 };
 private:
  enum class State { Off, Ready, Armed, Recording, Captured, Receiving,
    Loaded, Playing };
  struct Packet { uint16_t size=0; uint32_t link=0; uint8_t bytes[kMaxPacket]{}; };
  void process(const Packet&, uint32_t now);
  void reply(uint8_t op, uint16_t id, uint32_t value=0,
             const uint8_t* payload=nullptr, size_t size=0);
  void ack(uint8_t request, uint32_t value=0);
  void fail(uint32_t code);
  void stop();
  void resetQueue();
  void draw();
  bool allocate();
  void startRecording();
  void finishRecording(bool limited);
  bool queueRecordBlock();
  bool decodeOpus();
  BLEControl& control_;
  SoundControl* soundControl_=nullptr;
  BLEServer* server_=nullptr;
  BLECharacteristic* events_=nullptr;
  State state_=State::Off;
  uint8_t* buffer_=nullptr;
  uint8_t* decoded_=nullptr;
  uint32_t epoch_=0, link_=0, deadline_=0, recordStarted_=0;
  uint32_t total_=0, used_=0, rate_=16000, blockStarted_=0;
  uint32_t decodedSamples_=0, skipSamples_=0;
  uint16_t id_=0, lastId_=0, packetSize_=20;
  bool blockPending_=false, buttonReleased_=false, speakerOwned_=false;
  bool testPage_=false;
  bool opus_=false;
  uint32_t lastDraw_=0;
  uint32_t drainedAt_=0;
  uint32_t lastError_=0;
  const char* message_="Connect PC audio test";
  Packet queue_[4]{};
  uint8_t head_=0, count_=0;
  std::atomic<bool> cancel_{false}, overflow_{false};
  portMUX_TYPE mux_=portMUX_INITIALIZER_UNLOCKED;
};
