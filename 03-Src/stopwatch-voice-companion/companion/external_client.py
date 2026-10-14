"""Dependency-free Gork output client. Never controls microphones or business tasks."""
from datetime import datetime, timezone
import json
from pathlib import Path
import uuid
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from urllib.parse import urlsplit, quote


class GorkError(RuntimeError):
    def __init__(self, status, code):
        self.status, self.code = status, code
        super().__init__(f'Gork HTTP {status}: {code}')


class GorkClient:
    def __init__(self, token_file, base_url='http://127.0.0.1:8766', timeout=3):
        parsed=urlsplit(base_url)
        if parsed.scheme!='http' or parsed.hostname not in ('127.0.0.1','localhost') or parsed.path not in ('','/') or parsed.username or parsed.query or parsed.fragment:
            raise ValueError('Gork supports local loopback HTTP only')
        value=json.loads(Path(token_file).read_text(encoding='utf-8'))
        self.source,self._token=value['source'],value['token']
        self.base_url=base_url.rstrip('/');self.timeout=timeout

    def _request(self, method, path, data=None):
        body=None if data is None else json.dumps(data,ensure_ascii=False).encode('utf-8')
        request=Request(self.base_url+'/api/external'+path,body,method=method,
                        headers={'Authorization':'Bearer '+self._token,'Content-Type':'application/json'})
        try:
            with urlopen(request,timeout=self.timeout) as response:return json.load(response)
        except HTTPError as exc:
            try:code=json.load(exc).get('error',{}).get('code','HTTP_ERROR')
            except (ValueError,AttributeError):code='HTTP_ERROR'
            raise GorkError(exc.code,code) from None  # never expose server payload or credentials

    def capabilities(self):return self._request('GET','/capabilities')
    def status(self):return self._request('GET','/status')
    def send(self, payload):
        if payload.get('source')!=self.source:raise ValueError('payload source does not match token')
        return self._request('POST','/notifications',payload)
    def receipt(self,event_id):return self._request('GET','/notifications/'+quote(event_id,safe=''))
    def cancel_event(self,event_id):return self._request('DELETE','/notifications/'+quote(event_id,safe=''))
    def cancel_task(self,task_id,attempt):return self._request('POST','/cancel',{'task_id':task_id,'attempt':attempt})
    def heartbeat(self,event_id,task_id,attempt):return self._request('POST','/heartbeat',dict(event_id=event_id,task_id=task_id,attempt=attempt))
    def event(self, *, task_id, attempt, stage, sequence, **output):
        """Build once, retain this exact dict for retry. Producer persists sequence."""
        return dict(protocol_version='1.0',source=self.source,event_id=uuid.uuid4().hex,
                    task_id=task_id,attempt=attempt,stage=stage,sequence=sequence,
                    occurred_at=datetime.now(timezone.utc).isoformat(),**output)
