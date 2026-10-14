import asyncio
import json
from types import SimpleNamespace
import pytest
from companion.usb_network import UsbNetwork,payload

IDENTITY='123456789abcdef0'
DATA=payload('test-hotspot','test-password',b'k'*32,IDENTITY)

class Port:
    device='COM-test';vid=0x303a;pid=0x1001

class Serial:
    def __init__(self,**kwargs):
        self.lines=[];self.commands=[];self.closed=False;self.device='StopWatch-Gork';self.error=False
    def open(self):assert self.dtr is False and self.rts is False and self.port=='COM-test'
    def reset_input_buffer(self):pass
    def close(self):self.closed=True
    def write(self,value):
        prefix,command=value[:16],value[16:].decode().strip()
        self.commands.append(command)
        result={'device':self.device,'protocol':1} if command=='HELLO' else {'accepted':True} if command.startswith('SET ') else {'network':{'configured':True,'identity':IDENTITY,'address':'192.168.42.2','password':'must-not-return'}}
        self.lines=[b'GWUSB1 ffffffff {"error":"old reply"}\n',prefix+json.dumps(result).encode()+b'\n']
        if self.error:self.lines=[prefix+b'{"error":"test-password"}\n']
    def read_until(self,*args):return self.lines.pop(0) if self.lines else b''

def test_handshake_matching_reply_crc_public_status():
    serial=Serial()
    with UsbNetwork(lambda:[Port()],lambda **kwargs:serial) as usb:
        result=usb.configure(DATA,IDENTITY)
    assert result=={'configured':True,'identity':IDENTITY,'address':'192.168.42.2'}
    assert serial.commands[0]=='HELLO' and serial.commands[1].startswith('SET ')
    assert serial.closed

@pytest.mark.parametrize('ports',[[],[Port(),Port()]])
def test_ambiguous_ports_do_not_open(ports):
    with pytest.raises(ConnectionError):
        with UsbNetwork(lambda:ports,lambda **kwargs:pytest.fail('opened unexpected port')):pass

def test_wrong_device_never_receives_setup():
    serial=Serial();serial.device='other'
    with pytest.raises(ConnectionError):
        with UsbNetwork(lambda:[Port()],lambda **kwargs:serial):pass
    assert serial.commands==['HELLO'] and serial.closed

def test_error_does_not_echo_secret():
    serial=Serial();serial.error=True
    with pytest.raises(ConnectionError) as exc:
        with UsbNetwork(lambda:[Port()],lambda **kwargs:serial):pass
    assert 'test-password' not in str(exc.value)

@pytest.mark.parametrize('ssid,password,key,identity',[('', 'password',b'k'*32,IDENTITY),('x','short',b'k'*32,IDENTITY),('x'*33,'password',b'k'*32,IDENTITY),('x','p'*64,b'k'*32,IDENTITY),('x','password',bytes(32),IDENTITY),('x','password',b'k'*32,'z'*16),('x\0','password',b'k'*32,IDENTITY)])
def test_invalid_payload(ssid,password,key,identity):
    with pytest.raises(ValueError):payload(ssid,password,key,identity)

def test_usb_failed_device_ack_retains_dpapi_identity(tmp_path,monkeypatch):
    from companion.network_manager import NetworkManager
    import companion.usb_network as module
    class Lost:
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def configure(self,*args):raise ConnectionError('reply lost')
    monkeypatch.setattr(module,'UsbNetwork',Lost)
    robot=SimpleNamespace(client=SimpleNamespace(connected=False),audio_snapshot=lambda:{'running':False})
    manager=NetworkManager(robot,tmp_path/'network.local.json')
    with pytest.raises(ConnectionError):asyncio.run(manager.provision_usb('test-hotspot','test-password',0))
    assert manager.store.secret and manager.store.revision==1
    assert 'test-password' not in manager.store.path.read_text()

def test_stale_revision_does_not_open_usb(tmp_path,monkeypatch):
    from companion.network_manager import NetworkManager
    import companion.usb_network as module
    monkeypatch.setattr(module,'UsbNetwork',lambda:pytest.fail('unexpected setup'))
    robot=SimpleNamespace(client=SimpleNamespace(connected=False),audio_snapshot=lambda:{'running':False})
    manager=NetworkManager(robot,tmp_path/'network.local.json')
    with pytest.raises(ValueError):asyncio.run(manager.provision_usb('test-hotspot','test-password',2))

def test_http_usb_requires_owner_and_preserves_legacy_default():
    from fastapi.testclient import TestClient
    from companion.app import create_app
    from companion.control import Controller
    from test_companion import FakeRobot,FakeVoice
    import uuid
    seen=[]
    async def usb(*args):seen.append(('usb',args));return {'configured':True}
    async def ble(*args):seen.append(('ble',args));return {'configured':True}
    robot=FakeRobot();robot.network=SimpleNamespace(provision_usb=usb,provision=ble,router=SimpleNamespace(end=lambda:None))
    control=Controller(FakeVoice(),robot)
    headers={'X-Companion-Client':str(uuid.uuid4())}
    with TestClient(create_app(controller=control),base_url='http://127.0.0.1:8766') as client:
        body={'ssid':'test-hotspot','password':'test-password','revision':0,'via':'usb'}
        assert client.post('/api/device/network/provision',json=body,headers=headers).status_code==401
        assert not seen
        assert client.post('/api/workspace',json={},headers=headers).status_code==200
        assert client.post('/api/device/network/provision',json=body,headers=headers).status_code==200
        body.pop('via')
        assert client.post('/api/device/network/provision',json=body,headers=headers).status_code==200
        assert [item[0] for item in seen]==['usb','ble']
        body['via']='other'
        result=client.post('/api/device/network/provision',json=body,headers=headers)
        assert result.status_code==422 and 'test-password' not in result.text
