// SPDX-License-Identifier: AGPL-3.0-or-later

#pragma once

#include <stddef.h>
#include <stdint.h>

#include <BLEDevice.h>

// BLE remains an optional runtime feature.  The firmware owns the GATT
// protocol, while the main loop owns avatar state, rendering, and NVS.
class BLEControl {
 public:
  static constexpr const char* kDeviceName = "GorkBot-SW";
  static constexpr const char* kServiceUuid =
      "48f1a001-8a75-4db6-9c18-590f7e9b0a01";
  static constexpr const char* kCommandUuid =
      "48f1a002-8a75-4db6-9c18-590f7e9b0a01";
  static constexpr const char* kStatusUuid =
      "48f1a003-8a75-4db6-9c18-590f7e9b0a01";
  static constexpr uint8_t kPeerAddressLength = 6;
  static constexpr uint8_t kMaxCommandLength = 20;
  static constexpr uint8_t kMaxStatusLength = 20;
  static constexpr uint8_t kCommandQueueCapacity = 8;
  static constexpr uint8_t kStatusQueueCapacity = 4;
  static constexpr uint32_t kPairWindowMs = 120000;

  BLEControl();

  // When enabled is false, no BLE stack is initialized.  This preserves the
  // first-upgrade default and keeps the USB control path independent.
  bool begin(bool enabled, bool hasBoundPeer,
             const uint8_t* boundPeer = nullptr);
  void update(uint32_t nowMs);

  bool setEnabled(bool enabled, uint32_t nowMs);
  bool openPairingWindow(uint32_t nowMs);
  void clearBinding();

  bool takeCommand(char* out, size_t outCapacity, uint16_t* connectionId);
  void publishResult(uint16_t connectionId, const char* status);
  bool takeNewBinding(uint8_t* outPeer, size_t outCapacity);

  bool enabled() const { return enabled_; }
  bool initialized() const { return initialized_; }
  bool connected() const { return connected_; }
  bool authorized() const { return authorized_; }
  bool hasBoundPeer() const { return hasBoundPeer_; }
  bool pairingWindowOpen(uint32_t nowMs) const;
  uint16_t pairingSecondsRemaining(uint32_t nowMs) const;

 private:
  struct CommandEvent {
    uint16_t connectionId = 0;
    uint8_t length = 0;
    char value[kMaxCommandLength + 1] = {};
  };

  struct StatusEvent {
    uint16_t connectionId = 0;
    uint8_t length = 0;
    char value[kMaxStatusLength + 1] = {};
  };

  class ServerCallbacks : public BLEServerCallbacks {
   public:
    explicit ServerCallbacks(BLEControl* owner) : owner_(owner) {}
    void onConnect(BLEServer* server,
                   esp_ble_gatts_cb_param_t* param) override;
    void onDisconnect(BLEServer* server,
                      esp_ble_gatts_cb_param_t* param) override;

   private:
    BLEControl* owner_;
  };

  class CommandCallbacks : public BLECharacteristicCallbacks {
   public:
    explicit CommandCallbacks(BLEControl* owner) : owner_(owner) {}
    void onWrite(BLECharacteristic* characteristic,
                 esp_ble_gatts_cb_param_t* param) override;

   private:
    BLEControl* owner_;
  };

  class SecurityCallbacks : public BLESecurityCallbacks {
   public:
    explicit SecurityCallbacks(BLEControl* owner) : owner_(owner) {}
    uint32_t onPassKeyRequest() override;
    void onPassKeyNotify(uint32_t passKey) override;
    bool onSecurityRequest() override;
    void onAuthenticationComplete(esp_ble_auth_cmpl_t result) override;
    bool onConfirmPIN(uint32_t pin) override;

   private:
    BLEControl* owner_;
  };

  friend class ServerCallbacks;
  friend class CommandCallbacks;
  friend class SecurityCallbacks;

  bool initializeStack();
  void startAdvertising();
  void stopAdvertising();
  void requestDisconnect();
  bool addressMatches(const uint8_t* address) const;
  bool currentPeerAllowed() const;
  bool validCommandBytes(const uint8_t* data, size_t length) const;
  void enqueueCommand(uint16_t connectionId, const uint8_t* data,
                      size_t length);
  void enqueueStatus(uint16_t connectionId, const char* status);
  bool popStatus(StatusEvent* event);
  void notifyStatus(const StatusEvent& event);
  void resetQueues();

  BLEServer* server_ = nullptr;
  BLEService* service_ = nullptr;
  BLECharacteristic* commandCharacteristic_ = nullptr;
  BLECharacteristic* statusCharacteristic_ = nullptr;
  ServerCallbacks serverCallbacks_;
  CommandCallbacks commandCallbacks_;
  SecurityCallbacks securityCallbacks_;
  BLESecurity security_;

  bool enabled_ = false;
  bool initialized_ = false;
  bool advertising_ = false;
  bool pairingWindow_ = false;
  uint32_t pairingEndsAtMs_ = 0;

  bool hasBoundPeer_ = false;
  uint8_t boundPeer_[kPeerAddressLength] = {};
  bool pendingBinding_ = false;
  uint8_t pendingPeer_[kPeerAddressLength] = {};

  bool connected_ = false;
  bool authorized_ = false;
  bool disconnectRequested_ = false;
  bool rejectConnectionRequested_ = false;
  uint16_t rejectConnectionId_ = 0;
  uint16_t connectionId_ = 0;
  uint8_t connectedPeer_[kPeerAddressLength] = {};

  CommandEvent commandQueue_[kCommandQueueCapacity] = {};
  uint8_t commandHead_ = 0;
  uint8_t commandTail_ = 0;
  uint8_t commandCount_ = 0;

  StatusEvent statusQueue_[kStatusQueueCapacity] = {};
  uint8_t statusHead_ = 0;
  uint8_t statusTail_ = 0;
  uint8_t statusCount_ = 0;
  bool overflowStatusPending_ = false;
  uint16_t overflowStatusConnectionId_ = 0;

  portMUX_TYPE queueMux_ = portMUX_INITIALIZER_UNLOCKED;
};
