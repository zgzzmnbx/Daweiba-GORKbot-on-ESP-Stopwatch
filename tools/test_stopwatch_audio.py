"""Host protocol/bench tests, not a substitute for embedded I2S/BLE tests."""
import asyncio
import io
import struct
import sys
import unittest
import wave
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0,str(Path(__file__).parent))
from stopwatch_audio import AudioClient, Packet, Op, make_wav, read_wav, audio_connection, SERVICE_UUID, OPUS_HELLO_ID
from stopwatch_opus import encode_opus, _ogg_packets


class FakeBle:
    def __init__(self, mtu=244, opus=False):
        self.is_connected=True
        self.services=self
        self.mtu=mtu
        self.callback=None
        self.epoch=123
        self.written=[]
        self.received=bytearray()
        self.capture=b"\x01\x00"*1600
        self.drop=False
        self.bad_offset=False
        self.played=False
        self.opus=opus

    def get_characteristic(self, _):
        return SimpleNamespace(max_write_without_response_size=self.mtu)

    async def start_notify(self, _, callback):
        self.callback=callback

    async def stop_notify(self, _):
        self.callback=None

    def send(self, p):
        self.callback(None,p.encode())

    async def write_gatt_char(self, uuid, raw, response):
        p=Packet.decode(raw)
        self.written.append(p)
        assert len(raw)<=self.mtu
        if self.drop:
            return
        def event(op,value=0,data=b""):
            self.send(Packet(op,p.transfer,self.epoch,value,data))
        if p.op==Op.HELLO:
            event(Op.CAPS,480000,struct.pack("<HH",self.mtu,10)+(b"\x01" if self.opus else b""))
        elif p.op==Op.ARM:
            event(Op.ACK,0,bytes([p.op]))
            event(Op.RECORDING)
            event(Op.RECORDED,len(self.capture),b"\x00")
        elif p.op==Op.PULL:
            n=(self.mtu-12)&~1
            event(Op.AUDIO,p.value,self.capture[p.value:p.value+n])
        elif p.op in (Op.BEGIN,Op.BEGIN_OPUS):
            self.received.clear()
            event(Op.ACK,0,bytes([p.op]))
        elif p.op==Op.DATA:
            assert not response
            assert p.value==len(self.received)
            self.received.extend(p.data)
            event(Op.ACK,len(self.received)+(2 if self.bad_offset else 0),bytes([p.op]))
        elif p.op==Op.PLAY:
            event(Op.PLAYING,len(self.received))
            self.played=True
            event(Op.PLAYED)
        else:
            event(Op.ACK,p.value if p.op==Op.COMMIT else 0,bytes([p.op]))


class BatchedAckBle(FakeBle):
    def __init__(self):
        super().__init__()
        self.pending=[]
        self.max_pending=0

    async def write_gatt_char(self, uuid, raw, response):
        p=Packet.decode(raw)
        if p.op!=Op.DATA:
            return await super().write_gatt_char(uuid,raw,response)
        assert not response and p.value==len(self.received)
        self.written.append(p)
        self.received.extend(p.data)
        self.pending.append(len(self.received))
        self.max_pending=max(self.max_pending,len(self.pending))
        if len(self.pending)==3:
            for offset in self.pending:
                self.send(Packet(Op.ACK,p.transfer,self.epoch,offset,bytes([Op.DATA])))
            self.pending.clear()


