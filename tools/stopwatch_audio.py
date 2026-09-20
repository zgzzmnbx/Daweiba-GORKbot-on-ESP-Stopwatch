"""P0 BLE-only audio bench. No microphone capture on PC, HTTP, ASR or cloud.

This is a bounded, credit-one transport probe, not a low-latency audio product.
Use the device's Audio test page; A physically starts capture, B always stops.
"""
from __future__ import annotations

import argparse
import asyncio
import contextlib
import io
import math
from pathlib import Path
import struct
import time
import wave
from dataclasses import dataclass
from enum import IntEnum

from stopwatch_ble import scan_targets

INPUT_UUID = "48f1b002-8a75-4db6-9c18-590f7e9b0a01"
EVENT_UUID = "48f1b003-8a75-4db6-9c18-590f7e9b0a01"
HEADER = struct.Struct("<BBHII")
MAX_BYTES = 480_000
MAX_PACKET = 244


class Op(IntEnum):
    HELLO=1; ARM=2; PING=3; BEGIN=4; DATA=5; COMMIT=6; PLAY=7; CANCEL=8; PULL=9
    CAPS=128; ACK=129; RECORDING=130; RECORDED=131; AUDIO=132
    PLAYING=133; PLAYED=134; ERROR=255


@dataclass(frozen=True)
class Packet:
    op: Op
    transfer: int
    epoch: int
    value: int = 0
    data: bytes = b""

    def encode(self) -> bytes:
        if not 0 < self.transfer <= 65535 or len(self.data) > MAX_PACKET-HEADER.size:
            raise ValueError("invalid transfer or oversized packet")
        return HEADER.pack(1, self.op, self.transfer, self.epoch, self.value) + self.data

    @classmethod
    def decode(cls, raw: bytes) -> Packet:
        if not HEADER.size <= len(raw) <= MAX_PACKET:
            raise ValueError("invalid packet size")
        version, op, transfer, epoch, value = HEADER.unpack_from(raw)
        if version != 1 or not transfer:
            raise ValueError("invalid protocol version or transfer")
        return cls(Op(op), transfer, epoch, value, bytes(raw[HEADER.size:]))


def read_wav(data: bytes) -> tuple[bytes, int]:
    if len(data) > MAX_BYTES + 4096:
        raise ValueError("WAV too large (maximum 10 seconds)")
    with wave.open(io.BytesIO(data), "rb") as wav:
        rate = wav.getframerate()
        if wav.getnchannels()!=1 or wav.getsampwidth()!=2 or rate not in (16000,24000):
            raise ValueError("expected PCM16 mono WAV at 16000 or 24000 Hz")
        frames=wav.getnframes()
        if not rate//10 <= frames <= rate*10:
            raise ValueError("WAV must contain 0.1 to 10 seconds; no silent truncation")
        pcm=wav.readframes(frames)
        if len(pcm)!=frames*2:
            raise ValueError("truncated WAV")
        return pcm,rate


def make_wav(pcm: bytes, rate: int) -> bytes:
    if rate not in (16000,24000) or len(pcm)%2 or not rate//5 <= len(pcm) <= rate*20:
        raise ValueError("invalid PCM length/rate")
    target=io.BytesIO()
    with wave.open(target,"wb") as wav:
        wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(rate); wav.writeframes(pcm)
    return target.getvalue()


