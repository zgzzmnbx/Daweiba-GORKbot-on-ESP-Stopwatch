#include "network_setup.h"
#include "network_power.h"
#include <cassert>
#include <string>
#include <cstdio>
#include <vector>
using namespace gorksetup;
std::vector<uint8_t> payload(size_t a,size_t b){
  std::vector<uint8_t> v{static_cast<uint8_t>(a)};
  v.insert(v.end(),a,'s');v.push_back(b);v.insert(v.end(),b,'p');
  v.insert(v.end(),32,'k');const char* id="123456789abcdef0";v.insert(v.end(),id,id+16);return v;
}
std::string line(const std::vector<uint8_t>& v){
  char head[32];snprintf(head,sizeof(head),"GWUSB1 00000001 SET %08x ",gorknet::crc(v.data(),v.size()));
  std::string out=head;char h[3];for(auto b:v){snprintf(h,sizeof(h),"%02x",b);out+=h;}return out;
}
int main(){
  for(uint8_t power=1;power<=2;power++){
    assert(gorknet::modemSleep(power,true));
    assert(gorknet::modemSleep(power,false)==(power==2));
  }
  Fields f;Packet p;
  for(size_t a: {1U,32U})for(size_t b:{8U,63U}){
    auto v=payload(a,b);assert(decode(v.data(),v.size(),f));assert(strlen(f.ssid)==a&&strlen(f.password)==b);
    auto l=line(v);assert(parse(l.data(),l.size(),p)&&p.op==Op::Set&&p.size==v.size());
    l.back()=l.back()=='0'?'1':'0';assert(!parse(l.data(),l.size(),p));
    for(size_t n=0;n<v.size();n++)assert(!decode(v.data(),n,f));
  }
  for(const auto& v:{payload(0,8),payload(33,8),payload(1,7),payload(1,64)})assert(!decode(v.data(),v.size(),f));
  auto v=payload(1,8);v[1]=0;assert(!decode(v.data(),v.size(),f));
  v=payload(1,8);memset(v.data()+11,0,32);assert(!decode(v.data(),v.size(),f));
  v=payload(1,8);v.back()='z';auto invalid=line(v);assert(!parse(invalid.data(),invalid.size(),p));
  for(const std::string s:{"GWUSB1 00000000 HELLO","GWUSB1 0000000z HELLO","GWUSB2 00000001 HELLO","GWUSB1 00000001 HELLO extra"})assert(!parse(s.data(),s.size(),p));
  std::string hello="GWUSB1 00000001 HELLO",status="GWUSB1 00000002 STATUS";
  assert(parse(hello.data(),hello.size(),p)&&p.op==Op::Hello&&p.request==1);
  assert(parse(status.data(),status.size(),p)&&p.op==Op::Status&&p.request==2);
  puts("Production USB parser: boundaries, CRC, truncated requests, zero keys, malformed identity PASS");
}
