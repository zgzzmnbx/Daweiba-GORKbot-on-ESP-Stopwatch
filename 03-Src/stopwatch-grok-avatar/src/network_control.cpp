// SPDX-License-Identifier: AGPL-3.0-or-later
#include "network_control.h"
#include "network_setup.h"
#include "network_power.h"
#include <esp_bt.h>
#include "ble_control.h"
#include <WiFi.h>
#include <ESPmDNS.h>
#include <esp_heap_caps.h>
#include <esp_random.h>
#include <lwip/sockets.h>
#include <fcntl.h>
#include <mbedtls/ssl.h>
#include <mbedtls/ssl_ciphersuites.h>
#include <mbedtls/net_sockets.h>
#include <cstring>
#include <algorithm>
#include <M5Unified.h>
#include <BLE2902.h>
namespace {
constexpr char kService[]="48f1d001-8a75-4db6-9c18-590f7e9b0a01";
constexpr char kInput[]="48f1d002-8a75-4db6-9c18-590f7e9b0a01";
constexpr char kStatus[]="48f1d003-8a75-4db6-9c18-590f7e9b0a01";
constexpr char kVoice[]="48f1d004-8a75-4db6-9c18-590f7e9b0a01";
constexpr int kPort=7443;
int rng(void*,unsigned char* p,size_t n){esp_fill_random(p,n);return 0;}
int tx(void* ctx,const unsigned char* p,size_t n){int r=::send(*static_cast<int*>(ctx),p,n,0);return r>=0?r:(errno==EAGAIN||errno==EWOULDBLOCK?MBEDTLS_ERR_SSL_WANT_WRITE:MBEDTLS_ERR_NET_SEND_FAILED);}
int rx(void* ctx,unsigned char* p,size_t n){int r=::recv(*static_cast<int*>(ctx),p,n,0);return r>=0?r:(errno==EAGAIN||errno==EWOULDBLOCK?MBEDTLS_ERR_SSL_WANT_READ:MBEDTLS_ERR_NET_RECV_FAILED);}
NetworkControl::Frame* allocate(){return static_cast<NetworkControl::Frame*>(heap_caps_calloc(1,sizeof(NetworkControl::Frame),MALLOC_CAP_SPIRAM|MALLOC_CAP_8BIT));}
void release(NetworkControl::Frame* p){if(p){memset(p,0,sizeof(*p));heap_caps_free(p);}}
}
void NetworkControl::begin(){
  boot_=esp_random();if(!boot_)boot_=1;
  input_=xQueueCreate(4,sizeof(Frame*));output_=xQueueCreate(8,sizeof(Frame*));provision_=xQueueCreate(4,sizeof(Provision));
  prefs_.begin("gorknet",false);
  Config candidate{};
  if(prefs_.getBytesLength("config")==sizeof(candidate)&&prefs_.getBytes("config",&candidate,sizeof(candidate))==sizeof(candidate)&&candidate.magic==config_.magic&&candidate.crc==gorknet::crc(reinterpret_cast<const uint8_t*>(&candidate),offsetof(Config,crc))&&candidate.policy<=2&&candidate.power<=2&&candidate.ssid[32]==0&&candidate.password[63]==0&&candidate.identity[16]==0)config_=candidate;
  memset(&candidate,0,sizeof(candidate));
  if(input_&&output_&&provision_){xTaskCreatePinnedToCore(task,"gork-tls",12288,this,1,&worker_,0);}
  else status_="network resource failure";
}
void NetworkControl::prepareBluetooth(){
  // A first BLE enable can occur after Wi-Fi-only startup in performance mode.
  WiFi.setSleep(true);
}
bool NetworkControl::attach(BLEServer* server){
  auto* service=server->createService(kService);if(!service)return false;
  auto* input=service->createCharacteristic(kInput,BLECharacteristic::PROPERTY_WRITE);
  statusCharacteristic_=service->createCharacteristic(kStatus,BLECharacteristic::PROPERTY_READ);
  voiceCharacteristic_=service->createCharacteristic(kVoice,BLECharacteristic::PROPERTY_NOTIFY);
  auto* cccd=new BLE2902();cccd->setAccessPermissions(ESP_GATT_PERM_READ_ENCRYPTED|ESP_GATT_PERM_WRITE_ENCRYPTED);voiceCharacteristic_->addDescriptor(cccd);
  if(!input||!statusCharacteristic_)return false;
  input->setAccessPermissions(ESP_GATT_PERM_WRITE_ENCRYPTED);input->setCallbacks(this);
  statusCharacteristic_->setAccessPermissions(ESP_GATT_PERM_READ_ENCRYPTED);
  statusCharacteristic_->setValue("{\"protocol\":1,\"configured\":false}");service->start();return true;
}
void NetworkControl::onWrite(BLECharacteristic*,esp_ble_gatts_cb_param_t* p){
  if(!p||!ble_.audioPeerAllowed(p->write.conn_id)||!provision_||p->write.is_prep||p->write.offset||p->write.len<3||p->write.len>244)return;
  Provision packet;packet.size=p->write.len;packet.link=ble_.linkEpoch();memcpy(packet.data,p->write.value,packet.size);
  if(xQueueSend(provision_,&packet,0)!=pdTRUE)provisionOverflow_=true;
}
bool NetworkControl::save(Config candidate){
  candidate.crc=gorknet::crc(reinterpret_cast<const uint8_t*>(&candidate),offsetof(Config,crc));
  // NVS replaces one blob atomically; no half SSID/password/identity combinations.
  if(prefs_.putBytes("config",&candidate,sizeof(candidate))!=sizeof(candidate)){memset(&candidate,0,sizeof(candidate));return false;}
  // Delay applying the saved blob until the settings reply has drained.
  nextConfig_=candidate;applyAt_=millis()+300;if(!applyAt_)applyAt_=1;
  memset(&candidate,0,sizeof(candidate));return true;
}
void NetworkControl::provision(const Provision& p){
  if(p.link!=ble_.linkEpoch()||!ble_.authorized()||p.data[0]!=1)return;
  const uint8_t op=p.data[1],id=p.data[2];
  if(op==0&&p.size==4&&p.data[3]>=52&&p.data[3]<=sizeof(pending_)){
    memset(pending_,0,sizeof(pending_));expected_=p.data[3];used_=0;configId_=id;configLink_=p.link;configDeadline_=millis()+15000;return;
  }
  if(op==1&&p.size>=5&&id==configId_&&expected_&&p.link==configLink_&&p.data[3]==used_&&used_+p.size-4<=expected_){memcpy(pending_+used_,p.data+4,p.size-4);used_+=p.size-4;return;}
  if(op==2&&p.size==3&&id==configId_&&expected_&&used_==expected_&&p.link==configLink_){
    const uint8_t a=pending_[0];
    if(a>0&&a<=32&&1+a<used_){
      const uint8_t b=pending_[1+a];
      if(b>=8&&b<=63&&2+a+b+48==used_&&!memchr(pending_+1,0,a)&&!memchr(pending_+2+a,0,b)){
        Config c{};memcpy(c.ssid,pending_+1,a);memcpy(c.password,pending_+2+a,b);memcpy(c.key,pending_+2+a+b,32);memcpy(c.identity,pending_+34+a+b,16);
        bool valid=true;for(int i=0;i<16;++i)if(!isxdigit(c.identity[i]))valid=false;
        uint8_t any=0;for(auto v:c.key)any|=v;
        if(valid&&any&&save(c))status_="configuration saved";
        else status_="configuration rejected";
        memset(&c,0,sizeof(c));
      }
    }
  }else if(op==3&&p.size==5)options(p.data[3],p.data[4]);
  else if(op==4&&p.size==3)forget();
  else if(op==5&&p.size==3)reconnect();
  else if(op==6&&p.size==4)delegate(p.data[3]!=0,false);
  memset(pending_,0,sizeof(pending_));expected_=used_=0;
}
bool NetworkControl::options(uint8_t policy,uint8_t power){if(policy>2||power>2)return false;Config c=config_;c.policy=policy;c.power=power;return save(c);}
bool NetworkControl::configureUsb(const uint8_t* payload,size_t size){
  if(applyAt_)return false;
  gorksetup::Fields fields;
  if(!gorksetup::decode(payload,size,fields))return false;
  Config candidate{};candidate.power=config_.power;
  memcpy(candidate.ssid,fields.ssid,sizeof(candidate.ssid));
  memcpy(candidate.password,fields.password,sizeof(candidate.password));
  memcpy(candidate.key,fields.key,sizeof(candidate.key));
  memcpy(candidate.identity,fields.identity,sizeof(candidate.identity));
  const bool result=save(candidate);
  gorksetup::wipe(&fields,sizeof(fields));gorksetup::wipe(&candidate,sizeof(candidate));
  if(result)status_="USB configuration saved";
  return result;
}
void NetworkControl::localBleOnly(){options(1,config_.power);}
void NetworkControl::reconnect(){reset_=true;nextRetry_=attempt_=0;}
void NetworkControl::forget(){Config c{};c.policy=1;save(c);status_="hotspot forgotten";}
String NetworkControl::address()const{return WiFi.status()==WL_CONNECTED?WiFi.localIP().toString():String("");}
bool NetworkControl::wifiJoined()const{return WiFi.status()==WL_CONNECTED&&uint32_t(WiFi.localIP())!=0;}
void NetworkControl::delegate(bool enabled,bool network){voiceDeadline_=enabled?millis()+6000:0;voiceNetwork_=network;voiceLink_=network?link_.load():ble_.linkEpoch();}
bool NetworkControl::delegated()const{return voiceDeadline_&&int32_t(millis()-voiceDeadline_)<0&&(voiceNetwork_?(ready()&&link_.load()==voiceLink_):(ble_.authorized()&&ble_.linkEpoch()==voiceLink_));}
void NetworkControl::voiceEvent(uint8_t code){
  if(!delegated())return;
  if(voiceNetwork_)send(134,0,&code,1,session_);
  else if(voiceCharacteristic_)ble_.sendNotification(voiceCharacteristic_,&code,1);
}
String NetworkControl::publicStatus()const{
  char out[512];String ip=address();
  snprintf(out,sizeof(out),"{\"protocol\":1,\"boot\":%lu,\"session\":%lu,\"configured\":%s,\"identity\":\"%.16s\",\"address\":\"%s\",\"port\":7443,\"policy\":%u,\"power\":%u,\"effective_power\":%u,\"source\":\"%s\",\"state\":\"%s\",\"authenticated\":%s,\"free_heap\":%u,\"largest_heap\":%u,\"free_psram\":%u}",static_cast<unsigned long>(boot_),static_cast<unsigned long>(session_.load()),config_.ssid[0]?"true":"false",config_.identity,ip.c_str(),config_.policy,config_.power,effectivePower_,powerSource_,status_.load(),ready()?"true":"false",ESP.getFreeHeap(),heap_caps_get_largest_free_block(MALLOC_CAP_INTERNAL),ESP.getFreePsram());return String(out);
}
void NetworkControl::update(uint32_t now,bool busy){
  if(provisionOverflow_.exchange(false)){memset(pending_,0,sizeof(pending_));expected_=used_=0;status_="configuration queue overflow";}
  if(applyAt_&&!busy&&int32_t(now-applyAt_)>=0){
    const bool hotspotChanged=strcmp(config_.ssid,nextConfig_.ssid)||strcmp(config_.password,nextConfig_.password);
    if(mdns_){MDNS.end();mdns_=false;}
    reset_=true;
    if(hotspotChanged&&wifiStarted_){WiFi.disconnect(true,false);wifiStarted_=false;}
    portENTER_CRITICAL(&configMux_);config_=nextConfig_;++configRevision_;portEXIT_CRITICAL(&configMux_);
    memset(&nextConfig_,0,sizeof(nextConfig_));applyAt_=0;nextRetry_=attempt_=0;
  }
  Provision p;while(provision_&&xQueueReceive(provision_,&p,0)==pdTRUE){provision(p);memset(&p,0,sizeof(p));}
  if(expected_&&(int32_t(now-configDeadline_)>=0||configLink_!=ble_.linkEpoch())){memset(pending_,0,sizeof(pending_));expected_=used_=0;}
  if(now-lastPower_>=1000){lastPower_=now;auto source=M5.Power.M5pm1.getPowerSource();
    powerSource_=(source==m5::M5PM1_Class::vin||source==m5::M5PM1_Class::vinout)?"external":source==m5::M5PM1_Class::battery?"battery":"unknown";
  }
  uint8_t wanted=config_.power?config_.power:(!strcmp(powerSource_,"external")?1:2);
  const bool bluetoothEnabled=esp_bt_controller_get_status()==ESP_BT_CONTROLLER_STATUS_ENABLED;
  if(!busy&&wanted!=effectivePower_)effectivePower_=wanted;
  const bool sleep=gorknet::modemSleep(effectivePower_,bluetoothEnabled);
  if(wifiStarted_&&bool(WiFi.getSleep())!=sleep)WiFi.setSleep(sleep);
  if(config_.policy==1||!config_.ssid[0]){
    if(wifiStarted_){reset_=true;WiFi.disconnect(true,false);wifiStarted_=false;if(mdns_){MDNS.end();mdns_=false;}}
  }else if(!worker_){status_="TLS worker unavailable";}
  else if(WiFi.status()==WL_CONNECTED){
    attempt_=0;
    if(!mdns_){char name[32];snprintf(name,sizeof(name),"gork-%s",config_.identity);mdns_=MDNS.begin(name);if(mdns_)MDNS.addService("gork-watch","tcp",7443);}
    if(!ready())status_="hotspot connected; waiting PC";
  }else if(!busy&&int32_t(now-nextRetry_)>=0){
    WiFi.setSleep(gorknet::modemSleep(effectivePower_,bluetoothEnabled));
    WiFi.mode(WIFI_STA);WiFi.setAutoReconnect(false);WiFi.persistent(false);WiFi.begin(config_.ssid,config_.password);wifiStarted_=true;
    static const uint32_t perf[]={5000,15000,30000,60000},eco[]={15000,60000,120000,300000};
    const auto* waits=effectivePower_==1?perf:eco;nextRetry_=now+waits[std::min<uint32_t>(attempt_++,3)]+esp_random()%1000;
    status_=WiFi.status()==WL_CONNECT_FAILED?"hotspot authentication failed":"connecting / retry backoff";
  }
  if(statusCharacteristic_){static uint32_t last=0;if(now-last>=500){last=now;auto s=publicStatus();statusCharacteristic_->setValue(s.c_str());}}
}
bool NetworkControl::send(uint8_t kind,uint32_t request,const uint8_t* data,size_t size,uint32_t session){
  if(!output_||size>gorknet::MaxPayload||!ready())return false;
  auto* p=allocate();if(!p)return false;p->kind=kind;p->request=request;p->session=session;p->size=size;if(size)memcpy(p->data,data,size);
  if(xQueueSend(output_,&p,0)!=pdTRUE){release(p);reset_=true;return false;}return true;
}
void NetworkControl::reply(const Frame& p,const char* result,bool error){send(error?255:128,p.request,reinterpret_cast<const uint8_t*>(result),strlen(result),p.session);}
bool NetworkControl::audioReply(const uint8_t* data,size_t n){return send(133,0,data,n,session_);}
NetworkControl::Frame* NetworkControl::take(){Frame* p=nullptr;if(input_)xQueueReceive(input_,&p,0);return p;}
void NetworkControl::task(void* self){static_cast<NetworkControl*>(self)->serve();}
void NetworkControl::serve(){
  for(;;){
    Config config;portENTER_CRITICAL(&configMux_);config=config_;uint32_t revision=configRevision_;portEXIT_CRITICAL(&configMux_);
    if(config.policy==1||!config.ssid[0]||WiFi.status()!=WL_CONNECTED){memset(&config,0,sizeof(config));vTaskDelay(pdMS_TO_TICKS(100));continue;}
    int listener=socket(AF_INET,SOCK_STREAM,0);if(listener<0){vTaskDelay(pdMS_TO_TICKS(1000));continue;}
    int yes=1;setsockopt(listener,SOL_SOCKET,SO_REUSEADDR,&yes,sizeof(yes));sockaddr_in addr{};addr.sin_family=AF_INET;addr.sin_port=htons(kPort);addr.sin_addr.s_addr=INADDR_ANY;
    if(bind(listener,reinterpret_cast<sockaddr*>(&addr),sizeof(addr))||listen(listener,1)){close(listener);vTaskDelay(pdMS_TO_TICKS(1000));continue;}
    fcntl(listener,F_SETFL,O_NONBLOCK);
    while(WiFi.status()==WL_CONNECTED&&configRevision_==revision){
      int fd=accept(listener,nullptr,nullptr);if(fd<0){vTaskDelay(pdMS_TO_TICKS(20));continue;}
      fcntl(fd,F_SETFL,O_NONBLOCK);reset_=false;
      mbedtls_ssl_context ssl;mbedtls_ssl_config conf;mbedtls_ssl_init(&ssl);mbedtls_ssl_config_init(&conf);
      const int suites[]={MBEDTLS_TLS_PSK_WITH_AES_128_GCM_SHA256,0};
      int result=mbedtls_ssl_config_defaults(&conf,MBEDTLS_SSL_IS_SERVER,MBEDTLS_SSL_TRANSPORT_STREAM,MBEDTLS_SSL_PRESET_DEFAULT);
      mbedtls_ssl_conf_rng(&conf,rng,nullptr);mbedtls_ssl_conf_min_version(&conf,MBEDTLS_SSL_MAJOR_VERSION_3,MBEDTLS_SSL_MINOR_VERSION_3);mbedtls_ssl_conf_max_version(&conf,MBEDTLS_SSL_MAJOR_VERSION_3,MBEDTLS_SSL_MINOR_VERSION_3);mbedtls_ssl_conf_ciphersuites(&conf,suites);
      if(!result)result=mbedtls_ssl_conf_psk(&conf,config.key,32,reinterpret_cast<const uint8_t*>(config.identity),16);
      if(!result)result=mbedtls_ssl_setup(&ssl,&conf);
      mbedtls_ssl_set_bio(&ssl,&fd,tx,rx,nullptr);
      uint32_t deadline=millis()+5000;
      if(!result){do{result=mbedtls_ssl_handshake(&ssl);if(result==MBEDTLS_ERR_SSL_WANT_READ||result==MBEDTLS_ERR_SSL_WANT_WRITE)vTaskDelay(pdMS_TO_TICKS(2));else break;}while(!reset_&&int32_t(millis()-deadline)<0);}
      if(result==0&&!reset_){
        session_=esp_random();if(!session_)session_=1;++link_;authenticated_=true;recent_={};status_="authenticated PC";
        size_t got=0,need=gorknet::Header;auto* incoming=allocate();uint8_t header[gorknet::Header]{};uint32_t last=millis(),partial=0;
        while(incoming&&!reset_&&WiFi.status()==WL_CONNECTED&&configRevision_==revision){
          // Write at most one frame each pass. CANCEL/input is serviced between frames.
          Frame* out=nullptr;
          if(xQueueReceive(output_,&out,0)==pdTRUE){
            if(out->session==session_){
              auto* entry=recent_.find(out->request);if(entry&&(out->kind==128||out->kind==255)&&out->size<sizeof(entry->result)){memcpy(entry->result,out->data,out->size);entry->result[out->size]=0;entry->error=out->kind==255;entry->completed=true;}
              uint8_t h[gorknet::Header];gorknet::header(h,out->kind,out->size,boot_,session_,out->request,out->data);
              bool valid=true;for(int part=0;part<2&&valid;++part){const uint8_t* bytes=part?out->data:h;size_t n=part?out->size:sizeof(h),sent=0;uint32_t until=millis()+2000;
                while(sent<n){int r=mbedtls_ssl_write(&ssl,bytes+sent,n-sent);if(r>0)sent+=r;else if((r==MBEDTLS_ERR_SSL_WANT_READ||r==MBEDTLS_ERR_SSL_WANT_WRITE)&&int32_t(millis()-until)<0&&!reset_)vTaskDelay(pdMS_TO_TICKS(1));else{valid=false;break;}}}
              if(!valid)reset_=true;
            }release(out);
          }
          uint8_t* dest=got<gorknet::Header?header+got:incoming->data+got-gorknet::Header;
          int r=mbedtls_ssl_read(&ssl,dest,need-got);
          if(r>0){if(!partial)partial=millis();got+=r;last=millis();
            if(got==gorknet::Header&&need==gorknet::Header){if(!gorknet::validHeader(header)){reset_=true;break;}incoming->kind=header[3];incoming->size=gorknet::u16(header+4);incoming->request=gorknet::u32(header+16);incoming->session=session_;need+=incoming->size;}
            if(got==need){
              const bool hello=incoming->kind==0&&incoming->size==0&&gorknet::u32(header+8)==0&&gorknet::u32(header+12)==0;
              if((!hello&&(gorknet::u32(header+8)!=boot_||gorknet::u32(header+12)!=session_))||gorknet::crc(incoming->data,incoming->size)!=gorknet::u32(header+20)){reset_=true;break;}
              auto* old=recent_.find(incoming->request);
              if(old){if(old->hash==gorknet::u32(header+20)&&old->kind==incoming->kind){if(old->completed)reply(*incoming,old->result,old->error);else reply(*incoming,"result pending/unavailable; no replay",true);}else reply(*incoming,"conflicting request",true);}
              else if(!recent_.fresh(incoming->request))reply(*incoming,"unknown old request; no replay",true);
              else {auto& entry=recent_.add(incoming->request,gorknet::u32(header+20),incoming->kind);strncpy(entry.result,"accepted",sizeof(entry.result));
                if(xQueueSend(input_,&incoming,0)!=pdTRUE){reset_=true;break;}incoming=allocate();}
              got=0;need=gorknet::Header;partial=0;
            }
          }else if(r!=MBEDTLS_ERR_SSL_WANT_READ&&r!=MBEDTLS_ERR_SSL_WANT_WRITE){break;}
          if(millis()-last>15000||(partial&&millis()-partial>5000))break;
          vTaskDelay(pdMS_TO_TICKS(1));
        }
        release(incoming);
      }
      authenticated_=false;++link_;session_=0;
      Frame* stale=nullptr;while(xQueueReceive(output_,&stale,0)==pdTRUE)release(stale);
      while(xQueueReceive(input_,&stale,0)==pdTRUE)release(stale);
      mbedtls_ssl_free(&ssl);mbedtls_ssl_config_free(&conf);close(fd);
    }
    close(listener);
    memset(&config,0,sizeof(config));
  }
}
