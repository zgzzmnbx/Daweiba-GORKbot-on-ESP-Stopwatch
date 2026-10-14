// SPDX-License-Identifier: AGPL-3.0-or-later
#pragma once
#include <cstring>
#include "network_frame.h"

namespace gorksetup {
constexpr size_t MaxPayload = 145, MaxLine = 384;
struct Fields { char ssid[33]{}, password[64]{}, identity[17]{}; uint8_t key[32]{}; };
inline void wipe(void* data,size_t size) {
  volatile uint8_t* bytes=static_cast<volatile uint8_t*>(data);
  while(size--)*bytes++=0;
}
inline int hex(char c) {
  return c>='0'&&c<='9'?c-'0':c>='a'&&c<='f'?c-'a'+10:c>='A'&&c<='F'?c-'A'+10:-1;
}
inline bool decode(const uint8_t* p, size_t n, Fields& out) {
  out={};
  if(!p||n<59||n>MaxPayload)return false;
  const size_t a=p[0];
  if(a==0||a>32||a+1>=n)return false;
  const size_t b=p[a+1];
  if(b<8||b>63||a+b+50!=n||memchr(p+1,0,a)||memchr(p+a+2,0,b))return false;
  const uint8_t* key=p+a+b+2;uint8_t any=0;
  for(size_t i=0;i<32;++i)any|=key[i];
  if(!any)return false;
  for(size_t i=0;i<16;++i)if(hex(static_cast<char>(key[32+i]))<0)return false;
  memcpy(out.ssid,p+1,a);memcpy(out.password,p+a+2,b);
  memcpy(out.key,key,32);memcpy(out.identity,key+32,16);return true;
}
enum class Op { Invalid, Hello, Status, Set };
struct Packet { uint32_t request=0;Op op=Op::Invalid;uint8_t data[MaxPayload]{};size_t size=0; };
inline bool number(const char* p,uint32_t& out) {
  out=0;for(size_t i=0;i<8;++i){const int v=hex(p[i]);if(v<0)return false;out=(out<<4)|v;}return true;
}
inline bool parse(const char* line,size_t n,Packet& packet) {
  packet={};
  if(!line||n<21||n>=MaxLine||memcmp(line,"GWUSB1 ",7)||line[15]!=' '||!number(line+7,packet.request)||!packet.request)return false;
  if(n==21&&!memcmp(line+16,"HELLO",5)){packet.op=Op::Hello;return true;}
  if(n==22&&!memcmp(line+16,"STATUS",6)){packet.op=Op::Status;return true;}
  uint32_t checksum=0;
  if(n<29||memcmp(line+16,"SET ",4)||line[28]!=' '||!number(line+20,checksum)||(n-29)%2||(n-29)/2>MaxPayload)return false;
  packet.size=(n-29)/2;
  for(size_t i=0;i<packet.size;++i){int a=hex(line[29+i*2]),b=hex(line[30+i*2]);if(a<0||b<0)return false;packet.data[i]=(a<<4)|b;}
  if(gorknet::crc(packet.data,packet.size)!=checksum)return false;
  Fields check;const bool valid=decode(packet.data,packet.size,check);wipe(&check,sizeof(check));
  if(valid)packet.op=Op::Set;
  return valid;
}
}
