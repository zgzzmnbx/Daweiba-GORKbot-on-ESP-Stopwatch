"""Isolated loopback acceptance server; device, voice service and sentinels stay disabled."""
import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'03-Src/stopwatch-voice-companion'))
from companion.app import create_app
import uvicorn

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--port',type=int,default=8877)
    p.add_argument('--directory',type=Path,default=ROOT/'Codex-Temp/motion-preview')
    a=p.parse_args();a.directory.mkdir(parents=True,exist_ok=True)
    for name in ('sentinel.json','codex.json'):
        (a.directory/name).write_text(json.dumps({'enabled':False}),encoding='utf-8')
    app=create_app({'port':a.port,'auto_connect_device':False,'auto_connect_voice':False,
        'motion_state_path':a.directory/'motion.local.json',
        'motion_library_path':a.directory/'motion-library.local.json',
        'sentinel_state_path':a.directory/'sentinel.json','codex_state_path':a.directory/'codex.json',
        'codex_hook_queue':a.directory/'hooks','codex_jsonl_root':a.directory/'sessions'})
    print(f'ISOLATED_MOTION_PREVIEW http://127.0.0.1:{a.port}; no device/voice connection',flush=True)
    uvicorn.run(app,host='127.0.0.1',port=a.port,log_level='warning')
