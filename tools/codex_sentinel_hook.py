"""Advisory Codex hook: enqueue only lifecycle metadata, always exit silently."""
import json
import os
from pathlib import Path
import sys
import time
import uuid
from datetime import datetime, timezone


PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / '03-Src' / 'stopwatch-voice-companion'))


def main():
    try:
        from companion.codex_source import normalize_hook
        queue = Path(os.environ.get('GORK_CODEX_HOOK_QUEUE') or PROJECT / 'Codex-Temp' / 'codex-sentinel-hook-queue')
        marker = queue / 'enabled.json'
        if not marker.is_file():
            return
        lease = json.loads(marker.read_text(encoding='utf-8'))
        if not isinstance(lease.get('expires_at'), (int, float)) or lease['expires_at'] < time.time():
            return
        if sum(1 for _ in queue.glob('*.json')) >= 201:
            return
        raw = sys.stdin.buffer.read(1048577)
        if len(raw) > 1048576:
            return
        item = json.loads(raw)
        event = normalize_hook(item)
        if not event:
            return
        name = uuid.uuid4().hex
        temporary = queue / (name + '.tmp')
        stored = {'hook_event_name': item['hook_event_name'], 'session_id': item['session_id'],
                  'turn_id': item.get('turn_id', ''),
                  'timestamp': datetime.now(timezone.utc).isoformat(),
                  'event_id': uuid.uuid4().hex, 'stop_hook_active': bool(item.get('stop_hook_active'))}
        temporary.write_text(json.dumps(stored, separators=(',', ':')), encoding='utf-8')
        temporary.replace(queue / (name + '.json'))
    except Exception:
        pass  # Observability failure never alters Codex execution.


if __name__ == '__main__':
    main()
