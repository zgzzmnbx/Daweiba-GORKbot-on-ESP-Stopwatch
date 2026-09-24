#!/usr/bin/env python3
"""Minimal independent consumer for the local version-1 voice HTTP service.

This script does not import Gork, Electron, BLE, models or credentials.  With
no options it only reads capabilities.  `--text` explicitly requests local
TTS and writes a WAV file; it never records or plays audio itself.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
import uuid


def request(url: str, method: str = "GET", payload: dict | None = None, headers: dict | None = None):
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    request_headers = {"Content-Type": "application/json"} if data else {}
    request_headers.update(headers or {})
    with urlopen(Request(url, data=data, headers=request_headers, method=method), timeout=15) as response:
        body = response.read()
        return response.headers.get_content_type(), body


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8765", help="loopback voice-service base URL")
    parser.add_argument("--text", help="explicit local TTS text; omitted means capabilities only")
    parser.add_argument("--output", type=Path, default=Path("voice-example.wav"))
    args = parser.parse_args()
    base = args.url.rstrip("/")
    try:
        kind, body = request(base + "/v1/capabilities")
        capabilities = json.loads(body)
        if kind != "application/json" or capabilities.get("protocol_version") != 1:
            raise RuntimeError("incompatible voice-service protocol")
        print(json.dumps({"protocol_version": 1, "tts": capabilities.get("tts", {}), "cloud": capabilities.get("cloud", {})}, ensure_ascii=False))
        if not args.text:
            return
        _, body = request(base + "/v1/sessions", "POST", {})
        session = json.loads(body).get("session_id")
        if not session:
            raise RuntimeError("voice service did not return a session")
        headers = {"X-Voice-Session": session}
        try:
            _, body = request(base + f"/v1/sessions/{session}/turns", "POST", headers=headers)
            turn = json.loads(body).get("turn_id")
            if not isinstance(turn, int):
                raise RuntimeError("voice service did not return a turn")
            _, body = request(base + "/v1/tts/synthesize", "POST", {
                "turn_id": turn, "request_id": "example-" + str(uuid.uuid4()), "text": args.text,
                "speaker_id": 3, "speed": 1.0,
            }, headers)
            if not body.startswith(b"RIFF"):
                raise RuntimeError("service did not return WAV data")
            args.output.write_bytes(body)
            print(f"Wrote PCM WAV: {args.output}")
        finally:
            try: request(base + "/v1/sessions/" + session, "DELETE", headers=headers)
            except (HTTPError, URLError): pass
    except (HTTPError, URLError, ValueError, RuntimeError) as exc:
        raise SystemExit(f"voice service call failed: {exc}")


if __name__ == "__main__":
    main()
