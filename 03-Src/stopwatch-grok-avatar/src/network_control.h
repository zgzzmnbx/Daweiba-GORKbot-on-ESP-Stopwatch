// SPDX-License-Identifier: AGPL-3.0-or-later
#pragma once
#include <BLEDevice.h>
#include <Preferences.h>
#include <atomic>
#include "network_frame.h"
class BLEControl;
class NetworkControl:public BLECharacteristicCallbacks {
 public:
  struct Frame{uint8_t kind=0;uint32_t request=0,session=0;uint16_t size=0;uint8_t data[gorknet::MaxPayload]{};};
  explicit NetworkControl(BLEControl& ble):ble_(ble){}
  void begin();
  void prepareBluetooth();
  bool attach(BLEServer* server);
  void onWrite(BLECharacteristic*,esp_ble_gatts_cb_param_t* p) override;
  void update(uint32_t now,bool busy);
  Frame* take();
  void reply(const Frame& request,const char* result,bool error=false);
  bool audioReply(const uint8_t* data,size_t n);
  bool ready()const{return authenticated_;}
  uint32_t link()const{return link_.load();}
  uint32_t session()const{return session_.load();}
  uint8_t policy()const{return config_.policy;}
  uint8_t power()const{return config_.power;}
  uint8_t effectivePower()const{return effectivePower_;}
  const char* source()const{return powerSource_;}
  void delegate(bool enabled,bool network);
  bool delegated()const;
  void voiceEvent(uint8_t code);
  const char* state()const{return status_.load();}
  String address()const;
  bool wifiJoined()const;
  String publicStatus()const;
  bool options(uint8_t policy,uint8_t power);
  bool configureUsb(const uint8_t* payload,size_t size);
  void reconnect();
  void forget();
  void localBleOnly();
  uint32_t boot()const{return boot_;}
 private:
  struct Config{uint32_t magic=0x314E5747;uint8_t policy=0,power=0;char ssid[33]{},password[64]{},identity[17]{};uint8_t key[32]{};uint32_t crc=0;};
  struct Provision{uint8_t size=0;uint8_t data[244]{};uint32_t link=0;};
  static void task(void* self);
  void serve();
  bool save(Config candidate);
  void provision(const Provision& p);
  bool send(uint8_t kind,uint32_t request,const uint8_t* data,size_t size,uint32_t session);
  BLEControl& ble_;
  BLECharacteristic* statusCharacteristic_=nullptr;
  BLECharacteristic* voiceCharacteristic_=nullptr;
  Preferences prefs_;
  Config config_{};
  Config nextConfig_{};
  uint32_t applyAt_=0;
  QueueHandle_t input_=nullptr,output_=nullptr,provision_=nullptr;
  TaskHandle_t worker_=nullptr;
  uint32_t boot_=0,nextRetry_=0,attempt_=0;
  std::atomic<uint32_t> link_{1},session_{0};
  std::atomic<bool> authenticated_{false},reset_{false};
  uint8_t effectivePower_=2;
  const char* powerSource_="unknown";
  uint32_t lastPower_=0,voiceDeadline_=0,voiceLink_=0;
  bool voiceNetwork_=false;
  portMUX_TYPE configMux_=portMUX_INITIALIZER_UNLOCKED;
  std::atomic<uint32_t> configRevision_{0};
  bool wifiStarted_=false,mdns_=false;
  std::atomic<const char*> status_{"not configured"};
  std::atomic<bool> provisionOverflow_{false};
  uint8_t pending_[160]{},expected_=0,used_=0,configId_=0;
  uint32_t configLink_=0,configDeadline_=0;
  gorknet::Recent recent_{};
};
