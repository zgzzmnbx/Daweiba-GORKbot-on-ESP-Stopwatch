// SPDX-License-Identifier: AGPL-3.0-or-later
#include "audio_probe.h"
#include "ble_control.h"
#include <M5Unified.h>
#include <BLE2902.h>
#include <esp_heap_caps.h>
#include <algorithm>
#include <cstring>

namespace {
constexpr char kService[]="48f1b001-8a75-4db6-9c18-590f7e9b0a01";
constexpr char kInput[]="48f1b002-8a75-4db6-9c18-590f7e9b0a01";
constexpr char kEvents[]="48f1b003-8a75-4db6-9c18-590f7e9b0a01";
constexpr uint32_t kLeaseMs=15000, kBlockSamples=320, kRecordBytes=320000;
std::atomic<uint16_t> audioGattInterface{ESP_GATT_IF_NONE};
void captureGattInterface(esp_gatts_cb_event_t event, esp_gatt_if_t interface,
                          esp_ble_gatts_cb_param_t*) {
  if (event==ESP_GATTS_CONNECT_EVT && interface!=ESP_GATT_IF_NONE)
    audioGattInterface.store(interface);
}
uint16_t get16(const uint8_t* p) { return p[0] | (uint16_t(p[1])<<8); }
uint32_t get32(const uint8_t* p) { return get16(p) | (uint32_t(get16(p+2))<<16); }
void put16(uint8_t* p,uint16_t v) { p[0]=v; p[1]=v>>8; }
void put32(uint8_t* p,uint32_t v) { put16(p,v); put16(p+2,v>>16); }
}

bool AudioProbe::attach(BLEServer* server) {
  server_=server;
  BLEDevice::setCustomGattsHandler(captureGattInterface);
  auto* service=server->createService(kService);
  if (!service) return false;
  auto* input=service->createCharacteristic(kInput,
      BLECharacteristic::PROPERTY_WRITE | BLECharacteristic::PROPERTY_WRITE_NR);
  events_=service->createCharacteristic(kEvents, BLECharacteristic::PROPERTY_NOTIFY);
  if (!input || !events_) return false;
  input->setAccessPermissions(ESP_GATT_PERM_WRITE_ENCRYPTED);
  input->setCallbacks(this);
  auto* cccd=new BLE2902();
  cccd->setAccessPermissions(ESP_GATT_PERM_READ_ENCRYPTED | ESP_GATT_PERM_WRITE_ENCRYPTED);
  events_->addDescriptor(cccd);
  service->start();
  return true;
}

void AudioProbe::onWrite(BLECharacteristic*, esp_ble_gatts_cb_param_t* param) {
  if (!param || !control_.audioPeerAllowed(param->write.conn_id)) return;
  const auto& w=param->write;
  if (w.is_prep || w.offset || w.len<kHeader || w.len>kMaxPacket || w.value[0]!=kVersion) {
    overflow_.store(true); return;
  }
  // CANCEL always bypasses a saturated data queue. It is fail-safe: any cancel
  // from the authorized peer may stop audio, but never start/replay anything.
  if (w.value[1]==Cancel) { cancel_.store(true); return; }
  portENTER_CRITICAL(&mux_);
  if (count_==4) overflow_.store(true);
  else {
    auto& p=queue_[(head_+count_)%4];
    p.size=w.len; p.link=control_.linkEpoch();
    memcpy(p.bytes,w.value,w.len); ++count_;
  }
  portEXIT_CRITICAL(&mux_);
}

void AudioProbe::resetQueue() {
  portENTER_CRITICAL(&mux_); head_=count_=0; portEXIT_CRITICAL(&mux_);
}

void AudioProbe::stop() {
  // end() joins the library tasks before the shared PCM storage is released.
  if (M5.Mic.isRunning()) M5.Mic.end();
  if (M5.Speaker.isRunning()) M5.Speaker.end();
  if (buffer_) { memset(buffer_,0,kMaxBytes); heap_caps_free(buffer_); buffer_=nullptr; }
  blockPending_=false; total_=used_=0; drainedAt_=0;
  if (state_!=State::Off) state_=State::Ready;
}

bool AudioProbe::allocate() {
  if (!M5.Mic.isEnabled() || !M5.Speaker.isEnabled()) return false;
  buffer_=static_cast<uint8_t*>(heap_caps_calloc(1,kMaxBytes,MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT));
  return buffer_!=nullptr;
}

void AudioProbe::enter() {
  stop(); state_=State::Ready; epoch_=0; id_=lastId_=0; deadline_=0;
  link_=control_.linkEpoch(); buttonReleased_=false;
  message_="Connect PC audio test"; draw();
}

