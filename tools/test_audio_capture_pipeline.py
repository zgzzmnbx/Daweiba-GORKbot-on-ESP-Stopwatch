"""Production capture pulls over a delayed local peer; no physical speed claims."""
import asyncio
import time
import unittest
from stopwatch_audio import AudioClient,Packet,Op
from test_stopwatch_audio import FakeBle

class WifiPeer(FakeBle):
    capture_window=3
    def __init__(self,mode='normal'):
        super().__init__(4096)
        self.capture=bytes(range(256))*375
        self.mode=mode;self.inflight=0;self.maximum=0;self.offsets=[]
    def send(self,p):self.callback(None,p.encode(self.mtu))
    async def write_gatt_char(self,uuid,raw,response):
        p=Packet.decode(raw,self.mtu)
        if p.op!=Op.PULL:return await super().write_gatt_char(uuid,raw,response)
        self.offsets.append(p.value);self.inflight+=1;self.maximum=max(self.maximum,self.inflight)
        try:
            await asyncio.sleep(.012 if p.value==0 else .008)
            if self.mode=='disconnect':self.is_connected=False;raise ConnectionError('peer disconnected')
            if self.mode=='missing' and p.value==0:return
            chunk=(self.mtu-12)&~1;data=self.capture[p.value:p.value+chunk]
            if self.mode=='short' and p.value==0:data=data[:-2]
            epoch=self.epoch-1 if self.mode=='stale' else self.epoch
            self.send(Packet(Op.AUDIO,p.transfer,epoch,p.value,data))
            if self.mode=='duplicate':self.send(Packet(Op.AUDIO,p.transfer,epoch,p.value,data))
        finally:self.inflight-=1

class CapturePipeline(unittest.IsolatedAsyncioTestCase):
    async def capture(self,peer):
        client=AudioClient(peer,packet_bytes=4096,timeout=.1)
        await client.open()
        try:
            progress=[];start=time.monotonic()
            pcm,rate=await client.record(progress.append)
            return time.monotonic()-start,pcm,rate,progress
        finally:
            await client.close()
            self.assertFalse(client.pull_waiters)
            self.assertEqual(peer.inflight,0)

    async def test_three_pulls_reassemble_out_of_order_and_reduce_simulated_rtt_wait(self):
        serial=WifiPeer();serial.capture_window=1
        piped=WifiPeer()
        slow=await self.capture(serial);fast=await self.capture(piped)
        self.assertEqual(fast[1],piped.capture);self.assertEqual(fast[2],16000)
        self.assertEqual(piped.maximum,3);self.assertEqual(serial.maximum,1)
        self.assertEqual(len(piped.offsets),len(set(piped.offsets)))
        self.assertEqual(fast[3][-1]['stage'],'received')
        self.assertLess(fast[0],slow[0]*.7)
        print(f'Isolated 96KB capture: serial={slow[0]:.3f}s, window3={fast[0]:.3f}s; simulated peer delay, not hardware.')

    async def test_duplicate_responses_never_duplicate_samples(self):
        peer=WifiPeer('duplicate');result=await self.capture(peer)
        self.assertEqual(result[1],peer.capture)

    async def test_partial_missing_stale_and_disconnect_fail_without_replay(self):
        for mode in ('short','missing','stale','disconnect'):
            with self.subTest(mode=mode):
                peer=WifiPeer(mode)
                with self.assertRaises((RuntimeError,TimeoutError,ConnectionError)):await self.capture(peer)
                self.assertEqual(len(peer.offsets),len(set(peer.offsets)))

    async def test_cancel_releases_all_inflight_pulls(self):
        peer=WifiPeer('missing');client=AudioClient(peer,packet_bytes=4096,timeout=1)
        await client.open();task=asyncio.create_task(client.record())
        while len(peer.offsets)<3:await asyncio.sleep(0)
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):await task
        self.assertFalse(client.pull_waiters);self.assertEqual(peer.inflight,0)
        await client.close()

    async def test_ble_keeps_serial_capture(self):
        peer=FakeBle();client=AudioClient(peer)
        await client.open()
        try:
            self.assertEqual(client.capture_window,1)
            pcm,rate=await client.record();self.assertEqual(pcm,peer.capture)
        finally:await client.close()

if __name__=='__main__':unittest.main()
