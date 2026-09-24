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
    print('Desktop/web catalog and renderer match')
if __name__=='__main__':
    main()
