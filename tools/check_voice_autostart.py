"""Opt-in local lifecycle check. No sessions, microphone, BLE or cloud requests.

Run with Codex-Temp/voice-runtime/.venv Python (httpx + psutil).
An isolated free port is required; only this check's own child is stopped.
"""
import argparse
from pathlib import Path
import socket
import sys
import time

import psutil

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / '03-Src/stopwatch-voice-companion'))
from companion.service_manager import VoiceServiceManager


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--voice-project', type=Path, default=ROOT / '03-Src/voice-service')
    parser.add_argument('--port', type=int, default=8875)
    args = parser.parse_args()
    project = args.voice_project.resolve()
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', args.port))
    manager = VoiceServiceManager({'voice_url':f'http://127.0.0.1:{args.port}',
        'voice_service_command':[sys.executable,str(project/'tools/serve_managed.py'),'--port',str(args.port)],
        'voice_service_cwd':str(project)})
    children = []
    try:
        state = manager.ensure()
        assert state['mode'] == 'owned', state
        process = psutil.Process(state['pid'])
        deadline = time.monotonic() + 45
        while time.monotonic() < deadline:
            health = manager.client.get(manager.url + '/v1/health').json()
            if health['ready']:
                break
            time.sleep(.25)
        assert health['ready'], 'local models did not become ready'
        children = process.children(recursive=True)
        assert children, 'inference child not found'
        caps = manager.client.get(manager.url + '/v1/capabilities').json()
        assert len(caps['cloud']['voices']) == 6 and caps['cloud']['request_voice']
        assert len(caps['tts']['speakers']) == 100
        assert manager.ensure()['pid'] == state['pid']
        assert manager.snapshot()['mode'] == 'owned'
        print('PASS: managed start, real local models ready, six cloud voices, 100 local speakers, repeated ensure reuses owned process')
    finally:
        manager.close()
    _, alive = psutil.wait_procs(children, timeout=10)
    assert not alive, 'inference worker survived graceful close'
    print('PASS: parent pipe close stops owned service and inference worker')


if __name__ == '__main__':
    main()
