"""Shared-schema, persistence, conflict and bounded Watch conversion acceptance."""
from copy import deepcopy
import json
from pathlib import Path
import sys

import httpx
import pytest

from companion.motion import ASSETS, MotionStore, MotionLibrary, Conflict, validate, parse
from companion.app import create_app

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'tools'))
from convert_gork_motion import convert, cpp
from export_watch_expressions import export
from companion.motion import watch_token
from stopwatch_ble import normalize_command, BleConsoleError


@pytest.fixture
def user():
    return json.loads((ASSETS / 'initial-config.gork.json').read_text(encoding='utf-8'))


def test_user_config_exact_and_all_ranges(user):
    assert validate(user) == user
    specs = json.loads((ASSETS / 'field-specs.json').read_text(encoding='utf-8'))
    for name, scene in user['scenes'].items():
        for group, fields in scene.items():
            for key, value in fields.items():
                meta = specs[group][key]
                for bound in (meta[1:] if isinstance(meta[1], list) else (meta[1], meta[2])):
                    if isinstance(bound,list):
                        continue
                    c = deepcopy(user)
                    c['scenes'][name][group][key] = bound
                    validate(c)
                for bad in ([False, None, '1', float('nan'), float('inf'), 10**1000, meta[1]-1, meta[2]+1]
                            if not isinstance(meta[1],list) else ['unknown',0,None]):
                    c=deepcopy(user);c['scenes'][name][group][key]=bad
                    with pytest.raises(ValueError):
                        validate(c)
    for place in [user,user['scenes'],user['scenes']['idle'],user['scenes']['idle']['eyes']]:
        place['unknown']=1
        with pytest.raises(ValueError):
            validate(user)
        del place['unknown']


def test_versions_and_size(user):
    for bad in (0,3,True,'2'):
        c=deepcopy(user);c['version']=bad
        with pytest.raises(ValueError):validate(c)
    legacy=deepcopy(user);legacy['version']=1;w=legacy['scenes']['writing']['writing']
    del w['penStyle'];del w['strokeWidth'];w['handScale']=1
    result=validate(legacy)
    assert result['version']==2 and result['scenes']['writing']['writing']['penStyle']=='quill'
    assert result['scenes']['question']==user['scenes']['question']
    with pytest.raises(ValueError):parse(' '*20481)
    with pytest.raises(ValueError):parse('{"schema":"x","schema":"y"}')


@pytest.mark.parametrize('bound', [1, 2])
def test_extended_writing_saved_reload_and_watch_export(tmp_path, user, bound):
    config = deepcopy(user)
    specs = json.loads((ASSETS / 'field-specs.json').read_text(encoding='utf-8'))
    keys = ('x', 'y', 'scale', 'penScale', 'strokeWidth')
    for key in keys:
        config['scenes']['writing']['writing'][key] = specs['writing'][key][bound]
    app = create_app({'motion_state_path': tmp_path/'motion.json', 'motion_library_path': tmp_path/'library.json',
                      'auto_connect_device': False, 'auto_connect_voice': False})
    import asyncio
    async def run():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://127.0.0.1:8766') as client:
            response = await client.post('/api/motion/expressions', json={'expected_revision': 1, 'name': '扩展书写', 'scene': 'writing', 'config': config})
            assert response.status_code == 200, response.text
            entry = response.json()['entry']
            assert entry['config'] == config
            assert MotionLibrary(tmp_path/'library.json').get(entry['id'])['config'] == config
            exported = await client.get('/api/motion/watch/json', params={'expression_id': entry['id']})
            assert exported.status_code == 200
            assert exported.json()['scenes'][2]['props'][:5] == [specs['writing'][key][bound] for key in keys]
            header = await client.get('/api/motion/watch/header', params={'expression_id': entry['id']})
            assert header.status_code == 200 and 'constexpr MotionParams maximum[4]' in header.text
            # Export includes extended bounds, without rewriting the firmware candidate.
            assert '160.0f,200.0f,2.5f,3.0f,12.0f,3.0f' in header.text
    asyncio.run(run())


