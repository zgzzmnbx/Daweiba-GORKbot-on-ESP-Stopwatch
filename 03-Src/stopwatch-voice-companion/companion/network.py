"""TLS 1.2 PSK transport. Identity is a per-device random secret provisioned
over encrypted, bound BLE, independent of the hotspot password. No plaintext
or certificate-based cipher can be negotiated by this context.
"""
from __future__ import annotations
import asyncio
import contextlib
from dataclasses import dataclass
import ipaddress
import json
import ssl
import struct
import time
import zlib
import os
import shutil
import subprocess

HEADER = struct.Struct('<2sBBHHIIII')
MAX_PAYLOAD = 4096
PORT = 7443
NET_INPUT = '48f1d002-8a75-4db6-9c18-590f7e9b0a01'
NET_STATUS = '48f1d003-8a75-4db6-9c18-590f7e9b0a01'

@dataclass(frozen=True)
class Frame:
    kind: int
    boot: int
    session: int
    request: int
    data: bytes = b''
    def encode(self):
        if len(self.data)>MAX_PAYLOAD or not 0<=self.kind<=255:
            raise ValueError('frame exceeds bounds')
        return HEADER.pack(b'GW',1,self.kind,len(self.data),0,self.boot,self.session,self.request,zlib.crc32(self.data))+self.data
    @classmethod
    async def read(cls, reader):
        h=await reader.readexactly(HEADER.size)
        magic,version,kind,n,flags,boot,session,request,crc=HEADER.unpack(h)
        if magic!=b'GW' or version!=1 or flags or n>MAX_PAYLOAD:
            raise ValueError('invalid network header')
        data=await reader.readexactly(n)
        if zlib.crc32(data)!=crc: raise ValueError('invalid network CRC')
        return cls(kind,boot,session,request,data)

def psk_context(identity: str, key: bytes):
    if len(key)!=32 or not identity or len(identity.encode())>32:
        raise ValueError('invalid device identity')
    if not getattr(ssl,'HAS_PSK',False): raise RuntimeError('Python 3.13+ with TLS-PSK required')
    ctx=ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.minimum_version=ctx.maximum_version=ssl.TLSVersion.TLSv1_2
    ctx.check_hostname=False
    ctx.verify_mode=ssl.CERT_NONE  # PSK authenticates both ends; certificates are not used.
    ctx.set_ciphers('PSK-AES128-GCM-SHA256')
    ctx.set_psk_client_callback(lambda hint:(identity,key))
    return ctx

def local_address(address):
    ip=ipaddress.ip_address(address)
    if ip.version!=4 or not ip.is_private or ip.is_loopback or ip.is_unspecified or ip.is_multicast or ip.is_link_local:
        raise ValueError('需要热点上的 IPv4 私有地址')
    if not any(ip in ipaddress.ip_network(n) for n in ('10.0.0.0/8','172.16.0.0/12','192.168.0.0/16')):
        raise ValueError('地址不在 RFC1918 本地网络')
    return str(ip)

def verify_wifi_subnet(address):
    """Only on-link Wi-Fi destinations; no route/firewall/network mutations."""
    if os.name!='nt':raise ConnectionError('此版本尚未提供该系统的热点接口校验')
    shell=shutil.which('pwsh') or shutil.which('powershell')
    if not shell:raise ConnectionError('无法核验当前 Wi-Fi 接口')
    script="[Console]::OutputEncoding=[Text.UTF8Encoding]::new(); $a=@(Get-NetAdapter | Where-Object {$_.NdisPhysicalMedium -eq 9 -and $_.Status -eq 'Up'}); @($a | ForEach-Object {Get-NetIPAddress -InterfaceIndex $_.ifIndex -AddressFamily IPv4} | Select-Object IPAddress,PrefixLength) | ConvertTo-Json -Compress"
    result=subprocess.run([shell,'-NoProfile','-Command',script],capture_output=True,encoding='utf-8',timeout=8,check=True)
    values=json.loads(result.stdout or '[]')
    if isinstance(values,dict):values=[values]
    ip=ipaddress.ip_address(address)
    if not any(ip in ipaddress.ip_network(f"{v['IPAddress']}/{v['PrefixLength']}",strict=False) and str(ip)!=v['IPAddress'] for v in values):
        raise ConnectionError('Watch 地址不在当前 Wi-Fi 接口的本地子网，请确认同连热点')

