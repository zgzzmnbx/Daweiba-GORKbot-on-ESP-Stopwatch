"""Run production Wi-Fi power update/start and pre-BLE-enable snippets."""
from pathlib import Path
import subprocess
from test_gatt_upgrade import body
root=Path(__file__).resolve().parents[1];out=root/'Codex-Temp/wifi-usb-v0201/coexist';out.mkdir(parents=True,exist_ok=True)
s=(root/'03-Src/stopwatch-grok-avatar/src/network_control.cpp').read_text(encoding='utf-8')
update=s[s.index('  const bool bluetoothEnabled='):s.index('  if(config_.policy==1')]
start=s[s.index('    WiFi.setSleep(gorknet::modemSleep(effectivePower_,'):s.index('    static const uint32_t perf[]')]
cpp=r'''
#include "network_power.h"
#include <cassert>
#include <cstdio>
#include <string>
constexpr int ESP_BT_CONTROLLER_STATUS_ENABLED=1,WIFI_STA=1;
int bt=0;int esp_bt_controller_get_status(){return bt;}
struct Radio {bool sleeping=true;int begins=0;
 void setSleep(bool b){assert(!bt||b);sleeping=b;}
 int getSleep(){return sleeping;}
 void mode(int){}void setAutoReconnect(bool){}void persistent(bool){}
 void begin(const char*,const char*){assert(!bt||sleeping);begins++;}
} WiFi;
struct Controller {
 bool busy=false,wifiStarted_=false;uint8_t wanted=1,effectivePower_=2;
 struct {const char* ssid="dummy";const char* password="dummy-only";} config_;
 void update(){
'''+update+start+r'''
 }
 void prepareBluetooth()
'''+body(s,'void NetworkControl::prepareBluetooth()')+r'''
};
int main(){
 for(int bluetooth:{0,1})for(uint8_t power:{1,2}){
  bt=bluetooth;WiFi.sleeping=true;Controller c;c.wanted=power;c.update();
  assert(WiFi.sleeping==bool(power==2||bluetooth));
  c.prepareBluetooth();assert(WiFi.sleeping);bt=1;c.update();assert(WiFi.sleeping);
 }
 puts("Production coexist power/start/first BLE enable: all four power/radio combinations PASS");
}
'''
(out/'power.cpp').write_text(cpp,encoding='utf-8')
subprocess.run(['docker','run','--rm','--network','none','-v',f'{root}:/project','-w','/project','weknora-bundle/docreader:v0.8.2-3c36e7e7','sh','-c','g++ -std=c++17 -Wall -Wextra -Werror -I03-Src/stopwatch-grok-avatar/src Codex-Temp/wifi-usb-v0201/coexist/power.cpp -o /tmp/power && /tmp/power'],check=True)
