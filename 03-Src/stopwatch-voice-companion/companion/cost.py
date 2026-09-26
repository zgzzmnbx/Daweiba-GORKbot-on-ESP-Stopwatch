"""Read-only business adapter. No voice engine, BLE, database or model dependencies."""
import re
from urllib.parse import urlsplit

import httpx

from .voice import VoiceError


def fields(value, names):
    if not isinstance(value, dict):
        return {}
    return {key: value[key] for key in names if key in value and
            isinstance(value[key], (str, int, float, bool, type(None)))}


def records(data, key, names):
    values = data.get(key)
    if not isinstance(values, list) or any(not isinstance(item, dict) for item in values):
        raise VoiceError(502, 'COST_SCHEMA', '造价接口字段不兼容，请核对业务服务版本')
    return [fields(item, names) for item in values]


PROJECT_FIELDS = ('project_id', 'project_name', 'status', 'status_label', 'updated_at',
                  'lifecycle_stage', 'task_count', 'run_count')
SOURCE_FIELDS = ('id', 'source_file', 'source_type', 'title', 'title_path', 'authority_level', 'heading', 'snippet',
                 'library_name', 'page', 'line_start', 'line_end', 'score')
TASK_FIELDS = ('task_id', 'title', 'task_name', 'task_type', 'status', 'status_label', 'stage_label',
               'created_at', 'updated_at', 'progress')


class CostClient:
    def __init__(self, base_url='http://127.0.0.1:8000', transport=None):
        parsed = urlsplit(base_url)
        if (parsed.scheme != 'http' or parsed.hostname not in ('127.0.0.1', 'localhost')
                or parsed.username or parsed.password or parsed.query or parsed.fragment
                or parsed.path not in ('', '/')):
            raise ValueError('造价服务必须是本机 HTTP 地址，不允许路径或凭据')
        self.http = httpx.AsyncClient(base_url=base_url, transport=transport,
                                     timeout=60, trust_env=False, follow_redirects=False)

    async def close(self):
        await self.http.aclose()

    async def _request(self, method, path, **kwargs):
        try:
            response = await self.http.request(method, path, **kwargs)
            response.raise_for_status()
            value = response.json()
            if not isinstance(value, dict):
                raise ValueError('shape')
            return value
        except httpx.TimeoutException:
            raise VoiceError(504, 'COST_TIMEOUT', '造价服务查询超时；未自动重试') from None
        except httpx.HTTPStatusError as exc:
            code = exc.response.status_code
            raise VoiceError(502, 'COST_UPSTREAM', f'造价接口返回 HTTP {code}；请检查服务') from None
        except (httpx.RequestError, ValueError):
            raise VoiceError(503, 'COST_UNAVAILABLE', '造价服务不可用或响应格式不兼容') from None

    async def health(self):
        data = await self._request('GET', '/api/health', timeout=4)
        if data.get('service') != 'guankanzhisuan' or data.get('status') != 'ok':
            raise VoiceError(502, 'COST_IDENTITY', '此端口不是可用的造价智算服务')
        return fields(data, ('status', 'service', 'release_version', 'version'))

    async def projects(self, page=1):
        await self.health()
        data = await self._request('GET', '/api/projects', params={'page': page, 'page_size': 20})
        return {'items': records(data, 'items', PROJECT_FIELDS),
                'total': data.get('total', 0), 'page': page, 'page_size': 20}

    async def project(self, project_id):
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,100}', project_id):
            raise VoiceError(422, 'COST_PROJECT_ID', '项目 ID 格式不兼容')
        await self.health()
        data = await self._request('GET', f'/api/projects/{project_id}')
        tasks = await self._request('GET', f'/api/projects/{project_id}/tasks')
        return {'project': fields(data.get('project', data), PROJECT_FIELDS),
                'tasks': records(tasks, 'items', TASK_FIELDS)}

    async def query(self, question, allow_ai=False):
        question = question.strip()
        if not question or len(question) > 1000:
            raise VoiceError(422, 'COST_QUESTION', '请输入 1–1000 字的问题')
        await self.health()
        data = await self._request('POST', '/api/knowledge/ask' if allow_ai else '/api/knowledge/search',
                                   json={'question': question, 'retrieval_mode': 'classic',
                                         'force_knowledge': True, 'limit': 5})
        sources = records(data, 'sources' if allow_ai else 'results', SOURCE_FIELDS)
        mode = data.get('answer_mode', 'unknown') if allow_ai else 'local_search'
        return {'answer': str(data.get('answer', '')) if allow_ai else
                ('已检索到以下依据，请核对原文。' if sources else '未找到匹配依据，请调整问题。'),
                'sources': sources, 'evidence_found': data.get('evidence_found') is True,
                'answer_mode': mode, 'preset_answer': data.get('preset_answer') is True,
                'generated_by_model': data.get('generated_by_model', mode == 'model_answer'),
                'evidence_status': data.get('evidence_status', 'unknown'),
                'retrieval_mode': data.get('actual_retrieval_mode', data.get('retrieval_mode_used', 'unknown'))}