def test_atomic_save_restart_conflict_write_failure_and_recovery(tmp_path,user,monkeypatch):
    path=tmp_path/'motion.local.json';store=MotionStore(path)
    assert store.read()['config']==user
    changed=deepcopy(user);changed['scenes']['loading']['loading']['scale']=1.25
    assert store.save(changed,1)['revision']==2
    assert MotionStore(path).read()['config']==changed
    with pytest.raises(Conflict):store.save(user,1)
    before=path.read_bytes()
    import companion.motion as motion
    real=motion.os.replace
    def fail_primary(src,dest):
        if Path(dest)==path:raise OSError('disk full')
        return real(src,dest)
    monkeypatch.setattr(motion.os,'replace',fail_primary)
    with pytest.raises(OSError):store.save(user,2)
    assert path.read_bytes()==before and not list(tmp_path.glob('*.tmp'))
    monkeypatch.setattr(motion.os,'replace',real)
    path.write_text('broken',encoding='utf-8')
    recovered=MotionStore(path).read()
    assert recovered['config']==changed and recovered['warning']
    assert path.read_text()=='broken'
    store.backup.write_text('broken',encoding='utf-8')
    with pytest.raises(ValueError,match='均不可读'):MotionStore(path).read()
    restored=MotionStore(path).recover(user)
    assert restored['config']==user and restored['revision']>2
    assert len(list(tmp_path.glob('*.corrupt-*')))==2
    assert MotionStore(path).read()['config']==user
    with pytest.raises(Conflict):MotionStore(path).recover(changed)


def test_watch_fields_geometry_pen_styles_versions_and_determinism(user):
    result=convert(user,7);assert result==convert(user,7)
    assert result['geometry']['center']==[233,233] and result['geometry']['bodyRadius']==216
    assert result['version']==1 and result['sourceVersion']==2 and result['revision']==7
    specs=json.loads((ASSETS/'field-specs.json').read_text(encoding='utf-8'))
    for mapped in result['scenes']:
        source=user['scenes'][mapped['name']]
        for group in ('eyes','motion'):
            assert mapped[group]==[source[group][key] for key in specs[group]]
        if mapped['name']!='idle':
            values=list(source[mapped['name']].values())
            if mapped['name']=='writing':values[-1]=0
            assert mapped['props'][:len(values)]==values
    for i,pen in enumerate(('quill','nib','pencil','brush')):
        c=deepcopy(user);c['scenes']['writing']['writing']['penStyle']=pen
        assert convert(c)['scenes'][2]['props'][5]==i
    assert '34.0f,140.0f,1.15f,1.25f,5.0f,0.0f' in cpp(result)
    for rev in (0,-1,True,2**32):
        with pytest.raises(ValueError):convert(user,rev)


def test_named_watch_snapshot_independent_parameters_and_stale_tokens(tmp_path,user):
    lib=MotionLibrary(tmp_path/'library.json')
    entries=[]
    for i,scene in enumerate(('loading','question','writing')):
        config=deepcopy(user)
        config['scenes'][scene]['motion']['speed']=0.75+i*0.5
        entries.append(lib.save_expression('自定义'+str(i),scene,config,i+1)['entry'])
    record=lib.read()
    code,manifest=export(record)
    assert manifest['revision']==4 and len(manifest['entries'])==3
    assert len({e['token'] for e in manifest['entries']})==3
    for entry,saved in zip(entries,manifest['entries']):
        assert saved['config']==entry['config'] and saved['token']==watch_token(entry)
        token=saved['token']
        assert len(token)==14 and token.isalpha() and token.islower()
        assert normalize_command('loop '+token)=='loop '+token
        assert normalize_command('once '+token)=='once '+token
        assert token in code and entry['name'] in code
    changed=deepcopy(entries[0]);changed['config']['scenes']['loading']['loading']['scale']=1.13
    assert watch_token(changed)!=watch_token(entries[0])
    renamed=deepcopy(entries[0]);renamed['name']='新名字'
    assert watch_token(renamed)!=watch_token(entries[0])
    with pytest.raises(BleConsoleError):normalize_command('loop cx123456789abc')
    with pytest.raises(BleConsoleError):normalize_command('pingpong '+manifest['entries'][0]['token'])


@pytest.mark.anyio
async def test_custom_expression_routes_exact_snapshot_to_watch(tmp_path,user,monkeypatch):
    app=create_app({'motion_state_path':tmp_path/'motion.json','motion_library_path':tmp_path/'library.json','auto_connect_device':False,'auto_connect_voice':False})
    entry=app.state.motion_library.save_expression('我的书写','writing',user,1)['entry']
    control=app.state.control
    await control.acquire_workspace('test-watch',False)
    sent=[]
    class Writer:
        connected=True
        async def send_command(self,command):
            sent.append(command);return 'OK:APPLIED'
    monkeypatch.setattr(control.robot,'device_client',lambda:Writer())
    control.robot.enabled=True
    result=await control.play_character('test-watch',entry['id'],'loop','both',entry)
    assert result['watch']['accepted'] and result['desktop']['accepted']
    assert sent==['loop '+watch_token(entry)]
    assert control.character['custom_motion']==entry


