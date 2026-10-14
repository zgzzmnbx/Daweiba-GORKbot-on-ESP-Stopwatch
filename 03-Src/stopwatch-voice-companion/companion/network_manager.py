"""Own network discovery and health independently of BLE task generations."""
import asyncio
import contextlib
import json
from pathlib import Path
import secrets
import socket
from .network import WifiClient, LinkRouter, WifiAudioBridge, NET_INPUT,NET_STATUS,local_address
from .network_store import NetworkStore

POLICIES=('auto_wifi_first','ble_only','wifi_only')
POWERS=('auto','performance','eco')

class NetworkManager:
    def __init__(self,robot,path=None):
        self.robot=robot;self.wifi=WifiClient();self.router=LinkRouter();self.task=None
        self.store=NetworkStore(path or Path(__file__).resolve().parents[1]/'network.local.json');self.store.load()
        self.router.policy=self.store.policy;self.status={};self.error=self.store.error;self.wake=asyncio.Event()
        self.voice_event=None;self.voice_raw=None
        self.provision_lock=asyncio.Lock()
    def start(self):
        if not self.task:self.task=asyncio.create_task(self.run())
    async def close(self):
        if self.task:
            self.task.cancel()
            with contextlib.suppress(asyncio.CancelledError):await self.task
            self.task=None
        await self.wifi.disconnect()
    def snapshot(self):
        try:route=self.router.choose(self.robot.client.connected,self.wifi)
        except ConnectionError:route='offline'
        return dict(configured=bool(self.store.secret),revision=self.store.revision,policy=self.router.policy,power=self.store.power,route=route,active=self.router.active,
                    wifi_connected=self.wifi.connected,ble_connected=self.robot.client.connected,address=self.wifi.address or self.store.address,
                    error=self.error,device=self.status,manual_disconnected=self.router.manual)
    def selected(self):
        route=self.router.choose(self.robot.client.connected,self.wifi)
        return self.wifi if route=='wifi' else self.robot.client
    def audio(self):
        raw=getattr(self.robot.client,'client',None)
        connected=getattr(self.robot.client,'connected',getattr(raw,'is_connected',False))
        route=self.router.begin(connected,self.wifi)
        return WifiAudioBridge(self.wifi) if route=='wifi' else getattr(self.robot.client,'client',None)
    async def ble_status(self):
        raw=getattr(self.robot.client,'client',None)
        if not raw or not raw.is_connected:raise ConnectionError('首次配网需要已绑定的 BLE 连接')
        data=await raw.read_gatt_char(NET_STATUS)
        result=json.loads(bytes(data))
        if result.get('protocol')!=1:raise ValueError('Watch 尚不支持配网')
        return result
    async def provision(self,ssid,password,revision):
        if self.router.active or self.robot.audio_snapshot().get('running'):raise ValueError('请先停止设备音频/按键对话再配网')
        if revision!=self.store.revision:raise ValueError('配置已变化，请刷新')
        raw=getattr(self.robot.client,'client',None)
        if not raw or not raw.is_connected:raise ConnectionError('需要当前可信 BLE 连接')
        a,b=ssid.encode(),password.encode()
        if not 1<=len(a)<=32 or not 8<=len(b)<=63 or b'\0' in a+b:raise ValueError('SSID 1–32 字节，密码 8–63 字节')
        await self.ble_status()
        key=secrets.token_bytes(32);identity=secrets.token_hex(8)
        payload=bytes([len(a)])+a+bytes([len(b)])+b+key+identity.encode()
        # Save protected pending identity first so an interrupted acknowledgement
        # cannot strand a configured device without its matching PC identity.
        secret=dict(key=key.hex(),identity=identity,ssid=ssid)
        self.store.write(secret,self.router.policy,self.store.power,expected=revision)
        await raw.write_gatt_char(NET_INPUT,bytes([1,0,1,len(payload)]),response=True)
        for offset in range(0,len(payload),16):
            await raw.write_gatt_char(NET_INPUT,bytes([1,1,1,offset])+payload[offset:offset+16],response=True)
            await asyncio.sleep(.02)
        await raw.write_gatt_char(NET_INPUT,b'\x01\x02\x01',response=True)
        for _ in range(20):
            await asyncio.sleep(.2);status=await self.ble_status()
            if status.get('configured') and status.get('identity')==identity:
                self.status=status;self.router.manual=False;self.wake.set();return self.snapshot()
        raise ConnectionError('设备保存确认未到达；请读取设备状态，不能重复盲目配置')
    async def provision_usb(self,ssid,password,revision):
        from .usb_network import UsbNetwork,payload
        async with self.provision_lock:
            if self.router.active or self.robot.audio_snapshot().get('running'):
                raise ValueError('请先停止设备音频/按键对话再配网')
            if revision!=self.store.revision:raise ValueError('配置已变化，请刷新')
            key=secrets.token_bytes(32);identity=secrets.token_hex(8)
            data=payload(ssid,password,key,identity)
            def configure():
                with UsbNetwork() as usb:
                    # Verify the running USB protocol before replacing the local
                    # protected identity. Preserve it if the device reply is lost.
                    self.store.write(dict(key=key.hex(),identity=identity,ssid=ssid),
                                     'auto_wifi_first',self.store.power,expected=revision)
                    return usb.configure(data,identity)
            self.status=await asyncio.to_thread(configure)
            self.router.policy='auto_wifi_first';self.router.manual=False
            address=self.status.get('address','')
            if address:
                self.store.write(self.store.secret,self.store.policy,self.store.power,local_address(address))
            self.error='' if address else '设备已保存热点，等待热点连接；可查看Watch Network页面IP'
            self.wake.set();return self.snapshot()
    async def delegate(self,enabled):
        route=self.router.active or self.router.choose(self.robot.client.connected,self.wifi)
        if route=='wifi':
            self.wifi.voice_event=self.voice_event
            await self.wifi.control(bytes([3,bool(enabled)]))
        else:
            raw=getattr(self.robot.client,'client',None)
            if not raw or not raw.is_connected:raise ConnectionError('BLE 委托连接不可用')
            if raw is not self.voice_raw:
                await raw.start_notify('48f1d004-8a75-4db6-9c18-590f7e9b0a01',lambda _,data:self.voice_event(data[0]) if self.voice_event and data else None)
                self.voice_raw=raw
            await raw.write_gatt_char(NET_INPUT,bytes([1,6,1,bool(enabled)]),response=True)
    async def settings(self,policy,power,revision):
        if self.router.active or self.robot.audio_snapshot().get('running'):raise ValueError('请先停止当前设备任务')
        if policy not in POLICIES or power not in POWERS:raise ValueError('invalid mode')
        if revision!=self.store.revision:raise ValueError('配置已变化，请刷新')
        raw=getattr(self.robot.client,'client',None)
        # BLE maintenance is permitted for settings even when Wi-Fi-only is
        # selected, never for hidden business fallback.
        if raw and raw.is_connected:
            await raw.write_gatt_char(NET_INPUT,bytes([1,3,1,POLICIES.index(policy),POWERS.index(power)]),response=True)
            await asyncio.sleep(.6);status=await self.ble_status()
            if status.get('policy')!=POLICIES.index(policy) or status.get('power')!=POWERS.index(power):raise ConnectionError('设备未确认保存')
            self.status=status
        elif self.wifi.connected:
            await self.wifi.control(bytes([1,POLICIES.index(policy),POWERS.index(power)]))
        else:raise ConnectionError('设备未连接，未保存')
        if self.store.secret:self.store.write(self.store.secret,policy,power,self.store.address,revision)
        self.router.policy=policy;self.wake.set();return self.snapshot()
    async def manual_connect(self,address=''):
        if address:
            address=local_address(address)
            if not self.store.secret:raise ValueError('请先经可信 BLE 配网')
            self.store.write(self.store.secret,self.store.policy,self.store.power,address)
        self.router.manual=False;self.wake.set();return self.snapshot()
    async def forget(self):
        raw=getattr(self.robot.client,'client',None)
        if not raw or not raw.is_connected:raise ConnectionError('忘记热点需要可信 BLE')
        await raw.write_gatt_char(NET_INPUT,b'\x01\x04\x01',response=True)
        await asyncio.sleep(.6);status=await self.ble_status()
        if status.get('configured'):raise ConnectionError('设备未确认清除')
        await self.wifi.disconnect();self.store.secret=None;self.router.policy='ble_only'
        if self.store.path.exists():self.store.path.unlink()
        backup=self.store.path.with_name(self.store.path.name+'.bak')
        if backup.exists():backup.unlink()
        self.status=status;return self.snapshot()
    async def candidates(self):
        values=[]
        if self.robot.client.connected:
            with contextlib.suppress(Exception):
                self.status=await self.ble_status()
                if self.status.get('address'):values.append(self.status['address'])
        if self.store.address:values.append(self.store.address)
        if self.store.secret:
            with contextlib.suppress(Exception):
                found=await asyncio.wait_for(asyncio.get_running_loop().getaddrinfo('gork-'+self.store.secret['identity']+'.local',7443,family=socket.AF_INET,type=socket.SOCK_STREAM),3)
                values.extend(entry[4][0] for entry in found)
        return list(dict.fromkeys(values))[:4]
    async def run(self):
        delay=5
        try:
            while True:
                try:
                    if self.router.manual or self.router.policy=='ble_only' or not self.store.secret:
                        await self.wifi.disconnect()
                    elif self.wifi.connected:
                        self.status=await self.wifi.control();delay=2;self.error=''
                    else:
                        secret=self.store.secret
                        for address in await self.candidates():
                            try:
                                await self.wifi.connect(address,secret['identity'],bytes.fromhex(secret['key']))
                                self.store.write(secret,self.store.policy,self.store.power,address)
                                self.status=self.wifi.info;self.error='';delay=2;break
                            except Exception:self.error='热点通道不可达或身份认证失败；下一轮按策略选择通道'
                        if not self.wifi.connected:delay=min(60,delay*2)
                except Exception:
                    self.error='网络健康检查失败；当前通道不可用';await self.wifi.disconnect();delay=min(60,delay*2)
                try:await asyncio.wait_for(self.wake.wait(),delay)
                except TimeoutError:pass
                self.wake.clear()
        except asyncio.CancelledError:pass
        finally:await self.wifi.disconnect()