void AudioProbe::leave() {
  stop(); resetQueue(); epoch_=0; state_=State::Off;
}

void AudioProbe::reply(uint8_t op,uint16_t id,uint32_t value,const uint8_t* payload,size_t size) {
  if (!events_ || !server_ || !control_.audioPeerAllowed(control_.connectionId()) ||
      control_.linkEpoch()!=link_ || server_->getConnectedCount()!=1 || size+kHeader>packetSize_) return;
  auto* cccd=static_cast<BLE2902*>(events_->getDescriptorByUUID(BLEUUID(uint16_t(0x2902))));
  if (!cccd || !cccd->getNotifications()) return;
  uint8_t packet[kMaxPacket]={kVersion,op};
  put16(packet+2,id); put32(packet+4,epoch_); put32(packet+8,value);
  if (size) memcpy(packet+kHeader,payload,size);
  // Arduino notify() broadcasts over every server peer. Send only to the
  // authenticated connection instead, including while rejecting a second peer.
  if (audioGattInterface.load()==ESP_GATT_IF_NONE) return;
  esp_ble_gatts_send_indicate(audioGattInterface.load(),control_.connectionId(),
      events_->getHandle(),kHeader+size,packet,false);
}

void AudioProbe::ack(uint8_t request,uint32_t value) { reply(Ack,id_,value,&request,1); }
void AudioProbe::fail(uint32_t code) {
  stop(); message_="Stopped / error (see PC)"; reply(Error,id_,code);
}

void AudioProbe::process(const Packet& packet,uint32_t now) {
  if (packet.link!=link_) return;
  const auto* p=packet.bytes;
  uint8_t op=p[1]; uint16_t id=get16(p+2);
  uint32_t epoch=get32(p+4), value=get32(p+8);
  size_t size=packet.size-kHeader;
  const auto* payload=p+kHeader;
  if (op==Hello) {
    if (size || !id || epoch || value<20 || value>kMaxPacket) { fail(1); return; }
    stop(); resetQueue(); id_=lastId_=id;
    epoch_=esp_random(); if (!epoch_) epoch_=1;
    packetSize_=std::min<uint16_t>(value,std::max<int>(20,server_->getPeerMTU(control_.connectionId())-3));
    deadline_=now+kLeaseMs; message_="PC linked; microphone OFF";
    uint8_t caps[4]; put16(caps,packetSize_); put16(caps+2,10);
    reply(Caps,id_,kMaxBytes,caps,sizeof(caps)); return;
  }
  if (!epoch_ || epoch!=epoch_) return;
  if (op==Ping && !size && id==id_) { deadline_=now+kLeaseMs; ack(Ping); return; }
  if (op==Arm || op==Begin) {
    if (!id || id<=lastId_) { fail(2); return; }
    stop(); id_=lastId_=id;
    if ((op==Arm && (size || value)) ||
        (op==Begin && (size!=4 || (value!=16000 && value!=24000) ||
          get32(payload)<value/5 || get32(payload)%2 || get32(payload)>value*20))) { fail(1); return; }
    if (!allocate()) { fail(3); return; }
    deadline_=now+kLeaseMs;
    if (op==Arm) {
      state_=State::Armed; buttonReleased_=false;
      message_="Hold A to record (max 10s)";
    } else {
      rate_=value; total_=get32(payload); state_=State::Receiving;
      message_="Receiving WAV via BLE";
    }
    ack(op); return;
  }
  if (id!=id_) return;
  deadline_=now+kLeaseMs;
  switch (op) {
    case Data:
      if (state_!=State::Receiving || !size || size%2 || packet.size>packetSize_ ||
          value!=used_ || size>total_-used_) { fail(4); return; }
      memcpy(buffer_+used_,payload,size); used_+=size; ack(Data,used_); return;
    case Commit:
      if (state_!=State::Receiving || size || used_!=total_ || value!=total_) { fail(4); return; }
      state_=State::Loaded; message_="Ready to play"; ack(Commit,total_); return;
    case Play:
      if ((state_!=State::Loaded && state_!=State::Captured) || size || value) { fail(2); return; }
      M5.Mic.end(); M5.Speaker.setVolume(48);
      if (!M5.Speaker.begin() || !M5.Speaker.playRaw(reinterpret_cast<int16_t*>(buffer_),
          used_/2,rate_,false,1,0,true)) { fail(5); return; }
      state_=State::Playing; message_="PLAYING / B: stop";
      reply(Playing,id_,used_); return;
    case Pull: {
      if (state_!=State::Captured || size || value%2 || value>=used_) { fail(4); return; }
      size_t n=std::min<size_t>(used_-value,(packetSize_-kHeader)&~1U);
      reply(Audio,id_,value,buffer_+value,n); return;
    }
    default: fail(1); return;
  }
}

