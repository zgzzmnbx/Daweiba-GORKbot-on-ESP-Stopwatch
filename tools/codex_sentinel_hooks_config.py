"""Preview or precisely merge/remove Gork-owned hooks in a JSON hooks file."""
import argparse
import copy
import json
from pathlib import Path
import shutil
import sys
from datetime import datetime


EVENTS = ('UserPromptSubmit', 'PreToolUse', 'PostToolUse', 'PermissionRequest', 'Stop', 'Interrupt')
MARK = 'gork-codex-sentinel-v0.18.0'


def own_entry(command):
    return {'hooks': [{'type': 'command', 'command': command,
                                           'commandWindows': command, 'timeout': 3}]}


def is_ours(entry):
    if not isinstance(entry, dict) or not isinstance(entry.get('hooks'), list) or len(entry['hooks']) != 1:
        return False
    hook = entry['hooks'][0]
    return isinstance(hook, dict) and isinstance(hook.get('command'), str) and MARK in hook['command']


def merge(data, command, remove=False):
    result = copy.deepcopy(data)
    hooks = result.get('hooks', {})
    if not remove:
        result['hooks'] = hooks
    for event in EVENTS:
        entries = hooks.get(event, [])
        if not isinstance(entries, list):
            raise ValueError(f'{event} is not a list')
        kept = [entry for entry in entries if not is_ours(entry)]
        if not remove:
            kept.append(own_entry(command))
        if kept:
            hooks[event] = kept
        else:
            hooks.pop(event, None)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('file', type=Path, help='hooks.json to review or edit')
    parser.add_argument('--remove', action='store_true')
    parser.add_argument('--apply', action='store_true', help='write exact merge after timestamped backup')
    args = parser.parse_args(argv)
    current = json.loads(args.file.read_text(encoding='utf-8')) if args.file.exists() else {}
    if not isinstance(current, dict):
        raise ValueError('hooks config root must be an object')
    bridge = Path(__file__).with_name('codex_sentinel_hook.py').resolve()
    command = f'"{sys.executable}" "{bridge}" --{MARK}'
    planned = merge(current, command, args.remove)
    if args.apply and planned != current:
        args.file.parent.mkdir(parents=True, exist_ok=True)
        if args.file.exists():
            stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
            shutil.copy2(args.file, args.file.with_name(args.file.name + f'.{stamp}.bak'))
        temporary = args.file.with_suffix(args.file.suffix + '.tmp')
        temporary.write_text(json.dumps(planned, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        temporary.replace(args.file)
    print(json.dumps({'mode': 'applied' if args.apply else 'dry-run',
                      'operation': 'remove' if args.remove else 'install',
                      'changed': planned != current, 'events': list(EVENTS),
                      'target': str(args.file), 'preserved_other_entries': True}, ensure_ascii=False))
    if not args.apply:
        print(json.dumps(planned, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
