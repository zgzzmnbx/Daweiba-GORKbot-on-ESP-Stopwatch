import asyncio
import json
import ssl
import struct
from types import SimpleNamespace
import pytest
from companion.network import Frame,HEADER,LinkRouter,WifiClient,psk_context,local_address
from companion.network_store import NetworkStore,protect

def test_golden_frame():
    frame=Frame(5,0x12345678,0x10203040,1,b'abc')
    assert frame.encode().hex()=='4757010503000000785634124030201001000000c2412435616263'
    async def run():
        reader=asyncio.StreamReader()
        for b in frame.encode():reader.feed_data(bytes([b]))
        assert await Frame.read(reader)==frame
    asyncio.run(run())

@pytest.mark.parametrize('fault',['length','crc','magic','version','flags','truncated'])
def test_bad_frames(fault):
    data=bytearray(Frame(5,1,2,3,b'abc').encode())
    if fault=='length':data[4:6]=struct.pack('<H',4097)
    if fault=='crc':data[-1]^=1
    if fault=='magic':data[0]=0
    if fault=='version':data[2]=2
    if fault=='flags':data[6]=1
    if fault=='truncated':del data[-1]
    async def run():
        reader=asyncio.StreamReader();reader.feed_data(data);reader.feed_eof()
        with pytest.raises((ValueError,asyncio.IncompleteReadError)):await Frame.read(reader)
    asyncio.run(run())

@pytest.mark.parametrize('address',['127.0.0.1','0.0.0.0','224.0.0.1','8.8.8.8','169.254.2.1','::1','100.64.1.2'])
def test_forbidden_addresses(address):
    with pytest.raises(ValueError):local_address(address)

def test_router_pin_spare_failure_upgrade_and_manual():
    now=[100.];r=LinkRouter(lambda:now[0]);wifi=SimpleNamespace(connected=True,healthy_since=100.,successes=1)
    assert r.begin(True,wifi)=='ble'
    now[0]=111;wifi.successes=3
    assert r.choose(True,wifi)=='ble' # stays pinned while Wi-Fi improves.
    r.end();assert r.begin(True,wifi)=='wifi'
    assert r.choose(False,wifi)=='wifi' # BLE spare disconnect cannot stop Wi-Fi.
    wifi.connected=False
    assert r.choose(True,wifi)=='wifi' # failing task is not rerouted/replayed.
    r.end();assert r.choose(True,wifi)=='ble'
    r.manual=True
    with pytest.raises(ConnectionError):r.choose(True,wifi)
    r.manual=False;r.policy='wifi_only'
    with pytest.raises(ConnectionError):r.choose(True,wifi)
    r.policy='ble_only';wifi.connected=True
    assert r.choose(True,wifi)=='ble'

def test_production_robot_does_not_fallback_inside_pinned_wifi_task():
    from companion.robot import Robot
    r=Robot(client=SimpleNamespace(connected=True))
    r.network.router.active='wifi'
    assert not r.network.wifi.connected
    assert r.device_client() is r.network.wifi
    assert not r.device_connected
    r.network.router.end()
    assert r.device_client() is r.client

def test_dpapi_cas_and_corruption_preserve(tmp_path):
    secret={'key':'ab'*32,'identity':'123456789abcdef0','ssid':'test-hotspot'}
    path=tmp_path/'network.local.json';store=NetworkStore(path)
    store.write(secret,'auto_wifi_first','auto',expected=0)
    assert secret['key'] not in path.read_text()
    restored=NetworkStore(path);restored.load();assert restored.secret==secret
    with pytest.raises(ValueError):restored.write(secret,'ble_only','eco',expected=0)
    restored.write(secret,'ble_only','eco',expected=1)
    assert path.with_name(path.name+'.bak').exists()
    path.write_text('broken');bad=NetworkStore(path);bad.load()
    assert bad.secret is None and bad.error and path.read_text()=='broken'

def test_tls_psk_context_has_no_unauthenticated_cipher():
    ctx=psk_context('123456789abcdef0',b'k'*32)
    assert ctx.minimum_version==ctx.maximum_version==ssl.TLSVersion.TLSv1_2
    assert [c['name'] for c in ctx.get_ciphers() if c['protocol']=='TLSv1.2']==['PSK-AES128-GCM-SHA256']

@pytest.mark.parametrize('wrong',[False,True])
def test_production_tls_client_real_handshake(monkeypatch,wrong):
    import companion.network as network
    monkeypatch.setattr(network,'local_address',lambda a:a)
    monkeypatch.setattr(network,'verify_wifi_subnet',lambda a:None)
    async def run():
        identity='123456789abcdef0';key=b'\x1f'*32
        ctx=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.minimum_version=ctx.maximum_version=ssl.TLSVersion.TLSv1_2
        ctx.set_ciphers('PSK-AES128-GCM-SHA256')
        ctx.set_psk_server_callback(lambda received:key if received==identity else b'')
        async def handle(reader,writer):
            try:
                while True:
                    frame=await Frame.read(reader)
                    payload=json.dumps(dict(protocol=1,boot=10,session=20)).encode() if frame.kind==0 else b'OK:APPLIED'
                    writer.write(Frame(128,10,20,frame.request,payload).encode());await writer.drain()
            except (asyncio.IncompleteReadError,ConnectionError):pass
            finally:
                writer.close()
                try:await writer.wait_closed()
                except ConnectionError:pass
        server=await asyncio.start_server(handle,'127.0.0.1',0,ssl=ctx)
        port=server.sockets[0].getsockname()[1];monkeypatch.setattr(network,'PORT',port)
        client=WifiClient()
        try:
            if wrong:
                with pytest.raises((ssl.SSLError,ConnectionError)):await client.connect('127.0.0.1',identity,b'\x2f'*32)
                assert not client.connected
            else:
                await client.connect('127.0.0.1',identity,key)
                assert client.boot==10 and client.session==20
                for _ in range(20):assert await client.send_command('idle')=='OK:APPLIED'
        finally:
            await client.disconnect();server.close();await server.wait_closed()
    asyncio.run(run())
