"""Bounded BLE audio bench. No PC microphone, HTTP, ASR or cloud.

Playback works on the avatar page; recording requires Audio test and button A.
It transfers one complete clip before playback and is not live streaming.
"""
from __future__ import annotations

import argparse
import asyncio
import contextlib
import io
import inspect
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
SERVICE_UUID = "48f1b001-8a75-4db6-9c18-590f7e9b0a01"
BENCH_VERSION = "0.9.0"

ERROR_DETAILS = {
    5: "audio driver/capture failure (legacy firmware)",
    9: "microphone initialization failed",
    10: "microphone record queue failed",
    11: "microphone capture timed out (>1000 ms)",
    12: "speaker initialization failed",
    13: "speaker playback queue failed",
    14: "Opus decode failed",
}
HEADER = struct.Struct("<BBHII")
MAX_BYTES = 480_000
MAX_PACKET = 244
OPUS_HELLO_ID = 0xF00D


def audio_connection(device, client_factory=None):
    """Discover the current audio database, not a pre-upgrade Windows cache.

    Unfiltered UNCACHED discovery also failed with E_UNEXPECTED on this host;
    querying this service specifically works without removing the device bond.
    """
    if client_factory is None:
        from bleak import BleakClient
        client_factory=BleakClient
    return client_factory(device,pair=True,timeout=30,services=[SERVICE_UUID],
                          winrt={"use_cached_services":False})


