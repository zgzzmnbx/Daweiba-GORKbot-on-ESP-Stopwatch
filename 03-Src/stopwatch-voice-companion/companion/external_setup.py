"""Provision local callers without printing credentials or starting notifications."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import secrets

from .external import ROOT


def write_private(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    if os.name != 'nt':
        temporary.chmod(0o600)
    temporary.replace(path)


def provision(source, token_file=None, *, registry_path=None, enable=None, rotate=False):
    if not re.fullmatch(r'[a-z][a-z0-9_-]{0,39}', source):
        raise ValueError('source must be a lowercase application identifier')
    path = Path(registry_path or ROOT / 'external-clients.local.json')
    data = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {'clients': {}}
    clients = data['clients']
    old = clients.get(source)
    if old is None or rotate:
        if token_file is None:
            raise ValueError('new or rotated registration requires --token-file')
        token = secrets.token_urlsafe(32)
        write_private(token_file, {'source': source, 'token': token, 'protocol_version': '1.0'})
        clients[source] = {'token_sha256': hashlib.sha256(token.encode()).hexdigest(), 'enabled': enable is True,
                           'label': source, 'display_targets': ['desktop', 'watch'],
                           'speech_targets': [], 'max_priority': 2}
    elif token_file:
        saved = json.loads(Path(token_file).read_text(encoding='utf-8'))
        if saved.get('source') != source or hashlib.sha256(saved['token'].encode()).hexdigest() != old['token_sha256']:
            raise ValueError('token file does not match; use --rotate explicitly to replace')
    if enable is not None:
        clients[source]['enabled'] = enable
    write_private(path, data)
    return {'source': source, 'enabled': clients[source]['enabled']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True)
    parser.add_argument('--token-file', type=Path)
    parser.add_argument('--registry', type=Path)
    parser.add_argument('--rotate', action='store_true')
    toggle = parser.add_mutually_exclusive_group()
    toggle.add_argument('--enable', action='store_true')
    toggle.add_argument('--disable', action='store_true')
    args = parser.parse_args()
    try:
        result = provision(args.source, args.token_file, registry_path=args.registry,
                           enable=True if args.enable else False if args.disable else None, rotate=args.rotate)
    except (OSError, ValueError, KeyError, TypeError):
        parser.error('配置失败；请核对来源、令牌文件及目录权限。令牌不会输出。')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
