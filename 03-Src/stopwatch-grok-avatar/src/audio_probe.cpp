// SPDX-License-Identifier: AGPL-3.0-or-later
#include "audio_probe.h"
#include "audio_timing.h"
#include "ble_control.h"
#include "sound_control.h"
#include "speaker_output.h"
#include <M5Unified.h>
#include <BLE2902.h>
#include <esp_heap_caps.h>
#include <algorithm>
#include <cstring>
#include <opus.h>

namespace {
constexpr char kService[]="48f1b001-8a75-4db6-9c18-590f7e9b0a01";
constexpr char kInput[]="48f1b002-8a75-4db6-9c18-590f7e9b0a01";
constexpr char kEvents[]="48f1b003-8a75-4db6-9c18-590f7e9b0a01";
constexpr uint32_t kLeaseMs=15000, kBlockSamples=320, kRecordBytes=320000;
constexpr uint16_t kOpusHelloId=0xF00D;
uint16_t get16(const uint8_t* p) { return p[0] | (uint16_t(p[1])<<8); }
uint32_t get32(const uint8_t* p) { return get16(p) | (uint32_t(get16(p+2))<<16); }
void put16(uint8_t* p,uint16_t v) { p[0]=v; p[1]=v>>8; }
void put32(uint8_t* p,uint32_t v) { put16(p,v); put16(p+2,v>>16); }
}

bool AudioProbe::attach(BLEServer* server) {
  server_=server;
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
  const bool micOwned = state_ == State::Recording;
  if (M5.Mic.isRunning()) M5.Mic.end();
  if (speakerOwned_ || micOwned) stopStopWatchSpeaker();
  speakerOwned_=false;
  if (buffer_) { memset(buffer_,0,kMaxBytes); heap_caps_free(buffer_); buffer_=nullptr; }
  if (decoded_) { memset(decoded_,0,decodedSamples_*2); heap_caps_free(decoded_); decoded_=nullptr; }
  blockPending_=false; total_=used_=decodedSamples_=skipSamples_=0; drainedAt_=0;
  opus_=false;
  if (state_!=State::Off) state_=State::Ready;
}

bool AudioProbe::allocate() {
  if (!M5.Mic.isEnabled() || !M5.Speaker.isEnabled()) return false;
  buffer_=static_cast<uint8_t*>(heap_caps_calloc(1,kMaxBytes,MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT));
  return buffer_!=nullptr;
}

void AudioProbe::enter(bool testPage) {
  lastError_=0;
  stop(); state_=State::Ready; epoch_=0; id_=lastId_=0; deadline_=0;
  testPage_=testPage;
  link_=control_.linkEpoch(); buttonReleased_=false;
  message_=testPage_ ? "Connect PC audio test" : "Avatar audio ready";
  if (testPage_) draw();
}

void AudioProbe::leave() {
  stop(); resetQueue(); epoch_=0; state_=State::Off;
  testPage_=false;
}

void AudioProbe::reply(uint8_t op,uint16_t id,uint32_t value,const uint8_t* payload,size_t size) {
  if (!events_ || !server_ || !control_.audioPeerAllowed(control_.connectionId()) ||
      control_.linkEpoch()!=link_ || server_->getConnectedCount()!=1 || size+kHeader>packetSize_) return;
  auto* cccd=static_cast<BLE2902*>(events_->getDescriptorByUUID(BLEUUID(uint16_t(0x2902))));
  if (!cccd || !cccd->getNotifications()) return;
  uint8_t packet[kMaxPacket]={kVersion,op};
  put16(packet+2,id); put32(packet+4,epoch_); put32(packet+8,value);
  if (size) memcpy(packet+kHeader,payload,size);
  // BLEControl sends only to the authenticated connection.
  control_.sendNotification(events_,packet,kHeader+size);
}