class PacketTests(unittest.TestCase):
    def test_opus_packets_and_preskip(self):
        for rate in (16000, 24000):
            import numpy as np
            samples=(np.sin(np.arange(rate)*2*np.pi*440/rate)*12000).astype("<i2").tobytes()
            clip=encode_opus(samples,rate)
            self.assertEqual(clip.samples,rate)
            self.assertLess(len(clip.data),len(samples)//3)
            self.assertLessEqual(clip.skip,rate//5)
            offset=0
            while offset<len(clip.data):
                size=struct.unpack_from("<H",clip.data,offset)[0]
                self.assertGreater(size,0)
                offset+=2+size
            self.assertEqual(offset,len(clip.data))
        with self.assertRaises(ValueError):
            _ogg_packets(b"OggS")

    def test_connection_uses_uncached_targeted_discovery(self):
        calls=[]
        device=object()
        def factory(target,**kwargs):
            calls.append((target,kwargs)); return "connection"
        self.assertEqual(audio_connection(device,factory),"connection")
        target,options=calls[0]
        self.assertIs(target,device)
        self.assertEqual(options["services"],[SERVICE_UUID])
        self.assertEqual(options["winrt"],{"use_cached_services":False})
        self.assertTrue(options["pair"])

    def test_roundtrip_and_wire_layout(self):
        p=Packet(Op.DATA,0x1234,0xabcdef01,0x4321,b"\x00\xff")
        self.assertEqual(p.encode().hex(),"0105341201efcdab2143000000ff")
        self.assertEqual(Packet.decode(p.encode()),p)

    def test_invalid_packet(self):
        for raw in (b"",b"\x00"*12,b"\x01"*245,b"\x02"+b"\x01"*11,
                    b"\x01\x55\x01\x00"+b"\x00"*8):
            with self.assertRaises(ValueError):
                Packet.decode(raw)
        with self.assertRaises(ValueError):
            Packet(Op.DATA,1,1,data=b"x"*233).encode()

    def test_wav_roundtrip_rates(self):
        for rate in (16000,24000):
            pcm=b"\x12\x34"*rate
            self.assertEqual(read_wav(make_wav(pcm,rate)),(pcm,rate))

    def test_invalid_pcm(self):
        for pcm,rate in ((b"x",16000),(b"x"*320,16000),(b"x"*320002,16000),
                         (b"x"*480002,24000),(b"x"*32000,44100)):
            with self.assertRaises(ValueError):
                make_wav(pcm,rate)

    def test_reject_stereo_and_truncated_wav(self):
        buf=io.BytesIO()
        with wave.open(buf,"wb") as w:
            w.setnchannels(2); w.setsampwidth(2); w.setframerate(16000); w.writeframes(b"\0"*6400)
        for data in (buf.getvalue(),make_wav(b"\0"*3200,16000)[:-2]):
            with self.assertRaises(ValueError):
                read_wav(data)


class ClientTests(unittest.IsolatedAsyncioTestCase):
    async def test_opus_negotiation_and_compressed_transfer(self):
        ble=FakeBle(opus=True)
        client=AudioClient(ble)
        await client.open()
        try:
            self.assertEqual(ble.written[0].transfer,OPUS_HELLO_ID)
            self.assertTrue(client.opus_supported)
            import numpy as np
            rate=24000
            pcm=(np.sin(np.arange(rate)*2*np.pi*440/rate)*12000).astype("<i2").tobytes()
            progress=[]
            await client.play(pcm,rate,progress.append)
            begin=next(p for p in ble.written if p.op==Op.BEGIN_OPUS)
            encoded,samples,skip=struct.unpack("<III",begin.data)
            self.assertEqual(samples,rate)
            self.assertGreater(skip,0)
            self.assertEqual(encoded,len(ble.received))
            self.assertLess(encoded,len(pcm)//3)
            self.assertEqual(progress[-1]["codec"],"opus")
            self.assertEqual(progress[-1]["source_bytes"],len(pcm))
            await client.play(pcm,rate,codec="pcm16")
            self.assertEqual(bytes(ble.received),pcm)
            self.assertEqual([p.op for p in ble.written if p.op in (Op.BEGIN,Op.BEGIN_OPUS)][-1],Op.BEGIN)
        finally:
            await client.close()

    async def test_detailed_device_errors(self):
        for code, text in ((5,"legacy firmware"),(9,"microphone initialization"),
                           (10,"record queue"),(11,"capture timed out"),
                           (12,"speaker initialization"),(13,"playback queue")):
            client=AudioClient(FakeBle())
            client.transfer=1; client.epoch=123
            client.notify(None,Packet(Op.ERROR,1,123,code).encode())
            self.assertIn(text,str(client.failure))
            self.assertIn(f"code {code}",str(client.failure))

    async def test_cancel_is_not_driver_error(self):
        client=AudioClient(FakeBle())
        client.transfer=1; client.epoch=123
        client.notify(None,Packet(Op.ACK,1,123,0,bytes([Op.CANCEL])).encode())
        self.assertIn("cancelled",str(client.failure))

    async def asyncSetUp(self):
        self.ble=FakeBle()
        self.client=AudioClient(self.ble,timeout=.04)
        await self.client.open()

    async def asyncTearDown(self):
        await self.client.close()

    async def test_echo_full_transfer(self):
        progress=[]
        pcm,rate=await self.client.record(progress.append)
        await self.client.play(pcm,rate,progress.append)
        self.assertEqual(bytes(self.ble.received),pcm)
        self.assertTrue(self.ble.played)
        self.assertIn("recording",[x["stage"] for x in progress])
        self.assertIn("receiving",[x["stage"] for x in progress])
        self.assertIn("sending",[x["stage"] for x in progress])
        self.assertEqual(progress[-1]["stage"],"played")
        self.assertEqual(progress[-1]["bytes"],len(pcm))

    async def test_three_packet_window_with_delayed_ack(self):
        ble=BatchedAckBle(); client=AudioClient(ble,timeout=.1)
        await client.open()
        try:
            pcm=b"\0"*(232*15)  # five full windows at 244-byte packet size
            await client.play(pcm,16000)
            self.assertEqual(ble.received,pcm)
            self.assertEqual(ble.max_pending,3)
            self.assertFalse(ble.pending)
        finally:
            await client.close()

    async def test_minimum_mtu_20(self):
        ble=FakeBle(20); c=AudioClient(ble)
        try:
            await c.open()
            pcm,rate=await c.record()
            await c.play(pcm,rate)
            self.assertEqual(ble.received,pcm)
        finally:
            await c.close()

    async def test_wrong_offset_ack_does_not_advance(self):
        self.ble.bad_offset=True
        with self.assertRaisesRegex(TimeoutError, "DATA 回执超时"):
            await self.client.play(b"\0"*3200,16000)
        self.assertFalse(self.ble.played)
        self.assertEqual(sum(p.op==Op.DATA for p in self.ble.written),3)

    async def test_stale_epoch_and_transfer_ignored(self):
        for epoch,transfer in ((999,self.client.transfer),(self.client.epoch,999)):
            self.ble.send(Packet(Op.RECORDED,transfer,epoch,3200,b"\0"))
        self.assertTrue(self.client.events.empty())

    async def test_missing_response_fails_closed(self):
        self.ble.drop=True
        with self.assertRaisesRegex(TimeoutError, "PING 回执超时"):
            await self.client.request(Op.PING)
        count=len(self.ble.written)
        with self.assertRaises(TimeoutError):
            await self.client.record()
        self.assertEqual(count,len(self.ble.written))

    async def test_twenty_cancels_and_late_data(self):
        for _ in range(20):
            ble=FakeBle(); c=AudioClient(ble,timeout=.1)
            await c.open(); ble.drop=True
            operation=asyncio.create_task(c.play(b"\0"*3200,16000))
            await asyncio.sleep(0)
            await c.close()
            with self.assertRaises(RuntimeError):
                await operation
            c.notify(None,Packet(Op.PLAYED,c.transfer,c.epoch).encode())
            self.assertTrue(c.events.empty())
            self.assertEqual(ble.written[-1].op,Op.CANCEL)
            self.assertFalse(ble.played)

    async def test_physical_stop_is_not_success(self):
        self.ble.send(Packet(Op.ACK,self.client.transfer,self.client.epoch,0,bytes([Op.CANCEL])))
        with self.assertRaisesRegex(RuntimeError,"device stopped"):
            await self.client.event(Op.PLAYED)

    async def test_disconnect_no_replay(self):
        self.ble.is_connected=False
        with self.assertRaisesRegex(RuntimeError,"disconnected"):
            await self.client.record()
        self.assertFalse(any(p.op==Op.ARM for p in self.ble.written))

    async def test_oversized_audio_rejected_before_write(self):
        before=len(self.ble.written)
        with self.assertRaises(ValueError):
            await self.client.play(b"x"*480002,24000)
        self.assertEqual(before,len(self.ble.written))

    async def test_heartbeat_serialized_before_new_transfer(self):
        await asyncio.gather(self.client.request(Op.PING), self.client.record())
        self.assertIsNone(self.client.failure)

    async def test_event_overflow_fails_closed(self):
        for _ in range(9):
            self.ble.send(Packet(Op.RECORDING,self.client.transfer,self.client.epoch))
        with self.assertRaisesRegex(RuntimeError,"overflow"):
            self.client.check()

    async def test_missing_service_does_not_claim_wrong_firmware(self):
        ble=FakeBle()
        ble.get_characteristic=lambda _: None
        c=AudioClient(ble)
        with self.assertRaisesRegex(RuntimeError,"不能据此判定固件版本"):
            await c.open()
        await c.close()
        self.assertEqual(ble.written,[])


if __name__=="__main__":
    unittest.main()
