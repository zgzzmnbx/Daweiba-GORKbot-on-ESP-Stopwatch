// SPDX-License-Identifier: AGPL-3.0-or-later
#include "sound_control.h"
#include "ble_control.h"
#include "builtin_sounds.h"
#include "speaker_output.h"
#include <BLE2902.h>
#include <M5Unified.h>
#include <algorithm>
#include <cstring>

namespace {
constexpr char kService[]="48f1c001-8a75-4db6-9c18-590f7e9b0a01";
constexpr char kCommand[]="48f1c002-8a75-4db6-9c18-590f7e9b0a01";
constexpr char kEvents[]="48f1c003-8a75-4db6-9c18-590f7e9b0a01";
uint16_t get16(const uint8_t* p) { return p[0] | (uint16_t(p[1])<<8); }
uint32_t get32(const uint8_t* p) { return get16(p) | (uint32_t(get16(p+2))<<16); }
void put16(uint8_t* p,uint16_t v) { p[0]=v; p[1]=v>>8; }
void put32(uint8_t* p,uint32_t v) { put16(p,v); put16(p+2,v>>16); }
}

bool SoundControl::attach(BLEServer* server) {
  auto* service=server->createService(kService);
  if (!service) return false;
  auto* command=service->createCharacteristic(kCommand,BLECharacteristic::PROPERTY_WRITE);
  events_=service->createCharacteristic(kEvents,BLECharacteristic::PROPERTY_READ|BLECharacteristic::PROPERTY_NOTIFY);
  if (!command || !events_) return false;
  command->setAccessPermissions(ESP_GATT_PERM_WRITE_ENCRYPTED); command->setCallbacks(this);
  events_->setAccessPermissions(ESP_GATT_PERM_READ_ENCRYPTED);
  auto* cccd=new BLE2902();
  cccd->setAccessPermissions(ESP_GATT_PERM_READ_ENCRYPTED|ESP_GATT_PERM_WRITE_ENCRYPTED);
  events_->addDescriptor(cccd); service->start(); return true;
}

void SoundControl::onWrite(BLECharacteristic*,esp_ble_gatts_cb_param_t* param) {
  if (!param || !control_.audioPeerAllowed(param->write.conn_id)) return;
  const auto& w=param->write;
  if (w.len!=kFrameSize || w.is_prep || w.offset || w.value[0]!=kVersion || !get16(w.value+2)) return;
  if (w.value[1]==Stop) { stopRequestId_.store(get16(w.value+2)); stopRequested_.store(true); return; }
  portENTER_CRITICAL(&mux_);
  if (count_<8) { auto& f=queue_[(head_+count_)%8]; memcpy(f.bytes,w.value,kFrameSize); f.link=control_.linkEpoch(); ++count_; }
  portEXIT_CRITICAL(&mux_);
}

void SoundControl::setInitialVolume(uint8_t value) { volume_=std::min<uint8_t>(100,value); if(volume_)lastNonZeroVolume_=volume_; }
void SoundControl::setLocalVolume(uint8_t value) { volume_=std::min<uint8_t>(100,value); if(volume_)lastNonZeroVolume_=volume_; volumeChanged_=true; }
void SoundControl::toggleMute(){setLocalVolume(volume_?0:lastNonZeroVolume_);}
bool SoundControl::preview(uint8_t soundId) {
  if(playing_ || volume_==0)return false;
  size_t samples=0; const int16_t* pcm=sound(soundId,&samples); if(!pcm)return false;
  if(!startPlayback(pcm,samples))return false;
  activeRequest_=0;activeSound_=soundId;playing_=true;link_=control_.linkEpoch();return true;
}
bool SoundControl::takeVolumeChanged(uint8_t* value) { if (!volumeChanged_) return false; volumeChanged_=false; if(value)*value=volume_; return true; }
bool SoundControl::takeButtonBConsumed() { const bool value=buttonBConsumed_; buttonBConsumed_=false; return value; }
const int16_t* SoundControl::sound(uint8_t id,size_t* samples) const {
  for (const auto& item:gork_sounds::kCatalog) if(item.id==id){*samples=item.samples; return item.pcm;} return nullptr;
}
void SoundControl::reply(uint8_t op,uint16_t id,uint32_t value,uint8_t arg,bool terminal) {
  uint8_t frame[kFrameSize]={kVersion,op}; put16(frame+2,id); put32(frame+4,value); frame[8]=arg;
  control_.sendNotification(events_,frame,sizeof(frame));
  if(terminal && id){ auto& item=terminal_[terminalHead_]; item.id=id; item.op=op; item.arg=arg; item.value=value; item.link=control_.linkEpoch(); terminalHead_=(terminalHead_+1)%8; }
}
void SoundControl::fail(uint16_t id,Error error){ reply(Failed,id,error,activeSound_,true); }
bool SoundControl::replayTerminal(uint16_t id) {
  for(const auto& item:terminal_) if(item.id==id && item.link==control_.linkEpoch()){
    reply(item.op,item.id,item.value,item.arg); return true;
  }
  return false;
}
void SoundControl::stopNow(){ stopStopWatchSpeaker(); playing_=false; drainedAt_=0; activeSound_=0; }