class Op(IntEnum):
    HELLO=1; ARM=2; PING=3; BEGIN=4; DATA=5; COMMIT=6; PLAY=7; CANCEL=8; PULL=9; BEGIN_OPUS=10
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
        self.transfer=OPUS_HELLO_ID
        self.opus_supported=False
        self.codec="pcm16"
        self.source_bytes=0
        self.lock=asyncio.Lock()
        self.waiter=None
        self.events=asyncio.Queue(maxsize=8)
        self.data_acks=asyncio.Queue(maxsize=8)
        self.data_event=asyncio.Event()
        self.data_active=False
        self.data_window=3  # Below the device's four-packet ingress queue.
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
            detail = ERROR_DETAILS.get(p.value, "device error") if p.op==Op.ERROR else "cancelled"
            self.abort(RuntimeError(f"device stopped audio (code {p.value}): {detail}")); return
        if self.data_active and p.op==Op.ACK and p.data==bytes([Op.DATA]):
            if self.data_acks.full():
                self.abort(RuntimeError("audio DATA acknowledgement overflow"))
            else:
                self.data_acks.put_nowait(p)
                self.data_event.set()
            return
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
        self.data_event.set()
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
            except TimeoutError as exc:
                error = TimeoutError(
                    f"等待 Watch 音频 {op.name} 回执超时；请检查蓝牙连接，旧版固件还需打开 Settings → Audio test")
                self.abort(error)
                raise error from exc
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
            raise RuntimeError("未发现音频 GATT 特征，不能据此判定固件版本。请检查蓝牙服务发现、"
                               "关闭其他蓝牙连接并重试；仍失败请保留报错，勿直接重刷或清配对。")
        self.packet_bytes=min(self.packet_bytes,characteristic.max_write_without_response_size)
        if self.packet_bytes<20:
            raise RuntimeError("BLE packet limit below protocol minimum")
        await self.client.start_notify(EVENT_UUID,self.notify)
        p=await self.request(Op.HELLO,self.packet_bytes,expected=Op.CAPS)
        if len(p.data) not in (4,5) or p.value!=MAX_BYTES or not p.epoch:
            raise RuntimeError("incompatible audio capabilities")
        packet_bytes, seconds=struct.unpack_from("<HH",p.data)
        if not 20<=packet_bytes<=self.packet_bytes or seconds!=10:
            raise RuntimeError("invalid negotiated audio limits")
        self.packet_bytes=packet_bytes
        self.opus_supported=len(p.data)==5 and bool(p.data[4]&1)
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

    async def progress(self, callback, stage, done=0, total=0, started=None):
        if callback is None:
            return
        elapsed=max(0.0,time.monotonic()-(started or time.monotonic()))
        value={"stage":stage,"bytes":done,"total":total,"elapsed":elapsed,
               "rate":done/elapsed if done and elapsed else 0.0,
               "packet_bytes":self.packet_bytes,"window":self.data_window,
               "codec":self.codec,"source_bytes":self.source_bytes}
        result=callback(value)
        if inspect.isawaitable(result):
            await result

    async def record(self, progress=None):
        await self.request(Op.ARM,new_transfer=True)
        await self.progress(progress,"armed")
        print("已就绪：在设备 Audio test 页面按住 A 说话，松开结束；B 停止。")
        async with asyncio.timeout(45):
            while True:
                self.check()
                p=await self.events.get()
                if p.op==Op.RECORDING:
                    await self.progress(progress,"recording")
                elif p.op==Op.RECORDED:
                    break
        if not 3200<=p.value<=320000 or p.value%2 or p.data not in (b"\x00",b"\x01"):
            raise RuntimeError("invalid recorded length")
        if p.data==b"\x01":
            print("已达到 10 秒上限，设备已自动停止录音。")
        pcm=bytearray()
        started=time.monotonic()
        await self.progress(progress,"receiving",0,p.value,started)
        async with asyncio.timeout(180):
            while len(pcm)<p.value:
                block=await self.request(Op.PULL,len(pcm),expected=Op.AUDIO)
                if not block.data or len(block.data)%2 or len(pcm)+len(block.data)>p.value:
                    raise RuntimeError("invalid captured audio block")
                pcm.extend(block.data)
                await self.progress(progress,"receiving",len(pcm),p.value,started)
        print(f"设备→电脑：{len(pcm)} bytes，{len(pcm)/(time.monotonic()-started):.0f} B/s")
        await self.progress(progress,"received",len(pcm),p.value,started)
        return bytes(pcm),16000

    async def play(self, pcm, rate, progress=None, *, codec="auto"):
        job_started=time.monotonic()
        # Reuse the WAV validator so direct API callers cannot bypass limits.
        make_wav(pcm,rate)
        if codec not in ("auto", "pcm16", "opus"):
            raise ValueError("codec must be auto, pcm16 or opus")
        if codec=="opus" and not self.opus_supported:
            raise RuntimeError("Watch does not advertise Opus support")
        self.source_bytes=len(pcm)
        if codec=="opus" or (codec=="auto" and self.opus_supported):
            from stopwatch_opus import encode_opus
            clip=encode_opus(pcm,rate)
            payload=clip.data
            begin=Op.BEGIN_OPUS
            metadata=struct.pack("<III",len(payload),clip.samples,clip.skip)
            self.codec="opus"
        else:
            payload=pcm
            begin=Op.BEGIN
            metadata=struct.pack("<I",len(payload))
            self.codec="pcm16"
        await self.request(begin,rate,metadata,new_transfer=True)
        chunk=self.packet_bytes-HEADER.size
        if begin==Op.BEGIN:
            chunk &= ~1
        started=time.monotonic()
        await self.progress(progress,"sending",0,len(payload),started)
        await self.send_data(payload, chunk, progress, started)
        await self.request(Op.COMMIT,len(payload))
        send_elapsed=time.monotonic()-started
        print(f"电脑→设备 {self.codec}：{len(payload)} bytes，发送 {send_elapsed:.2f} s，{len(payload)/send_elapsed:.0f} B/s")
        await self.request(Op.PLAY,expected=Op.PLAYING)
        await self.progress(progress,"playing",len(payload),len(payload),started)
        print("设备报告开始播放；B 可随时停止。")
        await self.event(Op.PLAYED,15)
        await self.progress(progress,"played",len(payload),len(payload),started)
        print(f"设备报告播放结束；从编码开始 {time.monotonic()-job_started:.2f} s。实际声音请人工确认。")

    async def send_data(self, pcm, chunk, progress, started):
        # The receiver processes packets in order and ACKs each next offset.
        # Keep at most three unacknowledged writes for its four-slot queue;
        # progress advances only on device ACK, never on local write return.
        async with self.lock:
            self.check()
            while not self.data_acks.empty():
                self.data_acks.get_nowait()
            self.data_active=True
            sent=acked=0
            pending=[]
            try:
                async with asyncio.timeout(180):
                    while acked<len(pcm):
                        self.check()
                        while len(pending)<self.data_window and sent<len(pcm):
                            end=min(sent+chunk,len(pcm))
                            packet=Packet(Op.DATA,self.transfer,self.epoch,sent,pcm[sent:end])
                            try:
                                await asyncio.wait_for(
                                    self.client.write_gatt_char(INPUT_UUID,packet.encode(),response=False),
                                    self.timeout)
                            except TimeoutError as exc:
                                raise TimeoutError("等待 Watch 音频 DATA 写入超时") from exc
                            pending.append(end)
                            sent=end
                        if self.data_acks.empty():
                            self.data_event.clear()
                            try:
                                await asyncio.wait_for(self.data_event.wait(),self.timeout)
                            except TimeoutError as exc:
                                raise TimeoutError("等待 Watch 音频 DATA 回执超时；传输未完成") from exc
                        self.check()
                        response=self.data_acks.get_nowait()
                        if response.value not in pending:
                            continue  # stale or wrong offset cannot advance progress
                        boundary=pending.index(response.value)
                        acked=response.value
                        del pending[:boundary+1]
                        await self.progress(progress,"sending",acked,len(pcm),started)
                        await asyncio.sleep(0)
            except BaseException as exc:
                self.abort(exc)
                raise
            finally:
                self.data_active=False
                self.data_event.clear()
                while not self.data_acks.empty():
                    self.data_acks.get_nowait()

    async def close(self):
        if self.heartbeat:
            self.heartbeat.cancel()
            await self.heartbeat
        self.closed=True
        self.abort(RuntimeError("audio session closed"))
        # No bulk-transfer lock: stop preempts a timed-out/in-flight data request.
        if self.client.is_connected and self.epoch:
            with contextlib.suppress(Exception):
                await asyncio.wait_for(self.client.write_gatt_char(INPUT_UUID,
                    Packet(Op.CANCEL,self.transfer,self.epoch).encode(),response=True),2)
            with contextlib.suppress(Exception):
                await self.client.stop_notify(EVENT_UUID)