class WifiClient:
    def __init__(self):
        self.reader=self.writer=None
        self.boot=self.session=self.sequence=0
        self.pending={}
        self.listeners={}
        self.read_task=None
        self.lock=asyncio.Lock()
        self.last_success=0.0
        self.healthy_since=0.0
        self.successes=0
        self.error='未配网'
        self.address=''
        self.info={}
        self.voice_event=None
    @property
    def connected(self): return bool(self.writer and not self.writer.is_closing() and self.read_task and not self.read_task.done())
    @property
    def is_connected(self): return self.connected
    async def connect(self,address,identity,key):
        address=local_address(address)
        await asyncio.to_thread(verify_wifi_subnet,address)
        await self.disconnect()
        ctx=psk_context(identity,key)
        self.reader,self.writer=await asyncio.wait_for(asyncio.open_connection(address,PORT,ssl=ctx,server_hostname=None,ssl_handshake_timeout=5),7)
        if self.writer.get_extra_info('ssl_object').cipher()[0]!='PSK-AES128-GCM-SHA256':
            await self.disconnect();raise RuntimeError('TLS cipher mismatch')
        self.boot=self.session=self.sequence=0
        self.read_task=asyncio.create_task(self._read())
        try:
            result=await self.request(0)
            self.info=json.loads(result)
            if self.info.get('protocol')!=1 or not self.info.get('boot') or not self.info.get('session'):
                raise ValueError('invalid device hello')
            self.boot,self.session=self.info['boot'],self.info['session']
            self.address=address
            self.healthy_since=time.monotonic();self.successes=1;self.error=''
        except BaseException:
            await self.disconnect();raise
    async def _read(self):
        error=ConnectionError('Wi-Fi disconnected; current task interrupted')
        try:
            while True:
                frame=await Frame.read(self.reader)
                if self.boot and (frame.boot!=self.boot or frame.session!=self.session):
                    raise ValueError('stale device session')
                if frame.kind==134:
                    if self.voice_event and frame.data:self.voice_event(frame.data[0])
                elif frame.kind==133:
                    for callback in tuple(self.listeners.values()): callback(None,frame.data)
                else:
                    future=self.pending.get(frame.request)
                    if future and not future.done():
                        if frame.kind==255: future.set_exception(RuntimeError(frame.data.decode('utf-8','replace')))
                        elif frame.kind==128: future.set_result(frame.data)
                        else: raise ValueError('invalid reply kind')
                self.last_success=time.monotonic();self.successes+=1
        except asyncio.CancelledError: pass
        except Exception as exc:
            self.error=type(exc).__name__;error=ConnectionError('Wi-Fi interrupted; no replay')
        finally:
            if self.writer:self.writer.close()
            for future in self.pending.values():
                if not future.done():future.set_exception(error)
    async def request(self,kind,data=b'',timeout=5):
        if not self.connected:raise ConnectionError('Wi-Fi 未认证或已断开')
        self.sequence+=1
        if self.sequence>0xffffffff:raise ConnectionError('session ids exhausted')
        req=self.sequence
        future=asyncio.get_running_loop().create_future();self.pending[req]=future
        try:
            async with self.lock:
                self.writer.write(Frame(kind,self.boot,self.session,req,data).encode())
                await asyncio.wait_for(self.writer.drain(),timeout)
            return await asyncio.wait_for(future,timeout)
        finally:
            self.pending.pop(req,None)
    async def send_command(self,command):return (await self.request(1,command.encode('ascii'))).decode()
    async def send_text(self,text):return (await self.request(2,text.encode('utf-8'))).decode()
    async def clear_text(self):return (await self.request(3)).decode()
    async def control(self,data=b''):return json.loads(await self.request(6,data))
    async def disconnect(self):
        task,self.read_task=self.read_task,None
        if task and task is not asyncio.current_task():
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):await task
        writer,self.writer=self.writer,None
        if writer:
            writer.close()
            with contextlib.suppress(Exception):await writer.wait_closed()
        self.healthy_since=0;self.successes=0

class LinkRouter:
    """Select only at task boundaries. Failure of the spare link is harmless."""
    def __init__(self, clock=time.monotonic):
        self.clock=clock;self.policy='auto_wifi_first';self.manual=False
        self.active=None;self.last='ble';self.switched=0
    def choose(self,ble,wifi):
        if self.manual:raise ConnectionError('设备已主动断开')
        if self.active:return self.active
        ready_wifi=wifi.connected and (self.policy=='wifi_only' or (self.clock()-wifi.healthy_since>=10 and wifi.successes>=3))
        if self.policy=='ble_only':choice='ble' if ble else None
        elif self.policy=='wifi_only':choice='wifi' if ready_wifi else None
        elif ready_wifi and (self.last=='wifi' or not ble or self.clock()-self.switched>=30):choice='wifi'
        else:choice='ble' if ble else ('wifi' if ready_wifi else None)
        if not choice:raise ConnectionError('没有符合策略的已认证通道')
        if choice!=self.last:self.last=choice;self.switched=self.clock()
        return choice
    def begin(self,ble,wifi):
        self.active=self.choose(ble,wifi);return self.active
    def end(self):self.active=None

class WifiAudioBridge:
    """Transport adapter for the existing AudioClient state machine."""
    def __init__(self, wifi):self.wifi=wifi;self.services=self;self.max_write_without_response_size=MAX_PAYLOAD
    capture_window=3  # Four-slot device ingress queue; reserve one control slot.
    @property
    def is_connected(self):return self.wifi.connected
    def get_characteristic(self,_):return self
    async def start_notify(self,uuid,callback):self.wifi.listeners[uuid]=callback
    async def stop_notify(self,uuid):self.wifi.listeners.pop(uuid,None)
    async def write_gatt_char(self,uuid,data,response=True):await self.wifi.request(5,bytes(data))