void AudioProbe::ack(uint8_t request,uint32_t value) { reply(Ack,id_,value,&request,1); }
void AudioProbe::fail(uint32_t code) {
  stop(); lastError_=code;
  switch (code) {
    case 9: message_="E9: Mic init failed"; break;
    case 10: message_="E10: Mic queue failed"; break;
    case 11: message_="E11: Mic capture timeout"; break;
    case 12: message_="E12: Speaker init failed"; break;
    case 13: message_="E13: Playback queue failed"; break;
    case 14: message_="E14: Opus decode failed"; break;
    default: message_="Stopped / error (see PC)"; break;
  }
  reply(Error,id_,code);
}

bool AudioProbe::decodeOpus() {
  if (!opus_ || !buffer_ || !decodedSamples_ || !used_) return false;
  decoded_=static_cast<uint8_t*>(heap_caps_malloc(decodedSamples_*2,MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT));
  auto* frame=static_cast<opus_int16*>(heap_caps_malloc(rate_/1000*120*2,MALLOC_CAP_8BIT));
  int error=OPUS_OK;
  OpusDecoder* decoder=opus_decoder_create(rate_,1,&error);
  if (!decoded_ || !frame || !decoder || error!=OPUS_OK) {
    if (decoder) opus_decoder_destroy(decoder);
    if (frame) heap_caps_free(frame);
    return false;
  }
  uint32_t offset=0, samples=0, skip=skipSamples_;
  bool valid=true;
  while (offset+2<=used_) {
    const uint16_t length=get16(buffer_+offset); offset+=2;
    if (!length || length>1275 || length>used_-offset) { valid=false; break; }
    const int count=opus_decode(decoder,buffer_+offset,length,frame,rate_/1000*120,0);
    offset+=length;
    if (count<=0) { valid=false; break; }
    const uint32_t drop=std::min<uint32_t>(skip,count);
    skip-=drop;
    const uint32_t copy=std::min<uint32_t>(count-drop,decodedSamples_-samples);
    if (copy) memcpy(decoded_+samples*2,frame+drop,copy*2);
    samples+=copy;
  }
  opus_decoder_destroy(decoder);
  heap_caps_free(frame);
  return valid && offset==used_ && samples==decodedSamples_ && !skip;
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
    stop(); lastError_=0; resetQueue(); id_=lastId_=id;
    epoch_=esp_random(); if (!epoch_) epoch_=1;
    packetSize_=std::min<uint16_t>(value,std::max<int>(20,server_->getPeerMTU(control_.connectionId())-3));
    deadline_=now+kLeaseMs; message_="PC linked; microphone OFF";
    uint8_t caps[5]; put16(caps,packetSize_); put16(caps+2,10); caps[4]=1;
    reply(Caps,id_,kMaxBytes,caps,id==kOpusHelloId ? sizeof(caps) : 4); return;
  }
  if (!epoch_ || epoch!=epoch_) return;
  if (op==Ping && !size && id==id_) { deadline_=now+kLeaseMs; ack(Ping); return; }
  if (op==Arm || op==Begin || op==BeginOpus) {
    if ((op==Arm && !testPage_) || (op!=Arm && soundControl_ && soundControl_->isPlaying())) {
      fail(2); return;
    }
    if (!id || id<=lastId_) { fail(2); return; }
    stop(); lastError_=0; id_=lastId_=id;
    if ((op==Arm && (size || value)) ||
        (op==Begin && (size!=4 || (value!=16000 && value!=24000) ||
          get32(payload)<value/5 || get32(payload)%2 || get32(payload)>value*20)) ||
        (op==BeginOpus && (size!=12 || (value!=16000 && value!=24000) ||
          get32(payload)<4 || get32(payload)>kMaxBytes ||
          get32(payload+4)<value/10 || get32(payload+4)>value*10 ||
          get32(payload+8)>value/5))) { fail(1); return; }
    if (!allocate()) { fail(3); return; }
    deadline_=now+kLeaseMs;
    if (op==Arm) {
      state_=State::Armed; buttonReleased_=false;
      message_="Hold A to record (max 10s)";
    } else {
      rate_=value; total_=get32(payload);
      opus_=op==BeginOpus;
      if (opus_) { decodedSamples_=get32(payload+4); skipSamples_=get32(payload+8); }
      state_=State::Receiving;
      message_=opus_ ? "Receiving Opus via BLE" : "Receiving WAV via BLE";
    }
    ack(op); return;
  }
  if (id!=id_) return;
  deadline_=now+kLeaseMs;
  switch (op) {
    case Data:
      if (state_!=State::Receiving || !size || (!opus_ && size%2) || packet.size>packetSize_ ||
          value!=used_ || size>total_-used_) { fail(4); return; }
      memcpy(buffer_+used_,payload,size); used_+=size; ack(Data,used_); return;
    case Commit:
      if (state_!=State::Receiving || size || used_!=total_ || value!=total_) { fail(4); return; }
      state_=State::Loaded; message_="Ready to play"; ack(Commit,total_); return;
    case Play:
      if ((state_!=State::Loaded && state_!=State::Captured) || size || value) { fail(2); return; }
      if (opus_ && !decodeOpus()) { fail(14); return; }
      if (startStopWatchSpeaker(192)!=SpeakerStartResult::Ok) { fail(12); return; }
      speakerOwned_=true;
      if (!M5.Speaker.playRaw(reinterpret_cast<int16_t*>(opus_ ? decoded_ : buffer_),
          opus_ ? decodedSamples_ : used_/2,rate_,false,1,0,true)) { fail(13); return; }
      state_=State::Playing; message_="PLAYING / B: stop";
      reply(Playing,id_,opus_ ? decodedSamples_*2 : used_); return;
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

void AudioProbe::startRecording() {
  stopStopWatchSpeaker(); speakerOwned_=false;
  rate_=16000; used_=total_=0;
  if (!M5.Mic.begin()) { fail(9); return; }
  if (!queueRecordBlock()) { fail(10); return; }
  recordStarted_=blockStarted_; state_=State::Recording;
  message_="REC / release A to finish"; draw(); reply(Recording,id_);
}

void AudioProbe::finishRecording(bool limited) {
  M5.Mic.end(); blockPending_=false;
  stopStopWatchSpeaker(); speakerOwned_=false;  // shared audio rail off
  if (used_<3200) { fail(6); return; }
  state_=State::Captured; total_=used_;
  message_=limited ? "10s LIMIT / recording stopped" : "Recorded / microphone OFF";
  uint8_t flag=limited;
  reply(Recorded,id_,used_,&flag,1);
}

void AudioProbe::update(uint32_t now) {
  if (state_==State::Off) { resetQueue(); cancel_.store(false); overflow_.store(false); return; }
  if (control_.linkEpoch()!=link_ || !control_.audioPeerAllowed(control_.connectionId())) {
    if (buffer_ || epoch_) {
      stop(); epoch_=0; resetQueue();
      if (!lastError_) message_="BLE disconnected / stopped";
    }
    link_=control_.linkEpoch();
  }
  if (cancel_.exchange(false) || (testPage_ && M5.BtnB.wasPressed())) {
    stop(); resetQueue();
    if (!lastError_) message_="Stopped / microphone OFF";
    ack(Cancel);
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
    startRecording();
  }
  if (state_==State::Recording) {
    // Mic initialization/queueing can advance millis() after update's input.
    const uint32_t captureNow=millis();
    if (blockPending_ && !M5.Mic.isRecording()) { used_+=kBlockSamples*2; blockPending_=false; }
    if (blockPending_ && audioBlockTimedOut(captureNow,blockStarted_)) { fail(11); }
    else if (!blockPending_) {
      if (!M5.BtnA.isPressed() || used_>=kRecordBytes || captureNow-recordStarted_>=10000)
        finishRecording(used_>=kRecordBytes || captureNow-recordStarted_>=10000);
      else if (!queueRecordBlock()) fail(10);
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
  if (testPage_ && now-lastDraw_>=200) { lastDraw_=now; draw(); }
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