bool AudioProbe::queueRecordBlock() {
  blockPending_=M5.Mic.record(reinterpret_cast<int16_t*>(buffer_+used_),kBlockSamples,16000,false);
  blockStarted_=millis(); return blockPending_;
}

void AudioProbe::startRecording(uint32_t now) {
  M5.Speaker.end(); rate_=16000; used_=total_=0;
  if (!M5.Mic.begin() || !queueRecordBlock()) { fail(5); return; }
  recordStarted_=now; state_=State::Recording;
  message_="REC / release A to finish"; draw(); reply(Recording,id_);
}

void AudioProbe::finishRecording(bool limited) {
  M5.Mic.end(); blockPending_=false;
  M5.Speaker.end();  // official StopWatch callback powers the shared rail off
  if (used_<3200) { fail(6); return; }
  state_=State::Captured; total_=used_;
  message_=limited ? "10s LIMIT / recording stopped" : "Recorded / microphone OFF";
  uint8_t flag=limited;
  reply(Recorded,id_,used_,&flag,1);
}

void AudioProbe::update(uint32_t now) {
  if (state_==State::Off) { resetQueue(); cancel_.store(false); overflow_.store(false); return; }
  if (control_.linkEpoch()!=link_ || !control_.audioPeerAllowed(control_.connectionId())) {
    if (buffer_ || epoch_) { stop(); epoch_=0; resetQueue(); message_="BLE disconnected / stopped"; }
    link_=control_.linkEpoch();
  }
  if (cancel_.exchange(false) || M5.BtnB.wasPressed()) {
    stop(); resetQueue(); message_="Stopped / microphone OFF"; ack(Cancel);
  }
  if (overflow_.exchange(false)) { resetQueue(); fail(7); }
  if (epoch_ && int32_t(now-deadline_)>=0) {
    fail(8); epoch_=0; resetQueue();
  }
  // At most one packet per iteration; control/physical cancellation is always first.
  Packet packet;
  portENTER_CRITICAL(&mux_);
  if (count_) { packet=queue_[head_]; head_=(head_+1)%4; --count_; }
  portEXIT_CRITICAL(&mux_);
  if (packet.size && control_.audioPeerAllowed(control_.connectionId())) process(packet,now);
  if (!M5.BtnA.isPressed()) buttonReleased_=true;
  if (state_==State::Armed && buttonReleased_ && !M5.BtnB.isPressed() && M5.BtnA.pressedFor(250)) {
    startRecording(now);
  }
  if (state_==State::Recording) {
    if (blockPending_ && !M5.Mic.isRecording()) { used_+=kBlockSamples*2; blockPending_=false; }
    if (blockPending_ && now-blockStarted_>1000) { fail(5); }
    else if (!blockPending_) {
      if (!M5.BtnA.isPressed() || used_>=kRecordBytes || now-recordStarted_>=10000)
        finishRecording(used_>=kRecordBytes || now-recordStarted_>=10000);
      else if (!queueRecordBlock()) fail(5);
    }
  }
  if (state_==State::Playing && !M5.Speaker.isPlaying()) {
    // Queue empty is not necessarily DMA empty. Allow the default 8x256 DMA
    // buffer at 44.1 kHz to drain; validate the tail acoustically at P1.
    if (!drainedAt_) drainedAt_=now;
    if (now-drainedAt_>=100) {
      stop(); message_="Playback finished"; reply(Played,id_);
    }
  }
  if (now-lastDraw_>=200) { lastDraw_=now; draw(); }
}

void AudioProbe::draw() {
  M5.Display.setTextDatum(middle_center);
  M5.Display.setTextColor(state_==State::Recording ? TFT_RED : TFT_WHITE,TFT_BLACK);
  M5.Display.fillRect(50,115,366,220,TFT_BLACK);
  M5.Display.setTextSize(1);
  M5.Display.drawString(message_,233,155);
  M5.Display.drawString("A: push to talk   B: STOP",233,202);
  M5.Display.drawString("PCM16 mono / BLE only",233,238);
  char line[64]; snprintf(line,sizeof(line),"%lu bytes / PSRAM %lu KB",
      static_cast<unsigned long>(used_),static_cast<unsigned long>(ESP.getFreePsram()/1024));
  M5.Display.drawString(line,233,276);
  M5.Display.drawString("Test page only; no ASR / cloud",233,309);
  M5.Display.setTextDatum(top_left);
}