class AudioClient:
    def __init__(self, client, packet_bytes=244, timeout=4.0):
        if not 20 <= packet_bytes <= MAX_PACKET:
            raise ValueError("packet bytes must be 20..244")
        self.client=client
        self.packet_bytes=packet_bytes
        self.timeout=timeout
        self.epoch=0
        self.transfer=1
        self.lock=asyncio.Lock()
        self.waiter=None
        self.events=asyncio.Queue(maxsize=8)
        self.heartbeat=None
        self.failure=None
        self.closed=False

    def notify(self, _sender, raw):
        try:
            if len(raw)>self.packet_bytes:
                raise ValueError("notification exceeds negotiated packet size")
            p=Packet.decode(bytes(raw))
        except (ValueError, struct.error):
            self.abort(RuntimeError("malformed audio notification")); return
        if self.closed or p.transfer!=self.transfer:
            return
        if p.op!=Op.CAPS and p.epoch!=self.epoch:
            return
        if p.op==Op.ERROR or (p.op==Op.ACK and p.data==bytes([Op.CANCEL])):
            self.abort(RuntimeError(f"device stopped audio (code {p.value})")); return
        if self.waiter:
            predicate, future=self.waiter
            if not future.done() and predicate(p):
                future.set_result(p); return
        if p.op in (Op.RECORDING,Op.RECORDED,Op.PLAYED):
            if self.events.full():
                self.abort(RuntimeError("audio event overflow"))
            else:
                self.events.put_nowait(p)

    def abort(self, error):
        self.failure=error
        if self.waiter and not self.waiter[1].done():
            self.waiter[1].set_exception(error)

    def check(self):
        if self.failure:
            raise self.failure
        if self.closed or not self.client.is_connected:
            raise RuntimeError("BLE disconnected; reconnect manually (no replay)")

    async def request(self, op, value=0, data=b"", expected=Op.ACK, *, new_transfer=False):
        async with self.lock:
            self.check()
            if new_transfer:
                self.next_transfer()
            future=asyncio.get_running_loop().create_future()
            def matches(p):
                if p.op!=expected:
                    return False
                if expected==Op.ACK:
                    return p.data==bytes([op]) and (op!=Op.DATA or p.value==value+len(data))
                return expected!=Op.AUDIO or p.value==value
            self.waiter=(matches,future)
            try:
                raw=Packet(op,self.transfer,self.epoch,value,data).encode()
                if len(raw)>self.packet_bytes:
                    raise ValueError("packet exceeds negotiated limit")
                async with asyncio.timeout(self.timeout):
                    await self.client.write_gatt_char(INPUT_UUID,raw,response=op!=Op.DATA)
                    return await future
            except BaseException as exc:
                self.abort(exc)
                raise
            finally:
                if future.done() and not future.cancelled():
                    future.exception()  # consume write-failure race with notification
                else:
                    future.cancel()
                self.waiter=None

    async def open(self):
        characteristic=self.client.services.get_characteristic(INPUT_UUID)
        if not characteristic or not self.client.services.get_characteristic(EVENT_UUID):
            raise RuntimeError("v0.7.0 audio firmware required; current device has no audio service")
        self.packet_bytes=min(self.packet_bytes,characteristic.max_write_without_response_size)
        if self.packet_bytes<20:
            raise RuntimeError("BLE packet limit below protocol minimum")
        await self.client.start_notify(EVENT_UUID,self.notify)
        p=await self.request(Op.HELLO,self.packet_bytes,expected=Op.CAPS)
        if len(p.data)!=4 or p.value!=MAX_BYTES or not p.epoch:
            raise RuntimeError("incompatible audio capabilities")
        packet_bytes, seconds=struct.unpack("<HH",p.data)
        if not 20<=packet_bytes<=self.packet_bytes or seconds!=10:
            raise RuntimeError("invalid negotiated audio limits")
        self.packet_bytes=packet_bytes
        self.epoch=p.epoch
        self.heartbeat=asyncio.create_task(self.keepalive())

    async def keepalive(self):
        try:
            while True:
                await asyncio.sleep(3)
                await self.request(Op.PING)
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            self.abort(exc)

    def next_transfer(self):
        self.check()
        if self.transfer==65535:
            raise RuntimeError("transfer ids exhausted; reconnect")
        self.transfer+=1
        while not self.events.empty():
            self.events.get_nowait()

    async def event(self, op, seconds=45):
        async with asyncio.timeout(seconds):
            while True:
                self.check()
                try:
                    p=await asyncio.wait_for(self.events.get(),0.2)
                except TimeoutError:
                    continue
                if p.op==op and p.transfer==self.transfer and p.epoch==self.epoch:
                    return p

    async def record(self):
        await self.request(Op.ARM,new_transfer=True)
        print("已就绪：在设备 Audio test 页面按住 A 说话，松开结束；B 停止。")
        p=await self.event(Op.RECORDED)
        if not 3200<=p.value<=320000 or p.value%2 or p.data not in (b"\x00",b"\x01"):
            raise RuntimeError("invalid recorded length")
        if p.data==b"\x01":
            print("已达到 10 秒上限，设备已自动停止录音。")
        pcm=bytearray()
        started=time.monotonic()
        async with asyncio.timeout(180):
            while len(pcm)<p.value:
                block=await self.request(Op.PULL,len(pcm),expected=Op.AUDIO)
                if not block.data or len(block.data)%2 or len(pcm)+len(block.data)>p.value:
                    raise RuntimeError("invalid captured audio block")
                pcm.extend(block.data)
        print(f"设备→电脑：{len(pcm)} bytes，{len(pcm)/(time.monotonic()-started):.0f} B/s")
        return bytes(pcm),16000

    async def play(self, pcm, rate):
        # Reuse the WAV validator so direct API callers cannot bypass limits.
        make_wav(pcm,rate)
        await self.request(Op.BEGIN,rate,struct.pack("<I",len(pcm)),new_transfer=True)
        chunk=(self.packet_bytes-HEADER.size)&~1
        started=time.monotonic()
        async with asyncio.timeout(180):
            for offset in range(0,len(pcm),chunk):
                await self.request(Op.DATA,offset,pcm[offset:offset+chunk])
                await asyncio.sleep(0)  # cancellation and keepalive between packets
            await self.request(Op.COMMIT,len(pcm))
        print(f"电脑→设备：{len(pcm)} bytes，{len(pcm)/(time.monotonic()-started):.0f} B/s")
        await self.request(Op.PLAY,expected=Op.PLAYING)
        print("设备报告开始播放；B 可随时停止。")
        await self.event(Op.PLAYED,15)
        print("设备报告播放结束。实际声音请人工确认。")

    async def close(self):
        if self.heartbeat:
            self.heartbeat.cancel()
            await self.heartbeat
        self.closed=True
        self.abort(RuntimeError("audio session closed"))
        # No bulk-transfer lock: stop preempts a timed-out/in-flight data request.
        if self.client.is_connected:
            with contextlib.suppress(Exception):
                await asyncio.wait_for(self.client.write_gatt_char(INPUT_UUID,
                    Packet(Op.CANCEL,self.transfer,self.epoch).encode(),response=True),2)
            with contextlib.suppress(Exception):
                await self.client.stop_notify(EVENT_UUID)


