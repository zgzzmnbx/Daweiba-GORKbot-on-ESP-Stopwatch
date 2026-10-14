"""Windows user-scoped DPAPI secrets. Public snapshots never include ciphertext
or credentials. No global settings, key files or plaintext recovery copies.
"""
from pathlib import Path
import base64
import ctypes
from ctypes import wintypes
import json
import os
import uuid
import shutil

class Blob(ctypes.Structure):
    _fields_=[('size',wintypes.DWORD),('data',ctypes.POINTER(ctypes.c_ubyte))]

def protect(data:bytes,decode=False):
    if os.name!='nt':raise RuntimeError('此本机配置使用 Windows DPAPI，需要 Windows 当前用户')
    buffer=ctypes.create_string_buffer(data);source=Blob(len(data),ctypes.cast(buffer,ctypes.POINTER(ctypes.c_ubyte)));target=Blob()
    api=ctypes.WinDLL('crypt32',use_last_error=True)
    fn=api.CryptUnprotectData if decode else api.CryptProtectData
    fn.argtypes=[ctypes.POINTER(Blob),ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p,wintypes.DWORD,ctypes.POINTER(Blob)]
    fn.restype=wintypes.BOOL
    if not fn(ctypes.byref(source),None,None,None,None,1,ctypes.byref(target)):
        raise RuntimeError('本机凭据保护失败')
    try:return ctypes.string_at(target.data,target.size)
    finally:
        ctypes.memset(target.data,0,target.size)
        kernel=ctypes.WinDLL('kernel32');kernel.LocalFree.argtypes=[ctypes.c_void_p];kernel.LocalFree(target.data)

class NetworkStore:
    def __init__(self,path):self.path=Path(path);self.revision=0;self.secret=None;self.policy='auto_wifi_first';self.power='auto';self.address='';self.error=''
    def load(self):
        if not self.path.exists():return
        try:
            value=json.loads(self.path.read_text(encoding='utf-8'))
            secret=json.loads(protect(base64.b64decode(value['protected'],validate=True),True))
            if len(bytes.fromhex(secret['key']))!=32 or len(secret['identity'])!=16:raise ValueError()
            self.secret=secret;self.revision=value['revision'];self.policy=value['policy'];self.power=value['power'];self.address=value.get('address','')
            if self.policy not in ('auto_wifi_first','ble_only','wifi_only') or self.power not in ('auto','performance','eco'):raise ValueError()
        except Exception:
            self.secret=None;self.policy='auto_wifi_first';self.power='auto';self.address='';self.error='本机配网配置损坏或无法解密，请重新配网；原文件已保留'
    def write(self,secret,policy,power,address='',expected=None):
        if expected is not None and expected!=self.revision:raise ValueError('配置已变更，请刷新后重试')
        encrypted=base64.b64encode(protect(json.dumps(secret).encode())).decode()
        result=dict(version=1,revision=self.revision+1,protected=encrypted,policy=policy,power=power,address=address)
        self.path.parent.mkdir(parents=True,exist_ok=True)
        temp=self.path.with_name(self.path.name+'.'+uuid.uuid4().hex+'.tmp')
        try:
            temp.write_text(json.dumps(result),encoding='utf-8')
            if self.path.exists():shutil.copy2(self.path,self.path.with_name(self.path.name+'.bak'))
            os.replace(temp,self.path)
        finally:
            if temp.exists():temp.unlink()
        self.secret=secret;self.revision+=1;self.policy=policy;self.power=power;self.address=address;self.error=''
