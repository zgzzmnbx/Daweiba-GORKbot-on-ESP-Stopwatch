"""Explicit, local USB first provisioning; never logs credentials or raw replies."""
import json
import secrets
import time
import zlib


def payload(ssid, password, key, identity):
    a,b=ssid.encode('utf-8'),password.encode('utf-8')
    if not 1<=len(a)<=32 or not 8<=len(b)<=63 or b'\0' in a+b:
        raise ValueError('热点名称需1–32字节，密码需8–63字节')
    if len(key)!=32 or not any(key) or len(identity)!=16 or any(c not in '0123456789abcdefABCDEF' for c in identity):
        raise ValueError('本机设备身份格式不正确')
    return bytes([len(a)])+a+bytes([len(b)])+b+key+identity.encode('ascii')


class UsbNetwork:
    def __init__(self, port_source=None, serial_factory=None, clock=time.monotonic):
        if port_source is None:
            from serial.tools.list_ports import comports
            port_source=comports
        if serial_factory is None:
            from serial import Serial
            serial_factory=Serial
        self.port_source=port_source;self.serial_factory=serial_factory;self.clock=clock
        self.serial=None

    def __enter__(self):
        ports=[p.device for p in self.port_source() if p.vid==0x303a and p.pid==0x1001]
        if len(ports)!=1:
            raise ConnectionError('请用USB连接唯一一台Watch；端口未改动')
        try:
            self.serial=self.serial_factory(port=None,baudrate=115200,timeout=.15,write_timeout=3)
            # Set before opening. Never deliberately request ROM/download mode.
            self.serial.dtr=False;self.serial.rts=False;self.serial.port=ports[0]
            self.serial.open()
            self.serial.reset_input_buffer()
            result=self.request('HELLO')
            if result.get('device')!='StopWatch-Gork' or result.get('protocol')!=1:
                raise ConnectionError('USB设备未确认兼容配网协议，请检查实屏版本')
            return self
        except Exception:
            self.close()
            raise ConnectionError('Watch USB配网握手未完成；请确认新固件正常启动且串口未被占用') from None

    def close(self):
        if self.serial:
            self.serial.close();self.serial=None

    def __exit__(self,*_):self.close()

    def request(self, command):
        token=f'{secrets.randbelow(0xffffffff)+1:08x}'
        prefix=f'GWUSB1 {token} '.encode('ascii')
        try:
            self.serial.write(prefix+command.encode('ascii')+b'\n')
            deadline=self.clock()+3
            while self.clock()<deadline:
                line=self.serial.read_until(b'\n',2048)
                if not line.startswith(prefix) or not line.endswith(b'\n'):
                    continue
                value=json.loads(line[len(prefix):])
                if not isinstance(value,dict) or value.get('error'):
                    break
                return value
        except Exception:
            pass
        raise ConnectionError('USB请求未获确认；秘密输入不会出现在错误中') from None

    def configure(self, data, identity):
        checksum=zlib.crc32(data)&0xffffffff
        reply=self.request(f'SET {checksum:08x} {data.hex()}')
        if reply.get('accepted') is not True:
            raise ConnectionError('Watch未接受配网；请先停止设备音频后再操作')
        deadline=self.clock()+35
        confirmed=None
        while self.clock()<deadline:
            status=self.request('STATUS').get('network',{})
            if isinstance(status,dict) and status.get('configured') is True and status.get('identity')==identity:
                # Copy public fields only, even if another USB device misbehaves.
                confirmed={k:status[k] for k in ('protocol','boot','session','configured','identity','address','port','policy','power','effective_power','source','state','authenticated') if k in status}
                if confirmed.get('address'):
                    return confirmed
            time.sleep(.3)
        if confirmed:return confirmed
        raise ConnectionError('设备保存确认未到达；本机保护身份已保留，请读取状态后再操作')
