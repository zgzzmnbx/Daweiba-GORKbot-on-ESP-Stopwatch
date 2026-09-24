"""Encode a bounded mono PCM clip as length-prefixed raw Opus packets for BLE.

libsndfile writes Ogg Opus. The Watch uses libopus directly, so only the
audio packets and the OpusHead pre-skip are sent; Ogg page headers stay on PC.
"""
from __future__ import annotations

import io
import struct
from dataclasses import dataclass


@dataclass(frozen=True)
class OpusClip:
    data: bytes
    samples: int
    skip: int


def _ogg_packets(data: bytes) -> list[bytes]:
    packets: list[bytes] = []
    pending = bytearray()
    offset = 0
    serial = None
    sequence = 0
    while offset < len(data):
        if len(data) - offset < 27 or data[offset:offset + 4] != b"OggS" or data[offset + 4] != 0:
            raise ValueError("invalid Ogg Opus page")
        count = data[offset + 26]
        if len(data) - offset < 27 + count:
            raise ValueError("truncated Ogg lacing table")
        page_serial, page_sequence = struct.unpack_from("<II", data, offset + 14)
        if serial is None:
            serial = page_serial
        if serial != page_serial or page_sequence != sequence:
            raise ValueError("unexpected Ogg stream or page order")
        sequence += 1
        lacing = data[offset + 27:offset + 27 + count]
        body = offset + 27 + count
        if len(data) - body < sum(lacing):
            raise ValueError("truncated Ogg page")
        if bool(data[offset + 5] & 1) != bool(pending):
            raise ValueError("invalid Ogg continuation")
        for size in lacing:
            pending.extend(data[body:body + size])
            body += size
            if size < 255:
                packets.append(bytes(pending))
                pending.clear()
        offset = body
    if pending or len(packets) < 3:
        raise ValueError("incomplete Ogg Opus stream")
    return packets


def encode_opus(pcm: bytes, rate: int) -> OpusClip:
    if rate not in (16000, 24000) or len(pcm) % 2 or not rate // 10 <= len(pcm) // 2 <= rate * 10:
        raise ValueError("expected 0.1–10 s PCM16 mono at 16 or 24 kHz")
    # Imports are lazy so existing PCM playback needs no Opus dependency.
    import numpy as np
    import soundfile as sf

    target = io.BytesIO()
    sf.write(target, np.frombuffer(pcm, dtype="<i2"), rate, format="OGG", subtype="OPUS")
    packets = _ogg_packets(target.getvalue())
    head, tags, *audio = packets
    if (len(head) < 19 or not head.startswith(b"OpusHead") or head[8] != 1 or head[9] != 1
            or not tags.startswith(b"OpusTags") or not audio):
        raise ValueError("unsupported Ogg Opus layout")
    pre_skip_48k = struct.unpack_from("<H", head, 10)[0]
    if pre_skip_48k % (48000 // rate):
        raise ValueError("Opus pre-skip cannot be represented at output rate")
    skip = pre_skip_48k // (48000 // rate)
    if skip > rate // 5:
        raise ValueError("Opus pre-skip exceeds device limit")
    framed = bytearray()
    for packet in audio:
        if not 0 < len(packet) <= 1275:
            raise ValueError("invalid Opus packet size")
        framed.extend(struct.pack("<H", len(packet)))
        framed.extend(packet)
    if len(framed) > 480_000:
        raise ValueError("encoded Opus exceeds Watch buffer")
    return OpusClip(bytes(framed), len(pcm) // 2, skip)