@pytest.mark.anyio
async def test_http_save_validation_conflict_stream_limit_and_host(tmp_path,user):
    app=create_app({'motion_state_path':tmp_path/'motion.json','motion_library_path':tmp_path/'library.json','auto_connect_device':False,'auto_connect_voice':False})
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://127.0.0.1:8766') as c:
        r=await c.get('/api/motion/config');assert r.json()['config']==user
        before=(tmp_path/'motion.json').read_bytes()
        assert (await c.put('/api/motion/config',json={'config':user,'expected_revision':1})).status_code==409
        state=(await c.get('/api/desktop/state')).json()['character']
        assert (await c.get('/api/motion/expressions')).json()['entries']==[]
        body={'name':'我的书写','scene':'writing','config':user,'expected_revision':1}
        r=await c.post('/api/motion/expressions',json=body);assert r.status_code==200
        item=r.json()['entry'];assert item['name']=='我的书写'
        assert (await c.get('/api/desktop/state')).json()['character']==state
        assert (tmp_path/'motion.json').read_bytes()==before
        assert (await c.post('/api/motion/expressions',json=body)).status_code==409
        assert (await c.put('/api/motion/expressions/idle',json={**body,'expected_revision':2})).status_code==422
        assert (await c.post('/api/motion/expressions',json={**body,'config':{},'expected_revision':2})).status_code==422
        async def chunks():yield b' ' * 24577
        assert (await c.post('/api/motion/expressions',content=chunks())).status_code==413
        assert (await c.put('/api/motion/config',headers={'Origin':'https://example.com'},json={})).status_code==403
        watch=await c.get('/api/motion/watch/json',params={'expression_id':item['id']})
        assert watch.status_code==200 and watch.json()['revision']==2
        assert (await c.get('/api/motion/watch/header',params={'expression_id':item['id']})).text.startswith('// Generated')
        assert (await c.post('/api/motion/config/recover',json={'config':user})).status_code==409
        assert 'frame-ancestors \'self\'' in (await c.get('/static/motion/index.html')).headers['content-security-policy']
        assert 'frame-ancestors \'none\'' in (await c.get('/')).headers['content-security-policy']


def test_named_library_update_preserves_other_entries_and_failed_write(tmp_path,user,monkeypatch):
    lib=MotionLibrary(tmp_path/'library.json')
    one=lib.save_expression('书写一','writing',user,1)['entry']
    two=lib.save_expression('疑惑二','question',user,2)['entry']
    changed=deepcopy(user);changed['scenes']['writing']['writing']['strokeWidth']=2
    lib.save_expression('书写修改','writing',changed,3,one['id'])
    assert MotionLibrary(lib.path).get(one['id'])['config']==changed
    assert lib.get(two['id'])['config']==user
    with pytest.raises(Conflict):lib.save_expression('疑惑二','writing',changed,4,one['id'])
    with pytest.raises(ValueError):lib.save_expression('默认','idle',changed,4,'idle')
    before=lib.path.read_bytes()
    monkeypatch.setattr(lib,'_atomic',lambda *args:(_ for _ in ()).throw(OSError('disk full')))
    with pytest.raises(OSError):lib.save_expression('新建','idle',user,4)
    assert lib.path.read_bytes()==before


@pytest.mark.anyio
async def test_saved_edit_does_not_change_active_custom_snapshot(tmp_path,user):
    app=create_app({'motion_state_path':tmp_path/'motion.json','motion_library_path':tmp_path/'library.json','auto_connect_device':False,'auto_connect_voice':False})
    lib=app.state.motion_library
    entry=lib.save_expression('正在播放','writing',user,1)['entry']
    control=app.state.control
    await control.acquire_workspace('library-test',False)
    await control.play_character('library-test',entry['id'],'loop','desktop',lib.get(entry['id']))
    before=deepcopy(control.character)
    changed=deepcopy(user);changed['scenes']['writing']['writing']['x']=-30
    lib.save_expression('正在播放','writing',changed,2,entry['id'])
    assert control.character==before
    assert control.character['custom_motion']['config']==user
    result=await control.play_character('library-test',entry['id'],'once','watch',lib.get(entry['id']))
    assert not result['watch']['accepted'] and '固件' in result['watch']['error']
    assert control.character==before
