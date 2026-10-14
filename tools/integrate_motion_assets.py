"""Import handoff assets without replacing the project's existing avatar engine."""
from pathlib import Path
import json
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'Codex-Temp/motion-editor-handoff-20261003/Stopwatch-Windows-Handoff'
WEB = ROOT / '03-Src/stopwatch-voice-companion/static'
TARGET = WEB / 'motion'


def main():
    TARGET.mkdir(exist_ok=True)
    for name in ('gork-config.js', 'gork-pens.js', 'scene-controller.js',
                 'gork-renderer.js', 'gork-player.js', 'editor.js', 'index.html',
                 'style.css', 'LICENSE.upstream', 'PEN-REFERENCES.md', 'INTEGRATION.md'):
        dest = TARGET / name
        if dest.exists():
            raise SystemExit(f'Refusing to overwrite integrated asset: {dest}')
        shutil.copyfile(SOURCE / 'editor-source/dist' / name, dest)
    shutil.copyfile(SOURCE / 'gork-scenes.gork.json', TARGET / 'initial-config.gork.json')
    (TARGET / 'package.json').write_text('{"type":"commonjs"}\n', encoding='utf-8')
    script = "const c=require(process.argv[1]);process.stdout.write(JSON.stringify(c.fields,null,2)+'\\n')"
    fields = subprocess.check_output(['node', '-e', script, str(TARGET / 'gork-config.js')])
    (TARGET / 'field-specs.json').write_bytes(fields)
    tests = ROOT / '03-Src/stopwatch-voice-companion/tests/motion'
    shutil.copytree(SOURCE / 'editor-source/tests', tests)
    for f in tests.rglob('*.cjs'):
        text = f.read_text(encoding='utf-8').replace('../dist/', '../../static/motion/').replace('../dist', '../../static/motion')
        text = text.replace('vendor/avatar-engine.js', '../avatar-engine.js').replace('vendor/avatar-presets.js', '../avatar-presets.js')
        f.write_text(text, encoding='utf-8', newline='\n')
    print('Imported shared motion sources, initial user config and tests; existing engine preserved.')


if __name__ == '__main__':
    main()
