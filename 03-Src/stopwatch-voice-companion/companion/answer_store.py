"""Explicit local DeepSeek setup; credential protected by Windows user DPAPI."""
import base64
import json
from pathlib import Path
from .network_store import protect
from .answer import DEFAULT_PROMPT, DEFAULT_MAX_CHARS, system_message

BASE_URL = 'https://api.deepseek.com'
MODELS = ('deepseek-flash', 'deepseek-v4-pro')

class AnswerStore:
    def __init__(self, path):
        self.path=Path(path);self.key='';self.model=MODELS[0];self.error=''
        self.system_prompt=DEFAULT_PROMPT;self.max_chars=DEFAULT_MAX_CHARS
        self.revision=0
        if self.path.exists():
            try:
                value=json.loads(protect(base64.b64decode(self.path.read_bytes(),validate=True),True))
                self._validate(value['key'],value['model'])
                prompt=value.get('system_prompt',DEFAULT_PROMPT);limit=value.get('max_chars',DEFAULT_MAX_CHARS)
                self._validate_prompt(prompt,limit)
                revision=value.get('revision',0)
                if type(revision) is not int or revision<0:raise ValueError('Invalid revision')
                self.key=value['key'];self.model=value['model']
                self.system_prompt=prompt;self.max_chars=limit
                self.revision=revision
            except Exception:self.error='本机 AI 配置无法读取，请重新输入 API Key 并保存。'

    @staticmethod
    def _validate(key,model):
        if model not in MODELS:raise ValueError('请选择支持的 DeepSeek 模型')
        if not 8<=len(key)<=256 or any(c.isspace() or ord(c)<33 or ord(c)>126 for c in key):
            raise ValueError('请输入有效的 API Key')

    @staticmethod
    def _validate_prompt(prompt,limit):
        if not isinstance(prompt,str) or not prompt.strip() or len(prompt)>2000:
            raise ValueError('提示词不能为空且最多2000字')
        if type(limit) is not int or not 5<=limit<=300:
            raise ValueError('回答目标字数须为5到300')

    def save(self,key,model,system_prompt=None,max_chars=None):
        key=key.strip() or self.key
        prompt=self.system_prompt if system_prompt is None else system_prompt.strip()
        limit=self.max_chars if max_chars is None else max_chars
        self._validate(key,model)
        self._validate_prompt(prompt,limit)
        revision=self.revision+1
        data=base64.b64encode(protect(json.dumps(dict(key=key,model=model,system_prompt=prompt,max_chars=limit,revision=revision)).encode()))
        self.path.parent.mkdir(parents=True,exist_ok=True)
        temp=self.path.with_name(self.path.name+'.tmp')
        temp.write_bytes(data);temp.replace(self.path)
        self.key=key;self.model=model;self.error=''
        self.system_prompt=prompt;self.max_chars=limit
        self.revision=revision

    def snapshot(self):
        return dict(provider='DeepSeek',model=self.model,key_saved=bool(self.key),error=self.error,
            prompt_configurable=True,revision=self.revision,system_prompt=self.system_prompt,max_chars=self.max_chars,
            default_prompt=DEFAULT_PROMPT,default_max_chars=DEFAULT_MAX_CHARS,
            effective_prompt=system_message(self.system_prompt,self.max_chars),
            watch_prompt=system_message(self.system_prompt,self.max_chars,short=True))