async def run(args):
    from bleak import BleakClient
    targets=await scan_targets()
    if args.address:
        targets=[t for t in targets if t.address.lower()==args.address.lower()]
    if not targets:
        raise RuntimeError("未发现设备：打开 BLE，首次点击 Pair；关闭网页中的设备连接和旧控制台。")
    if len(targets)!=1:
        for t in targets:
            print(f"{t.name}: {t.address}")
        raise RuntimeError("发现多个设备，请用 --address 指定本次列表中的地址。")
    print("请在设备上进入 Settings → Audio test。此工具不调用语音服务，也不上传云端。")
    async with BleakClient(targets[0].device,pair=True,timeout=30) as ble:
        client=AudioClient(ble,args.packet_bytes)
        try:
            await client.open()
            print(f"协商包长 {client.packet_bytes} bytes；单包信用窗口，非实时流。Ctrl+C 停止。")
            if args.command in ("record","echo"):
                pcm,rate=await client.record()
                if args.command=="record":
                    # Exclusive creation: never overwrite a personal recording.
                    with Path(args.output).open("xb") as output:
                        output.write(make_wav(pcm,rate))
                    print("录音已保存到指定本地文件。")
                else:
                    await client.play(pcm,rate)
            elif args.command=="tone":
                rate=16000
                pcm=b"".join(struct.pack("<h",int(2000*math.sin(2*math.pi*440*i/rate)))
                             for i in range(rate//2))
                await client.play(pcm,rate)
            elif args.command=="play":
                with Path(args.wav).open("rb") as source:
                    pcm,rate=read_wav(source.read(MAX_BYTES+4097))
                await client.play(pcm,rate)
        finally:
            await client.close()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--address")
    parser.add_argument("--packet-bytes",type=int,default=244)
    modes=parser.add_subparsers(dest="command",required=True)
    modes.add_parser("tone",help="播放半秒低音量测试音")
    modes.add_parser("echo",help="设备录音→BLE→电脑内存→BLE→设备回放")
    record=modes.add_parser("record",help="将设备录音保存为完整 WAV")
    record.add_argument("output")
    play=modes.add_parser("play",help="将指定 PCM16 单声道短 WAV 发到设备")
    play.add_argument("wav")
    args=parser.parse_args()
    try:
        asyncio.run(run(args))
    except KeyboardInterrupt:
        print("已请求停止；断连后不会自动重播。")
    except Exception as exc:
        print(f"Audio test failed: {exc}")
        return 1
    return 0


if __name__=="__main__":
    raise SystemExit(main())
