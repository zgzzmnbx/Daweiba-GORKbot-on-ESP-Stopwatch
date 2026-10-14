"""Execute production GATT registration against a bounded handle allocator.

Checks upgrade compatibility with the retained pre-Wi-Fi source, not Windows
cache behaviour or real radio connectivity. Uses the existing offline compiler.
"""
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
FW = ROOT / '03-Src/stopwatch-grok-avatar/src'
OUT = ROOT / 'Codex-Temp/gatt-upgrade'


def body(source, signature):
    start = source.index('{', source.index(signature))
    end, depth = start + 1, 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[start:end]


def registration(source):
    begin = source.index('  service_ = server_->createService(kServiceUuid);')
    end = source.index('  return true;', source.index('  initialized_ = true;', begin))
    return '{\n' + source[begin:end] + '  return true;\n}'


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    legacy = ROOT / 'tools/fixtures/gatt-pre-wifi-registration.cpp.inc'
    before = ROOT / 'tools/fixtures/gatt-v0111-registration.cpp.inc'
    if not legacy.exists() or not before.exists():
        raise SystemExit('Retained upgrade baselines are required; do not substitute current source.')
    stub = r'''
#include <cassert>
#include <iostream>
#include <memory>
#include <string>
#include <vector>
constexpr int ESP_GATT_PERM_READ_ENCRYPTED=1,ESP_GATT_PERM_WRITE_ENCRYPTED=2;
struct BLE2902 {void setAccessPermissions(int){}};
struct BLECharacteristic {
 enum {PROPERTY_WRITE=1,PROPERTY_WRITE_NR=2,PROPERTY_READ=4,PROPERTY_NOTIFY=8};
 void setAccessPermissions(int){} void setCallbacks(void*){}
 void addDescriptor(BLE2902* d){delete d;} void setValue(const char*){}
};
struct BLEService {
 std::string uuid; unsigned handle; std::vector<std::unique_ptr<BLECharacteristic>> chars;
 BLECharacteristic* createCharacteristic(const char*,int){chars.emplace_back(new BLECharacteristic);return chars.back().get();}
 BLECharacteristic* getCharacteristic(const char*){return nullptr;}
 void start(){}
};
struct BLEAdvertising {void addServiceUUID(const char*){}void setScanResponse(bool){}};
struct BLEServer {
 unsigned next=40; std::string fail; std::vector<std::unique_ptr<BLEService>> services;
 BLEAdvertising advertising;
 BLEService* createService(const char* uuid){
  if(fail==uuid)return nullptr;
  services.emplace_back(new BLEService{uuid,next,{}});next+=15;return services.back().get();
 }
 BLEAdvertising* getAdvertising(){return &advertising;}
 unsigned handle(const char* uuid){for(auto& s:services)if(s->uuid==uuid)return s->handle;return 0;}
};
struct BLEDevice {static inline bool stopped=false;static void deinit(bool){stopped=true;}};
'''
    uuids = {name: f'48f1{code}001-8a75-4db6-9c18-590f7e9b0a01' for name, code in [('expression','a'),('audio','b'),('sound','c'),('network','d')]}
    source = stub
    for klass, file, code in [('AudioProbe','audio_probe.cpp','b'),('SoundControl','sound_control.cpp','c'),('NetworkControl','network_control.cpp','d')]:
        text = (FW / file).read_text(encoding='utf-8-sig')
        consts = text[text.index('constexpr char kService[]'):text.index(';',text.index('constexpr char kEvents[]' if klass!='NetworkControl' else 'constexpr char kVoice[]'))+1]
        source += f'namespace {klass}NS {{\n{consts}\nstruct {klass} {{ BLEServer* server_=nullptr; BLECharacteristic* events_=nullptr; BLECharacteristic* statusCharacteristic_=nullptr; BLECharacteristic* voiceCharacteristic_=nullptr; bool attach(BLEServer* server) {body(text, f"bool {klass}::attach(")} }};\n}}\n'
    source += f'''
using AudioProbe=AudioProbeNS::AudioProbe;using SoundControl=SoundControlNS::SoundControl;using NetworkControl=NetworkControlNS::NetworkControl;
constexpr const char* kServiceUuid="{uuids['expression']}";
constexpr const char* kCommandUuid="48f1a002-8a75-4db6-9c18-590f7e9b0a01";
constexpr const char* kStatusUuid="48f1a003-8a75-4db6-9c18-590f7e9b0a01";
struct Owner {{
 explicit Owner(BLEServer* server):server_(server){{}}
 BLEServer* server_;BLEService* service_=nullptr;BLECharacteristic* commandCharacteristic_=nullptr;BLECharacteristic* statusCharacteristic_=nullptr;
 AudioProbe audio;SoundControl sound;NetworkControl network;
 AudioProbe* audioProbe_=&audio;SoundControl* soundControl_=&sound;NetworkControl* networkControl_=&network;
 int commandCallbacks_=0;bool initialized_=false;
 bool legacy(){registration(legacy.read_text(encoding='utf-8-sig'))}
 bool before(){registration(before.read_text(encoding='utf-8-sig'))}
 bool candidate(){registration((FW/'ble_control.cpp').read_text(encoding='utf-8-sig'))}
}};
int main(){{
 BLEServer oldServer,badServer,newServer;Owner old{{&oldServer}},bad{{&badServer}},now{{&newServer}};
 assert(old.legacy()&&bad.before()&&now.candidate());
 unsigned moved=0;
 for(auto uuid:{{"{uuids['expression']}","{uuids['audio']}","{uuids['sound']}"}}){{
  moved+=oldServer.handle(uuid)!=badServer.handle(uuid);
  assert(oldServer.handle(uuid)==newServer.handle(uuid));
  std::cout<<uuid<<" legacy="<<oldServer.handle(uuid)<<" before="<<badServer.handle(uuid)<<" candidate="<<newServer.handle(uuid)<<"\\n";
 }}
 assert(moved==2&&newServer.services.size()==4&&newServer.services.back()->uuid=="{uuids['network']}");
 for(auto uuid:{{"{uuids['expression']}","{uuids['audio']}","{uuids['sound']}","{uuids['network']}"}}){{
  BLEDevice::stopped=false;BLEServer failed;failed.fail=uuid;Owner owner{{&failed}};
  assert(!owner.candidate()&&!owner.initialized_&&BLEDevice::stopped);
 }}
 std::cout<<"PASS: all 3 old service ranges preserved; 2 moved before fix; 4 service failures stop BLE.\\n";
}}
'''
    path = OUT / 'gatt_upgrade.cpp'
    path.write_text(source, encoding='utf-8')
    compiler = shutil.which('g++')
    if compiler:
        executable = OUT / 'gatt_upgrade.exe'
        subprocess.run([compiler,'-std=c++17','-Wall','-Wextra',str(path),'-o',str(executable)],check=True)
        subprocess.run([str(executable)],check=True)
    else:
        subprocess.run(['docker','run','--rm','--network','none','-v',f'{OUT}:/work','-w','/work','weknora-bundle/docreader:v0.8.2-3c36e7e7','sh','-c','g++ -std=c++17 -Wall -Wextra gatt_upgrade.cpp -o /tmp/gatt_upgrade && /tmp/gatt_upgrade'],check=True)


if __name__ == '__main__':
    main()
