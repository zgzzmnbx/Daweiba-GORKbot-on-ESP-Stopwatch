"""Exercise the actual firmware USB dispatch with a host serial transport."""
from pathlib import Path
import subprocess
from test_gatt_upgrade import body
root=Path(__file__).resolve().parents[1]
out=root/'Codex-Temp/wifi-usb-v0201/native';out.mkdir(parents=True,exist_ok=True)
source=(root/'03-Src/stopwatch-grok-avatar/src/main.cpp').read_text(encoding='utf-8')
stub=r'''
#include "network_setup.h"
#include <cassert>
#include <string>
#include <cstdarg>
#include <cstdio>
using String=std::string;
struct SerialStub {
 std::string input,output;
 int available(){return input.size();}
 char read(){char c=input[0];input.erase(0,1);return c;}
 void println(const char* s){output+=s;output+='\n';}
 void printf(const char* fmt,...){char b[1024];va_list a;va_start(a,fmt);vsnprintf(b,sizeof(b),fmt,a);va_end(a);output+=b;}
} Serial;
struct Audio {bool active=false;bool busy(){return active;}} audioProbe;
struct Sound {bool active=false;bool isPlaying(){return active;}} soundControl;
struct Network {int sets=0;bool configureUsb(const uint8_t*,size_t){sets++;return true;}String publicStatus(){return "{}";}} networkControl;
const char* kFirmwareVersion="test";bool menuOpen=false,serialOverflow=false;
char serialLine[gorksetup::MaxLine]{};size_t serialUsed=0;uint32_t serialLastByte=0;
std::string expression;
void dispatchExpressionCommand(String s,uint32_t,const char*){expression=s;}
void handleSerialCommands(uint32_t nowMs)
'''
tests=r'''
void input(std::string s,uint32_t t=100){Serial.input=s;handleSerialCommands(t);}
int main(){
 input("idle\n");assert(expression=="idle");expression.clear();
 menuOpen=true;input("GWUSB1 00000001 HELLO\n");assert(Serial.output.find("StopWatch-Gork")!=std::string::npos);
 input("idle\n");assert(expression.empty());menuOpen=false;
 Serial.output.clear();input("GWUSB2 00000001 SET secret\n");assert(expression.empty()&&Serial.output.find("secret")==std::string::npos);
 input(std::string(500,'x')+"\n");assert(expression.empty()&&serialUsed==0&&!serialOverflow);
 input("GWUSB1 partial-secret");assert(serialUsed>0);handleSerialCommands(2101);assert(serialUsed==0);
 for(char c:serialLine)assert(c==0);
 uint8_t p[59]{};p[0]=1;p[1]='s';p[2]=8;memset(p+3,'p',8);memset(p+11,'k',32);memcpy(p+43,"123456789abcdef0",16);
 char h[32],hex[3];snprintf(h,sizeof(h),"GWUSB1 00000001 SET %08x ",gorknet::crc(p,59));std::string cmd=h;
 for(auto b:p){snprintf(hex,sizeof(hex),"%02x",b);cmd+=hex;}cmd+='\n';
 audioProbe.active=true;input(cmd);assert(networkControl.sets==0);audioProbe.active=false;
 soundControl.active=true;input(cmd);assert(networkControl.sets==0);soundControl.active=false;
 input(cmd);assert(networkControl.sets==1);for(char c:serialLine)assert(c==0);
 puts("Production USB dispatch: legacy commands, menu handshake, no secret echo, bounded input, timeout, busy guard PASS");
}
'''
(out/'dispatch.cpp').write_text(stub+body(source,'void handleSerialCommands(')+tests,encoding='utf-8')
subprocess.run(['docker','run','--rm','--network','none','-v',f'{root}:/project','-w','/project','weknora-bundle/docreader:v0.8.2-3c36e7e7','sh','-c','g++ -std=c++17 -Wall -Wextra -Werror -I03-Src/stopwatch-grok-avatar/src Codex-Temp/wifi-usb-v0201/native/dispatch.cpp -o /tmp/dispatch && /tmp/dispatch'],check=True)
