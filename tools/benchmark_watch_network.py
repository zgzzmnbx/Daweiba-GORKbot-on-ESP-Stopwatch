"""Explicit live-device protocol measurements; no cloud calls or saved mic audio.

Close the formal client's device connection before running. This tool alone
cannot certify cloud dialogues, diverse physical faults, hearing or battery.
"""
import argparse,asyncio,json,math,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'03-Src/stopwatch-voice-companion'),str(ROOT/'tools')]
from companion.network import WifiClient,WifiAudioBridge
from companion.network_store import NetworkStore
from stopwatch_ble import BleExpressionClient,scan_targets
from stopwatch_audio import AudioClient,read_wav

def stats(values):
    if not values:return {'n':0}
    values=sorted(values)
    return dict(n=len(values),p50=values[math.ceil(.5*len(values))-1],p95=values[math.ceil(.95*len(values))-1],max=values[-1])

async def run(args):
    if not args.live:raise ValueError('Real commands/audio require --live; first stop the formal device connection')
    count=args.count or (1000 if args.mode=='control' else 30)
    if not 1<=count<=10000:raise ValueError('count must be 1..10000')
    client=None;audio=None;records=[]
    report=dict(route=args.route,mode=args.mode,requested=count,started=time.strftime('%Y-%m-%dT%H:%M:%S%z'),
                software='0.20.0-dev',physical_hearing='NOT_RUN',cloud_dialogue='NOT_RUN',samples=records)
    path=Path(args.output);path.parent.mkdir(parents=True,exist_ok=True)
    try:
        if args.route=='wifi':
            store=NetworkStore(ROOT/'03-Src/stopwatch-voice-companion/network.local.json');store.load()
            if not store.secret:raise ValueError('Configure securely through the formal UI first')
            client=WifiClient();await client.connect(args.address or store.address,store.secret['identity'],bytes.fromhex(store.secret['key']))
            raw=WifiAudioBridge(client);report['device_status']=await client.control()
            # Public status has no passwords/keys; keep device identity only local.
        else:
            found=await scan_targets()
            if args.address:found=[d for d in found if d.address.lower()==args.address.lower()]
            if len(found)!=1:raise ValueError('Need one current scanned Watch; use --address from that scan')
            client=BleExpressionClient();await client.connect(found[0]);raw=client.client
        pcm=rate=None
        if args.mode=='down':
            if not args.wav:raise ValueError('Supply an existing fixed test WAV with --wav; no TTS is generated')
            pcm,rate=read_wav(Path(args.wav).read_bytes())
        if args.mode!='control':
            audio=AudioClient(raw,packet_bytes=4096) if args.route=='wifi' else AudioClient(raw)
            await audio.open()
        for i in range(count):
            row=dict(index=i+1,result='FAIL');records.append(row);started=time.monotonic()
            try:
                if args.mode=='control':
                    reply=await client.send_command('idle')
                    if not reply.startswith('OK:'):raise RuntimeError('No application acknowledgement')
                    row['seconds']=time.monotonic()-started
                elif args.mode=='down':
                    def progress(value):
                        if value['stage']=='ready':row.update(commit_seconds=value['elapsed'],wire_bytes=value['bytes'])
                    async def committed():row['prepare_and_commit_seconds']=time.monotonic()-started
                    await audio.play(pcm,rate,progress,codec=args.codec,before_play=committed)
                    row.update(seconds=time.monotonic()-started,packet_bytes=audio.packet_bytes,codec=audio.codec,source_bytes=len(pcm))
                else:
                    # Legacy diagnostic ARM requires Settings -> Audio test and
                    # a new A hold for each sample. Microphone data stays in RAM.
                    def progress(value):
                        if value['stage']=='received':row['receive_seconds']=value['elapsed']
                    captured,rate=await audio.record(progress)
                    row.update(seconds=time.monotonic()-started,bytes=len(captured),full_ten_seconds=len(captured)==320000)
                    captured=None
                row['result']='ACKNOWLEDGED' # never a hearing acceptance
            except Exception:
                row.update(seconds=time.monotonic()-started,error='current sample interrupted; no replay')
                break # Do not manufacture recovery samples or silently retry.
            finally:path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        for key in ('seconds','commit_seconds','receive_seconds'):
            report[key]=stats([r[key] for r in records if r['result']=='ACKNOWLEDGED' and key in r])
        report['failures']=sum(r['result']=='FAIL' for r in records)
        report['completed']=len(records);report['full_ten_seconds']=sum(r.get('full_ten_seconds',False) for r in records)
    finally:
        if audio:await audio.close()
        if client:await client.disconnect()
        path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k not in ('samples','device_status')},ensure_ascii=False))
    return 1 if report['failures'] or report['completed']!=count else 0

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=('control','down','up'))
    parser.add_argument('--route',choices=('wifi','ble'),required=True)
    parser.add_argument('--live',action='store_true',help='explicitly run real commands/audio on the connected device')
    parser.add_argument('--address',default='');parser.add_argument('--wav');parser.add_argument('--count',type=int)
    parser.add_argument('--codec',choices=('auto','pcm16','opus'),default='auto')
    parser.add_argument('--output',default=str(ROOT/'Codex-Temp/wifi-ble-v020/live-benchmark.json'))
    args=parser.parse_args()
    try:return asyncio.run(run(args))
    except KeyboardInterrupt:print('Cancelled; no replay')
    except Exception:print('Measurement could not complete; check current device, secure configuration and output record',file=sys.stderr);return 1
    return 0
if __name__=='__main__':raise SystemExit(main())