bool SoundControl::startPlayback(const int16_t* pcm,size_t samples) {
  if(!pcm || !samples)return false;
  const auto result=startStopWatchSpeaker(
      (volume_*255+50)/100, SpeakerGainProfile::BuiltInLoud);
  hardwareStatus_=speakerStartResultText(result);
  if(result!=SpeakerStartResult::Ok)return false;
  if(!M5.Speaker.playRaw(pcm,samples,16000,false,1,0,true)){
    hardwareStatus_="PCM queue failed";
    stopStopWatchSpeaker();
    return false;
  }
  hardwareStatus_="playing";
  return true;
}

void SoundControl::process(const Frame& frame,uint32_t) {
  const auto* p=frame.bytes; const uint8_t op=p[1],arg=p[8]; const uint16_t id=get16(p+2); const uint32_t value=get32(p+4);
  if(frame.link!=control_.linkEpoch())return;
  if(replayTerminal(id))return;
  if(playing_ && id==activeRequest_){ reply(Started,id,volume_,activeSound_); return; }
  if(op==Caps){ reply(Status,id,0x0f,6,true); return; }
  if(op==Catalog){ reply(Status,id,6,1,true); return; }
  if(op==GetStatus){ reply(Status,id,volume_,playing_?activeSound_:0,true); return; }
  if(op==SetVolume){ if(value>100){fail(id,BadFrame);return;} setLocalVolume(value); reply(Completed,id,volume_,0,true); return; }
  if(op!=Play || value){ fail(id,BadFrame); return; }
  if(playing_){ fail(id,Busy); return; }
  size_t samples=0; const int16_t* pcm=sound(arg,&samples); if(!pcm){fail(id,UnknownSound);return;}
  reply(Accepted,id,volume_,arg);
  if(volume_==0){ reply(Completed,id,0,arg,true); return; }
  if(!startPlayback(pcm,samples)){ fail(id,Speaker); return; }
  activeRequest_=id; activeSound_=arg; playing_=true; link_=control_.linkEpoch(); reply(Started,id,volume_,arg);
}

void SoundControl::update(uint32_t now,bool blocked) {
  if(playing_ && M5.BtnB.wasPressed()){ buttonBConsumed_=true; stopRequestId_.store(activeRequest_); stopRequested_.store(true); }
  if(stopRequested_.exchange(false)){ const auto id=stopRequestId_.exchange(0); if(!replayTerminal(id)){const auto soundId=activeSound_; stopNow(); reply(Stopped,id,0,soundId,true);} }
  if(playing_ && activeRequest_ && (blocked || link_!=control_.linkEpoch() || !control_.audioPeerAllowed(control_.connectionId()))) stopNow();
  Frame frame; bool have=false; portENTER_CRITICAL(&mux_); if(count_){frame=queue_[head_];head_=(head_+1)%8;--count_;have=true;} portEXIT_CRITICAL(&mux_);
  if(have){ const uint16_t id=get16(frame.bytes+2); if(blocked)fail(id,Blocked); else process(frame,now); }
  if(playing_ && !M5.Speaker.isPlaying()){ if(!drainedAt_)drainedAt_=now; if(now-drainedAt_>=100){const auto id=activeRequest_;const auto soundId=activeSound_;stopNow();hardwareStatus_="completed";reply(Completed,id,0,soundId,true);} }
}
