"""Export the pinned local Avatar Lab snapshot without network or temp-folder inputs."""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    source = ROOT / '03-Src/avatar-library'
    target = ROOT / '03-Src/stopwatch-voice-companion/static'
    document = json.loads((source / 'defaultStudioDocument.json').read_text(encoding='utf-8'))
    presets = [dict(id='gork' if a['name'] == 'Grok bot' else a['name'].lower(), name=a['name'],
                    body=a['body'], eyes=a['eyes'], colors=a['colors']) for a in document['library']['avatars']]
    presets.sort(key=lambda a: a['id'] != 'gork')
    notice = '/* Bible Strong Avatar Lab @79fe9ba; AGPL-3.0-only. See 03-Src/avatar-library. */\n'
    library = notice + '(function(root){const presets=' + json.dumps(presets, ensure_ascii=False, separators=(',', ':')) + ';if(typeof module!=="undefined")module.exports=presets;else root.GorkPresets=presets;})(typeof window!=="undefined"?window:this);\n'
    encoded = (source/'standaloneEngine.generated.ts').read_text(encoding='utf-8').split('export const standaloneEngineSource = ', 1)[1].strip().rstrip(';')
    for name, data in [('avatar-presets.js', library), ('avatar-engine.js', notice + json.loads(encoded))]:
        if args.check:
            assert (target/name).read_text(encoding='utf-8') == data, f'Stale: {name}'
        else:
            (target/name).write_text(data, encoding='utf-8', newline='\n')
    print('Avatar library matches the pinned local source')

if __name__ == '__main__':
    main()
