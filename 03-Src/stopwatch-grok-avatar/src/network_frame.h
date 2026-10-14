// SPDX-License-Identifier: AGPL-3.0-or-later
#pragma once
#include <stdint.h>
#include <stddef.h>
namespace gorknet {
constexpr size_t Header=24, MaxPayload=4096;
inline uint16_t u16(const uint8_t* p){return p[0]|uint16_t(p[1])<<8;}
inline uint32_t u32(const uint8_t* p){return u16(p)|uint32_t(u16(p+2))<<16;}
inline void p16(uint8_t* p,uint16_t v){p[0]=v;p[1]=v>>8;}
inline void p32(uint8_t* p,uint32_t v){p16(p,v);p16(p+2,v>>16);}
inline uint32_t crc(const uint8_t* p,size_t n){uint32_t c=~0U;while(n--){c^=*p++;for(int i=0;i<8;++i)c=(c>>1)^(0xEDB88320U&-(c&1));}return ~c;}
inline bool validHeader(const uint8_t* p){return p[0]=='G'&&p[1]=='W'&&p[2]==1&&u16(p+4)<=MaxPayload&&u16(p+6)==0;}
inline void header(uint8_t* p,uint8_t kind,uint16_t n,uint32_t boot,uint32_t session,uint32_t request,const uint8_t* data){p[0]='G';p[1]='W';p[2]=1;p[3]=kind;p16(p+4,n);p16(p+6,0);p32(p+8,boot);p32(p+12,session);p32(p+16,request);p32(p+20,crc(data,n));}
// Reject evicted/old requests rather than treating them as new. Recent results
// survive lost replies in this TLS session; a new session never resumes work.
struct Recent {
  struct Entry{uint32_t id=0,hash=0;uint8_t kind=0;bool completed=false,error=false;char result[80]{};} entries[32];
  uint32_t highest=0;size_t next=0;
  Entry* find(uint32_t id){for(auto& e:entries)if(id&&e.id==id)return &e;return nullptr;}
  bool fresh(uint32_t id){return id&&id>highest;}
  Entry& add(uint32_t id,uint32_t hash,uint8_t kind){auto& e=entries[next++%32];e={};e.id=id;e.hash=hash;e.kind=kind;highest=id;return e;}
};
}
