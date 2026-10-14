"""Export pinned Watch catalog and the shared browser renderer, without hashes."""
import argparse
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    source = json.loads((ROOT/'03-Src/stopwatch-grok-avatar/assets/source-grok-bot/avatar-studio-project.json').read_text(encoding='utf-8'))
    text = '// Generated from pinned Watch Grok bot catalog.\nwindow.GorkCatalog = '+json.dumps({k:source[k] for k in ('expressions','sequences')},ensure_ascii=False,separators=(',',':'))+';\n'
    web = ROOT/'03-Src/stopwatch-voice-companion/static'
    desktop = ROOT/'03-Src/gork-desktop'
    for path, data in ((web/'gork-catalog.js',text),(desktop/'gork-catalog.js',text),(desktop/'gork-avatar.js',(web/'gork-avatar.js').read_text(encoding='utf-8'))):
        if args.check:
            assert path.read_text(encoding='utf-8')==data, f'Stale: {path}'
        else:
            path.write_text(data,encoding='utf-8',newline='\n')
    for name in ('avatar-engine.js','avatar-presets.js','gork-appearance.js'):
        data=(web/name).read_text(encoding='utf-8')
        if args.check:
            assert (desktop/name).read_text(encoding='utf-8')==data, f'Stale: {name}'
        else:
            (desktop/name).write_text(data,encoding='utf-8',newline='\n')
    motion = web/'motion'
    for name in ('gork-config.js','gork-pens.js','scene-controller.js','gork-renderer.js',
                 'gork-player.js','desktop-adapter.js','expression-preview.js','initial-config.gork.json','LICENSE.upstream','PEN-REFERENCES.md'):
        target=desktop/'motion'/name
        data=(motion/name).read_bytes()
        if args.check:
            assert target.read_bytes()==data, f'Stale motion asset: {name}'
        else:
            target.parent.mkdir(exist_ok=True)
            target.write_bytes(data)
    initial='// User handoff configuration; generated, never substitute defaults.\nwindow.GorkMotionInitial = '+(motion/'initial-config.gork.json').read_text(encoding='utf-8').strip()+';\n'
    for target in (motion/'initial-config.js',desktop/'motion/initial-config.js'):
        if args.check:
            assert target.read_text(encoding='utf-8')==initial, f'Stale: {target}'
        else:
            target.write_text(initial,encoding='utf-8',newline='\n')
    names=json.dumps(sorted({s['id'] for s in source['sequences']}|{'processing','generating','speaking','error','ready','sleepy','dizzy','happy-work'}))+ '\n'
    for target in (motion/'legacy-scene-names.json',desktop/'motion/legacy-scene-names.json'):
        if args.check:
            assert target.read_text(encoding='utf-8')==names, f'Stale: {target}'
        else:
            target.write_text(names,encoding='utf-8',newline='\n')
    print('Desktop/web catalog, renderer and motion assets match')
if __name__=='__main__':
    main()
