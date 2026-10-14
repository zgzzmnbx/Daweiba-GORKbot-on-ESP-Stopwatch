"""Validated, revisioned local motion configuration. SPDX-License-Identifier: AGPL-3.0-only."""
from copy import deepcopy
import json
import math
import os
from pathlib import Path
import tempfile
import threading
import shutil
import time
import uuid
import re
import hashlib

ASSETS = Path(__file__).resolve().parents[1] / 'static/motion'
NAMES = ('idle', 'loading', 'writing', 'question')
MAX_BYTES = 20480

def watch_token(entry):
    """Compiled identity fits the existing encrypted 20-byte command channel."""
    value={'id':entry['id'],'name':entry['name'],'scene':entry['scene'],'config':validate(entry['config'])}
    encoded=json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf-8')
    digest=hashlib.sha256(encoded).hexdigest()[:12]
    return 'cx'+''.join('abcdefghijklmnop'[int(c,16)] for c in digest)


def exact(value, keys, label):
    if type(value) is not dict or set(value) != set(keys):
        raise ValueError(f'{label} 字段不完整或含未知字段')


def validate(config):
    if len(json.dumps(config, ensure_ascii=False).encode('utf-8')) > MAX_BYTES:
        raise ValueError('配置不能超过 20 KiB')
    exact(config, ('schema', 'version', 'scenes'), '配置')
    if config['schema'] != 'gork-motion-studio' or type(config['version']) is not int or config['version'] not in (1, 2):
        raise ValueError('不支持的动效配置版本')
    exact(config['scenes'], NAMES, '场景')
    specs = json.loads((ASSETS / 'field-specs.json').read_text(encoding='utf-8'))
    out = deepcopy(config)
    for name in NAMES:
        groups = ['eyes', 'motion'] + ([] if name == 'idle' else [name])
        exact(config['scenes'][name], groups, name)
        for group in groups:
            fields = specs[group]
            if group == 'writing' and config['version'] == 1:
                fields = {k: specs[group][k] for k in ('x', 'y', 'scale', 'penScale')}
                fields['handScale'] = ['旧手套', .6, 1.2, .05]
            exact(config['scenes'][name][group], fields, f'{name}.{group}')
            for key, meta in fields.items():
                v = config['scenes'][name][group][key]
                if isinstance(meta[1], list):
                    if type(v) is not str or v not in meta[1]:
                        raise ValueError('未知笔型')
                elif type(v) not in (int, float) or not meta[1] <= v <= meta[2] or not math.isfinite(v):
                    raise ValueError(f'{name}.{group}.{key} 超出范围')
    if config['version'] == 1:
        w = out['scenes']['writing']['writing']
        del w['handScale']
        w.update(penStyle='quill', strokeWidth=3)
        out['version'] = 2
    return out


def parse(text):
    if len(text.encode('utf-8')) > MAX_BYTES:
        raise ValueError('配置不能超过 20 KiB')
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('JSON 含重复字段')
            result[key] = value
        return result
    return validate(json.loads(text, object_pairs_hook=pairs))


class Conflict(ValueError):
    pass