async def run(args):
    print(f"StopWatch BLE audio bench v{BENCH_VERSION}")
    targets=await scan_targets()
    if args.address:
        targets=[t for t in targets if t.address.lower()==args.address.lower()]
    if not targets:
        raise RuntimeError("未发现设备：打开 BLE，首次点击 Pair；关闭网页中的设备连接和旧控制台。")
    if len(targets)!=1:
        for t in targets:
            print(f"{t.name}: {t.address}")
        raise RuntimeError("发现多个设备，请用 --address 指定本次列表中的地址。")
    print("播放可留在小人页；录音请进入 Settings → Audio test。此工具不调用语音服务，也不上传云端。")
    async with audio_connection(targets[0].device) as ble:
        client=AudioClient(ble,args.packet_bytes)
        try:
            await client.open()
            print(f"协商包长 {client.packet_bytes} bytes；Opus={client.opus_supported}；窗口 {client.data_window} 包。Ctrl+C 停止。")
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
                # The device probe deliberately uses a conservative speaker
                # volume (48/255). Keep the diagnostic tone long and strong
                # enough to be audibly useful without changing firmware.
                pcm=b"".join(struct.pack("<h",int(16000*math.sin(2*math.pi*440*i/rate)))
                             for i in range(rate*2))
                await client.play(pcm,rate,codec=args.codec)
            elif args.command=="play":
                with Path(args.wav).open("rb") as source:
                    pcm,rate=read_wav(source.read(MAX_BYTES+4097))
                await client.play(pcm,rate,codec=args.codec)
        finally:
            await client.close()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--address")
    parser.add_argument("--packet-bytes",type=int,default=244)
    parser.add_argument("--codec",choices=("auto","pcm16","opus"),default="auto",
                        help="播放编码；pcm16 可在同一固件上与 Opus 做 A/B 测量")
    modes=parser.add_subparsers(dest="command",required=True)
    modes.add_parser("tone",help="播放 2 秒清晰诊断音")
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