class MotionStore:
    def __init__(self, path):
        self.path = Path(path)
        self.backup = self.path.with_suffix(self.path.suffix + '.bak')
        self.lock = threading.Lock()
        self.warning = ''

    def _atomic(self, path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, name = tempfile.mkstemp(prefix=path.name + '-', suffix='.tmp', dir=path.parent)
        try:
            with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as f:
                json.dump(value, f, ensure_ascii=False, indent=2, allow_nan=False)
                f.write('\n')
                f.flush()
                os.fsync(f.fileno())
            os.replace(name, path)
        finally:
            if os.path.exists(name):
                os.unlink(name)

    def _record(self, path):
        if path.stat().st_size > MAX_BYTES + 4096:
            raise ValueError('保存文件过大')
        record = json.loads(path.read_text(encoding='utf-8'))
        exact(record, ('revision', 'config'), '保存记录')
        if type(record['revision']) is not int or not 1 <= record['revision'] <= 2**53-1:
            raise ValueError('配置修订号无效')
        record['config'] = validate(record['config'])
        return record

    def _read(self):
        if not self.path.exists() and not self.backup.exists():
            record = {'revision': 1, 'config': parse((ASSETS / 'initial-config.gork.json').read_text(encoding='utf-8'))}
            self._atomic(self.path, record)
            return record
        try:
            return self._record(self.path)
        except (OSError, ValueError, TypeError):
            try:
                record = self._record(self.backup)
            except (OSError, ValueError, TypeError) as exc:
                raise ValueError('配置与备份均不可读；原文件已保留，请显式导入恢复') from exc
            self.warning = '当前配置损坏或不可读，使用最近有效备份；原文件已保留'
            return record

    def read(self):
        with self.lock:
            return {**self._read(), 'warning': self.warning}

    def save(self, config, expected_revision):
        next_config = validate(config)
        with self.lock:
            previous = self._read()
            if type(expected_revision) is not int or expected_revision != previous['revision']:
                raise Conflict('配置已在另一窗口更新；请读取保存版本后重新编辑')
            record = {'revision': previous['revision'] + 1, 'config': next_config}
            self._atomic(self.backup, previous)
            self._atomic(self.path, record)
            self.warning = ''
            return {**record, 'warning': ''}

    def recover(self, config):
        next_config = validate(config)
        with self.lock:
            try:
                self._read()
            except ValueError:
                pass
            else:
                raise Conflict('已有有效保存版本，请读取后按修订号保存')
            # Keep both corrupt originals before the explicit import replaces the primary.
            token = uuid.uuid4().hex[:12]
            for path in (self.path, self.backup):
                if path.exists():
                    shutil.copyfile(path, path.with_name(path.name + '.corrupt-' + token))
            record = {'revision': int(time.time()), 'config': next_config}
            self._atomic(self.path, record)
            self.warning = ''
            return {**record, 'warning': '已从显式导入恢复；损坏原文件另存保留'}


class MotionLibrary(MotionStore):
    """Named user expressions; default catalog and active playback are never written."""
    def _record(self, path):
        if path.stat().st_size > 2 * 1024 * 1024:
            raise ValueError('自定义表情库过大')
        record = json.loads(path.read_text(encoding='utf-8'))
        exact(record, ('schema', 'version', 'revision', 'entries'), '自定义表情库')
        if record['schema'] != 'gork-expression-library' or type(record['version']) is not int or record['version'] != 1:
            raise ValueError('不支持的表情库版本')
        if type(record['revision']) is not int or not 1 <= record['revision'] <= 2**53 - 1:
            raise ValueError('表情库修订号无效')
        if type(record['entries']) is not list or len(record['entries']) > 64:
            raise ValueError('自定义表情最多 64 个')
        ids, names = set(), set()
        for entry in record['entries']:
            exact(entry, ('id', 'name', 'scene', 'config'), '自定义表情')
            if type(entry['id']) is not str or not re.fullmatch(r'motion-[0-9a-f]{12}', entry['id']) or entry['id'] in ids:
                raise ValueError('自定义表情编号无效')
            entry['name'] = self._name(entry['name'])
            if entry['name'] in names or entry['scene'] not in NAMES:
                raise ValueError('自定义表情名称重复或场景无效')
            entry['config'] = validate(entry['config'])
            ids.add(entry['id']); names.add(entry['name'])
        return record

    @staticmethod
    def _name(value):
        if type(value) is not str or not value.strip() or len(value.strip()) > 48 or any(not c.isprintable() for c in value):
            raise ValueError('表情名称须为 1–48 个可显示字符')
        return value.strip()

    def _read(self):
        if not self.path.exists() and not self.backup.exists():
            record = {'schema': 'gork-expression-library', 'version': 1, 'revision': 1, 'entries': []}
            self._atomic(self.path, record)
            return record
        return super()._read()

    def get(self, item_id):
        record = self.read()
        entry = next((v for v in record['entries'] if v['id'] == item_id), None)
        if entry is None:
            raise KeyError('自定义表情不存在')
        return {'revision': record['revision'], **deepcopy(entry)}

    def save_expression(self, name, scene, config, expected_revision, item_id=None):
        name, config = self._name(name), validate(config)
        if type(scene) is not str or scene not in NAMES:
            raise ValueError('请选择四个可编辑场景之一')
        with self.lock:
            previous = self._read()
            if type(expected_revision) is not int or expected_revision != previous['revision']:
                raise Conflict('表情库已在其他窗口更新，请重新读取后保存')
            entries = deepcopy(previous['entries'])
            index = next((i for i, v in enumerate(entries) if v['id'] == item_id), None)
            if item_id is not None and index is None:
                raise ValueError('只能修改已有自定义表情，不能修改内置表情')
            if any(v['name'] == name and v['id'] != item_id for v in entries):
                raise Conflict('已有同名自定义表情，请改名或从列表选择它再保存')
            if item_id is None and len(entries) >= 64:
                raise ValueError('自定义表情最多 64 个')
            entry = {'id': item_id or 'motion-' + uuid.uuid4().hex[:12], 'name': name, 'scene': scene, 'config': config}
            if index is None: entries.append(entry)
            else: entries[index] = entry
            record = {**previous, 'revision': previous['revision'] + 1, 'entries': entries}
            self._atomic(self.backup, previous)
            self._atomic(self.path, record)
            self.warning = ''
            return {**record, 'entry': deepcopy(entry), 'warning': ''}
