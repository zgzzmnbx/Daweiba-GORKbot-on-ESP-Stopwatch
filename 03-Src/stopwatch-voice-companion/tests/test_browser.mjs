import test from 'node:test';
import assert from 'node:assert/strict';
import {toPCM16, Epoch} from '../static/pcm.js';
import fs from 'node:fs';
import vm from 'node:vm';
import {webcrypto} from 'node:crypto';
import {createDebugConsole} from '../static/debug-console.js';
import {createExpressionMenu} from '../static/expression-menu.js';
import {createAppearancePicker} from '../static/appearance-picker.js';
import {createWatchChat} from '../static/watch-chat.js';
import {createNoticeChat} from '../static/notice-chat.js';
const catalogScope = {window:{}};
vm.runInNewContext(fs.readFileSync(new URL('../static/gork-catalog.js',import.meta.url),'utf8'),catalogScope);

test('48k stereo-downmixed floats become real 16k mono PCM WAV', () => {
  const wav = toPCM16([new Float32Array(4800).fill(.5)], 48000), view = new DataView(wav);
  assert.equal(wav.byteLength, 44 + 3200);
  assert.equal(view.getUint32(24, true), 16000);
  assert.equal(view.getUint16(22, true), 1);
  assert.equal(view.getUint16(34, true), 16);
  assert.equal(view.getInt16(44, true), 16384);
});
test('sample saturation and 30-second maximum', () => {
  const view = new DataView(toPCM16([Float32Array.of(2, -2)], 16000));
  assert.equal(view.getInt16(44, true),32767); assert.equal(view.getInt16(46,true),-32768);
  assert.equal(toPCM16([new Float32Array(16000*31)],16000).byteLength,960044);
});
test('20 intermediate stops invalidate old playback/HTTP generations', () => {
  const epoch = new Epoch();
  for (let i=0; i<20; i++) {
    const old = epoch.next(), oldSignal = epoch.abort.signal;
    epoch.next(); assert.equal(epoch.valid(old), false); assert.equal(oldSignal.aborted, true);
  }
});

function workbench(saved = {}, uiOptions = {}) {
  const elements = new Map(), waiting = [], played = [], requests = [], events = {}, avatarStates = [], previewMounts = [];
  let sentinel = uiOptions.sentinel || {enabled:true,mode:'auto',task_id:'',target:'desktop',sound:false,sound_target:'pc',current:null,last_result:null,last_success_at:'',connection_error:'',history:[],presentation:null};
  const nodes = name => ({nodeName:name, children:[], dataset:{}, listeners:{}, hidden:false,
    attrs:{},classList:{toggle(){}},setAttribute(k,v){this.attrs[k]=v;},getAttribute(k){return this.attrs[k];},removeAttribute(k){delete this.attrs[k];},focus(){this.focused=true;},remove(){this.removed=true;},
    append(...items){this.children.push(...items);},replaceChildren(...items){this.children=items;this.options=[];this.value='';},
    addEventListener(type,fn){(this.listeners[type] ||= []).push(fn);},
    async keydown(event){for(const fn of this.listeners.keydown || []) await fn(event);}});
  const element = id => {
    if (!elements.has(id)) elements.set(id, {...nodes('div'),value:id==='asr'?'local':id==='interaction-mode'?'read':'',textContent:'',checked:false,options:[],
      async change(){for(const fn of this.listeners.change || []) await fn(); if(this.onchange) await this.onchange();},
      add(option){this.options.push(option);if(this.options.length===1)this.value=option.value;},getTracks(){return [];}});
    return elements.get(id);
  };
  const pages = ['dialogue','cost','character','watch','settings','logs'].map(page=>Object.assign(nodes('section'),{dataset:{page}}));
  const tabs = ['dialogue','cost','character','watch','settings','logs'].map(page=>Object.assign(nodes('a'),{dataset:{pageLink:page}}));
  const location = {hash:uiOptions.hash || '#dialogue'};
  const desktop = uiOptions.desktop;
  class AudioContext {
    constructor(){this.state='running';}
    async resume(){} async suspend(){} async close(){this.state='closed';}
    async decodeAudioData(){return {};}
    createGain(){return {gain:{value:1},connect(){}};}
    createBufferSource(){const player={stopped:false,connect(){},disconnect(){},start(){played.push(this);},stop(){this.stopped=true;}};return player;}
  }
  const context = vm.createContext({
    toPCM16,Epoch,AbortController,AbortSignal,DOMException,ArrayBuffer,TextEncoder,performance,AudioContext,createDebugConsole,createExpressionMenu,createAppearancePicker,createWatchChat,createNoticeChat,
    Recorder:class{async start(){requests.push({url:'recorder:start'});return true;}finish(){return new ArrayBuffer(44);}stop(){}},
    WavPlayer:class{constructor(){this.playing=false;}async play(_bytes,onended){this.playing=true;this.onended=onended;return true;}stop(){this.playing=false;}},
    Option:class{constructor(label,value){this.label=label;this.value=value;}},
    crypto:webcrypto,location,history:{replaceState(_a,_b,hash){location.hash=hash;}},
    document:{getElementById:element,createElement:nodes,querySelectorAll:selector=>selector==='[data-page]'?pages:selector==='[data-page-link]'?tabs:[],body:{dataset:{}}},
    window:{GorkCatalog:catalogScope.window.GorkCatalog,GorkAvatar:{mount(_canvas,_catalog,options){const mount={options,disposed:false};previewMounts.push(mount);return {set:state=>avatarStates.push(state),playCustom:(entry,opts)=>avatarStates.push({custom:entry.id,...opts}),dispose(){mount.disposed=true;}};}},gorkDesktop:desktop,
      addEventListener(name,fn){events[name]=fn;},localStorage:{getItem:key=>saved[key]??null,setItem:(key,value)=>{if(uiOptions.storageWritesFail)throw new Error('Storage quota exceeded');saved[key]=value;}}},
    setInterval:()=>0,clearInterval(){},clearTimeout,setTimeout,console,
    async fetch(url, options={}){
      requests.push({url,body:options.body,headers:options.headers});
      const injected = await uiOptions.onRequest?.(url,options);
      if(injected) return injected;
      if(url==='/api/motion/expressions')return {ok:true,json:async()=>({revision:1,entries:uiOptions.customEntries||[]})};
      if(url==='/api/workspace' && uiOptions.workspaceBusy) return {ok:false,status:409,json:async()=>({error:{code:'WORKSPACE_BUSY',message:'工作台已占用'}})};
      if(url==='/api/character' && options.method==='POST') {
        const {target}=JSON.parse(options.body);
        const result={desktop:{requested:target!=='watch',accepted:target!=='watch'},watch:{requested:target!=='desktop',accepted:target!=='desktop'&&!uiOptions.watchError,error:uiOptions.watchError,receipt:'OK:EXPR'}};
        if(uiOptions.delayExpression) return await new Promise(resolve=>waiting.push(()=>resolve({ok:true,json:async()=>result})));
        return {ok:true,json:async()=>result};
      }
      if (url === '/api/cost/query') {
        const result = {answer:'完整业务回答',sources:[{source_file:'规则.md',snippet:'<script>仅作文本</script>'}],evidence_found:true,answer_mode:'curated_demo',preset_answer:true};
        if (uiOptions.delayCost) return await new Promise(resolve => waiting.push(() => resolve({ok:true,json:async()=>result})));
        return {ok:true,json:async()=>result};
      }
      if (url === '/api/cost/sentinel') {
        if (options.method === 'PUT') sentinel = {...sentinel,...JSON.parse(options.body)};
        return {ok:true,json:async()=>sentinel};
      }
      if (url.startsWith('/api/cost/sentinel/projects') && uiOptions.sentinelProjects) {
        const source = new URL(url, 'http://localhost').searchParams.get('source');
        const result = {items:[{project_id:source,project_name:source}],total:1};
        if (uiOptions.delaySentinelProjects) return await new Promise(resolve=>waiting.push(()=>resolve({ok:true,json:async()=>result})));
        return {ok:true,json:async()=>result};
      }
      if (url === '/api/character/voice-library' && uiOptions.voiceLibrary)
        return {ok:true,json:async()=>uiOptions.voiceLibrary};
      if (url === '/api/character/voice-library/generate' && uiOptions.voiceLibrary) {
        uiOptions.voiceLibrary = {...uiOptions.voiceLibrary,ready:1,items:uiOptions.voiceLibrary.items.map(item=>({...item,ready:true}))};
        return {ok:true,json:async()=>({generated:['conversion_start'],library:uiOptions.voiceLibrary})};
      }
      if (url === '/api/character/voice-library/conversion_start/preview')
        return {ok:true,arrayBuffer:async()=>new ArrayBuffer(44)};
      if (url === '/api/device/audio/speech' && uiOptions.oldBackend)
        return {ok:false,status:404,json:async()=>({})};
      if(url==='/api/tts') return await new Promise(resolve=>waiting.push(()=>resolve({ok:true,arrayBuffer:async()=>new ArrayBuffer(44)})));
      return {ok:true,json:async()=>url==='/api/health'?(uiOptions.healthResponses?.length ? uiOptions.healthResponses.shift() : {version:uiOptions.healthVersion || '9.8.7-test',auto_connect_voice:uiOptions.autoConnectVoice === true,watch_speech_sync:uiOptions.oldBackend !== true,answer_speech_continuity:uiOptions.answerSpeechContinuity!==false,voice:{ready:true},voice_url:'local',robot:{connected:uiOptions.robotConnected === true},answer:{enabled:true},
        capabilities:{protocol_version:1,tts:{speakers:[{id:3,label:'local 3'},{id:58,label:'local 58'}]},
          cloud:{request_voice:true,voices:[{id:'Cherry',label:'Cherry'},{id:'Ethan',label:'Ethan'}]}}}):url==='/api/answer'?(uiOptions.answerResult||{text:'单独的回答'}):
        url==='/api/state'&&uiOptions.stateResult?uiOptions.stateResult:
        url==='/api/character/bubble'?{desktop:{requested:true,accepted:true},watch:{requested:true,accepted:true,receipt:'OK:TEXT'}}:
        ['/api/device/audio/speech','/api/device/audio/play'].includes(url)?{job_id:'test-job'}:
        url==='/api/device/audio'?(uiOptions.audioResult || {job_id:'test-job',running:false,stage:'played',bytes:44,total:44}):{generation:0,robot:{}}};
    }
  });
  const script = fs.readFileSync(new URL('../static/app.js', import.meta.url),'utf8').replace(/^import .*;\r?\n/gm, '');
  vm.runInContext(script,context);
  return {element,waiting,played,requests,pages,tabs,location,events,avatarStates,saved,previewMounts,context};
}
const settle = () => new Promise(resolve=>setImmediate(resolve));

test('Codex status follows backend startup and manual off without enabling during refresh', async()=>{
  let enabled=true;
  const ui=workbench({}, {onRequest:async url=>url==='/api/codex/sentinel' ? {ok:true,json:async()=>({enabled,mode:'auto',target:'desktop',sound:false,sound_target:'pc',threshold:20,threads:[],history:[],quota:{buckets:{}}})}:null});
  await settle();
  await vm.runInContext('refreshCodex()',ui.context);
  assert.equal(ui.element('codex-enable').checked,true);
  enabled=false;
  for(let i=0;i<2;i++) await vm.runInContext('refreshCodex()',ui.context);
  assert.equal(ui.element('codex-enable').checked,false);
  assert.match(ui.element('codex-status').textContent,/下次启动默认开启/);
  assert.equal(ui.requests.filter(r=>r.url==='/api/codex/sentinel'&&r.body).length,0);
});

test('header follows the selected Watch route through switching and disconnects', async()=>{
  const ui=workbench();await settle();
  for(const [robot,text,state] of [
    [{connected:true,network:{route:'ble',ble_connected:true,wifi_connected:true,policy:'auto_wifi_first'}},'Watch：蓝牙已连接','ready'],
    [{connected:true,network:{route:'wifi',ble_connected:true,wifi_connected:true,policy:'auto_wifi_first'}},'Watch：Wi-Fi 已连接','ready'],
    [{connected:false,network:{route:'wifi',ble_connected:true,wifi_connected:false}},'Watch：未连接','offline'],
    [{connected:true,network:{route:'ble',ble_connected:true,wifi_connected:false}},'Watch：蓝牙已连接','ready'],
    [{connected:true},'Watch：已连接','ready'],
    [{connected:true,network:{route:'offline',ble_connected:true}},'Watch：已连接','ready'],
  ]) {
    vm.runInContext(`paintRobot(${JSON.stringify(robot)})`,ui.context);
    assert.equal(ui.element('global-watch').textContent,text);
    assert.equal(ui.element('global-watch').dataset.state,state);
  }
});

test('answer writing replaces manual preview and restores the original avatar afterwards',async()=>{
  const entry={id:'motion-000000000001',name:'我的书写',scene:'writing',config:{}};
  const base={version:'fixture',auto_connect_voice:false,voice:{ready:true},robot:{connected:true},answer:{enabled:true}};
  const ui=workbench({}, {healthResponses:[base,{...base,answer_expression:entry},base]});await settle();
  vm.runInContext("manualPreview=true;",ui.context);
  await vm.runInContext('refresh()',ui.context);
  assert.equal(ui.avatarStates.at(-1).custom,entry.id);assert.equal(ui.avatarStates.at(-1).mode,'loop');
  const before=ui.avatarStates.length;
  await vm.runInContext('refresh()',ui.context);
  assert.equal(ui.avatarStates.length,before+1);assert.equal(typeof ui.avatarStates.at(-1),'string');
});

test('record and spoken-answer custom snapshots override preview and restore after the interaction',async()=>{
  const question={id:'motion-000000000002',name:'我的疑惑',scene:'question',config:{saved:true}};
  const writing={id:'motion-000000000001',name:'我的书写',scene:'writing',config:{saved:true}};
  const base={version:'fixture',auto_connect_voice:false,voice:{ready:true},robot:{connected:true},answer:{enabled:true}};
  const ui=workbench({}, {healthResponses:[base,{...base,interaction_expression:question},{...base,interaction_expression:writing},base]});await settle();
  vm.runInContext('manualPreview=true;',ui.context);
  await vm.runInContext('refresh()',ui.context);assert.equal(ui.avatarStates.at(-1).custom,question.id);
  await vm.runInContext('refresh()',ui.context);assert.equal(ui.avatarStates.at(-1).custom,writing.id);
  await vm.runInContext('refresh()',ui.context);assert.equal(typeof ui.avatarStates.at(-1),'string');
});

test('character voice library lists cached phrases and previews locally', async () => {
  const voiceLibrary={voice:'Cherry',voice_label:'芊悦 · Cherry',model:'qwen3-tts-flash',ready:1,total:1,
    items:[{id:'conversion_start',group:'转换',text:'开始转换',ready:true}]};
  const ui=workbench({}, {hash:'#character',voiceLibrary}); await settle();
  assert.match(ui.element('voice-library-status').textContent,/已缓存 1\/1 条/);
  const row=ui.element('voice-library-items').children[0];
  assert.match(row.children[0].textContent,/开始转换/);
  await row.children[2].onclick();
  assert.equal(ui.requests.filter(r=>r.url.includes('/voice-library/')).at(-1).url,
    '/api/character/voice-library/conversion_start/preview');
  assert.equal(ui.requests.some(r=>r.url==='/api/tts'),false);
});

test('settings shows the running console version from health', async () => {
  const ui=workbench({}, {hash:'#settings'}); await settle();
  assert.equal(ui.element('desktop-version').textContent,'v9.8.7-test');
  assert.equal(ui.element('header-version').textContent,'v9.8.7-test');
});

test('voice status logs only sustained state changes, not isolated health failures', async () => {
  const base={version:'9.8.7-test',auto_connect_voice:false,voice_url:'local',
    voice_service:{mode:'owned',owned:true},robot:{connected:false},answer:{enabled:false}};
  const ready={...base,voice:{ready:true}};
  const failed={...base,voice_error:{code:'VOICE_OFFLINE',message:'检查失败'}};
  const ui=workbench({}, {healthResponses:[ready,failed,ready,failed,failed,failed,ready,ready]});
  await settle();
  const serviceRows=()=>ui.element('debug-log').children.map(row=>row.textContent).filter(row=>row.includes('[SERVICE]'));
  assert.equal(serviceRows().length,1);
  await vm.runInContext('refresh()',ui.context);
  assert.equal(ui.element('voice-status').textContent,'在线');
  assert.equal(serviceRows().length,1);
  await vm.runInContext('refresh()',ui.context);
  assert.equal(serviceRows().length,1);
  await vm.runInContext('refresh()',ui.context);
  assert.equal(serviceRows().length,1);
  await vm.runInContext('refresh()',ui.context);
  assert.equal(ui.element('voice-status').textContent,'暂不可用');
  assert.match(serviceRows().at(-1),/连续失败（VOICE_OFFLINE）/);
  await vm.runInContext('refresh()',ui.context);
  assert.equal(serviceRows().length,2);
  await vm.runInContext('refresh()',ui.context);
  assert.equal(ui.element('voice-status').textContent,'在线');
  assert.equal(serviceRows().length,3);
  await vm.runInContext('refresh()',ui.context);
  assert.equal(serviceRows().length,3);
});

test('cost query is opt-in AI, labels demo, renders literal sources and never speaks', async () => {
  const ui=workbench({}, {hash:'#cost'}); await settle();
  assert.equal(ui.requests.some(r=>r.url.startsWith('/api/cost') && r.url!=='/api/cost/sentinel'),false);
  ui.element('cost-question').value='计费依据';
  await ui.element('cost-query').onclick();
  assert.equal(JSON.parse(ui.requests.find(r=>r.url==='/api/cost/query').body).allow_ai,false);
  assert.match(ui.element('cost-evidence').textContent,/预设演示/);
  assert.equal(ui.element('cost-sources').children[0].children[2].textContent,'<script>仅作文本</script>');
  ui.element('cost-ai').checked=true;
  await ui.element('cost-query').onclick();
  assert.equal(ui.element('cost-ai').checked,false);
  assert.equal(ui.requests.some(r=>['/api/tts','/api/answer','/api/device/audio/speech','/api/character/bubble'].includes(r.url)),false);
});

test('task sentinel starts on and the switch can turn it off without fetching business data', async () => {
  const ui=workbench({}, {hash:'#cost'}); await settle();
  assert.equal(ui.element('sentinel-enable').checked,true);
  assert.equal(ui.requests.filter(r=>r.url==='/api/cost/sentinel' && r.body).length,0);
  assert.equal(ui.requests.some(r=>r.url==='/api/cost/projects'),false);
  ui.element('sentinel-enable').checked=false;
  await ui.element('sentinel-enable').onchange();
  const request=ui.requests.find(r=>r.url==='/api/cost/sentinel' && r.body);
  assert.deepEqual(JSON.parse(request.body),{enabled:false,mode:'auto',task_id:'',target:'desktop',sound:false,sound_kind:'speech',sound_target:'pc'});
});

test('task sentinel switch is rendered as a switch in the generated console', () => {
  const html=fs.readFileSync(new URL('../static/index.html',import.meta.url),'utf8');
  assert.match(html,/<input(?=[^>]*id="sentinel-enable")(?=[^>]*role="switch")[^>]*>/);
});

test('Astra selection is explicit and old consoles cannot submit an unsupported source', async()=>{
  const old=workbench();await settle();
  assert.equal(old.element('sentinel-source').disabled,true);
  assert.match(old.element('sentinel-source-note').textContent,/重开/);
  const sentinel={source:'legacy',enabled:false,mode:'auto',target:'both',sound:true,sound_kind:'speech',sound_target:'pc',history:[]};
  const ui=workbench({}, {hash:'#cost',sentinel});await settle();
  ui.element('sentinel-source').value='astra';
  await ui.element('sentinel-source').change();
  assert.equal(ui.requests.some(r=>r.url==='/api/cost/sentinel'&&r.body),false);
  assert.match(ui.element('sentinel-source-note').textContent,/尚未应用/);
  ui.element('sentinel-enable').checked=true;
  await ui.element('sentinel-apply').onclick();
  const request=ui.requests.find(r=>r.url==='/api/cost/sentinel'&&r.body);
  assert.deepEqual(JSON.parse(request.body),{source:'astra',enabled:true,mode:'auto',task_id:'',target:'both',sound:true,sound_kind:'speech',sound_target:'pc'});
  assert.match(ui.element('sentinel-source-note').textContent,/当前来源：智算 Astra/);
});

test('late project list from the old source cannot overwrite the selected source',async()=>{
  const ui=workbench({}, {sentinel:{source:'legacy',enabled:false,mode:'auto',target:'desktop',history:[]},sentinelProjects:true,delaySentinelProjects:true});
  await settle();
  const previous=ui.element('sentinel-projects').onclick();await settle();
  ui.element('sentinel-source').value='astra';await ui.element('sentinel-source').change();
  const current=ui.element('sentinel-projects').onclick();await settle();
  assert.equal(ui.waiting.length,2);
  ui.waiting[1]();await current;
  ui.waiting[0]();await previous;
  assert.deepEqual(ui.element('sentinel-project').options.map(item=>item.value),['astra']);
  assert.equal(ui.requests.some(r=>r.url==='/api/cost/sentinel'&&r.body),false);
});

test('manual character preview returns to the active sentinel after its priority window', async () => {
  const ui=workbench({}, {hash:'#character',sentinel:{enabled:true,mode:'auto',task_id:'',target:'desktop',sound:false,sound_target:'pc',current:{activity:{status:'running'},attention:{review_rows:0,warning_rows:0},task_id:'tsk_test',task_name:'测试任务'},last_result:null,last_success_at:'',connection_error:'',history:[],presentation:null}});
  await settle();
  await vm.runInContext('refreshSentinel()',ui.context);
  assert.equal(ui.avatarStates.at(-1),'working');
  ui.element('character-expression').value='happy';
  await ui.element('character-expression').onchange();
  assert.equal(ui.avatarStates.at(-1),'happy');
  vm.runInContext('manualPreviewUntil = Date.now() - 1; render()',ui.context);
  assert.equal(ui.avatarStates.at(-1),'working');
});

test('task sentinel explains when a human action postpones a real reminder', async () => {
  const sentinel={enabled:true,mode:'auto',task_id:'',target:'both',sound:false,sound_target:'pc',current:null,last_result:null,last_success_at:'',connection_error:'',history:[],presentation:null,
    deferred:{task_id:'tsk_test',message:'本次处理结束，请复核结果。',reason:'人工角色操作优先'}};
  const ui=workbench({}, {hash:'#cost',sentinel}); await settle();
  assert.match(ui.element('sentinel-status').textContent,/提醒暂缓：人工角色操作优先/);
  assert.match(ui.element('sentinel-status').textContent,/空闲后自动提示/);
});

test('stage reminders remain visible without an active batch-match snapshot', async () => {
  const record={at:'2026-09-28',task_id:'tsk_stage',task_name:'转换任务',message:'开始转换，正在识别表格。',
    delivery:{desktop:'displayed',watch:'not_requested',sound:'off'}};
  const sentinel={enabled:true,mode:'auto',task_id:'',target:'desktop',sound:false,sound_target:'pc',
    current:null,last_result:null,last_success_at:'2026-09-28',connection_error:'',history:[record],presentation:null};
  const ui=workbench({}, {hash:'#cost',sentinel}); await settle();
  assert.match(ui.element('sentinel-status').textContent,/最近节点：开始转换/);
  assert.match(ui.element('sentinel-current').textContent,/转换任务/);
});

test('cost late result is discarded after stop and summary handoff cannot autoplay', async () => {
  const ui=workbench({}, {hash:'#cost',delayCost:true}); await settle();
  ui.element('cost-question').value='计费依据';
  const request=ui.element('cost-query').onclick(); await settle();
  await ui.element('cost-stop').onclick(); ui.waiting.shift()(); await request;
  assert.equal(ui.element('cost-answer').textContent,'');
  ui.element('cost-summary').value='这是人工确认的摘要';
  ui.element('cost-transfer').onclick();
  assert.equal(ui.location.hash,'#dialogue');
  assert.equal(ui.element('transcript').value,'这是人工确认的摘要');
  assert.equal(ui.element('interaction-mode').value,'read');
  assert.equal(ui.requests.some(r=>['/api/tts','/api/answer','/api/character/bubble'].includes(r.url)),false);
});

test('voice catalogue, saved preferences and cloud speed restriction',async()=>{
  const saved={'gork.cloud-defaults-v1':'true','gork.tts':'local','gork.speech':JSON.stringify({speaker_id:58,cloud_voice:'Ethan',speed:1.15})};
  const ui=workbench(saved);await settle();
  assert.equal(ui.element('voice-select').value,'58');
  ui.element('tts').value='cloud';await ui.element('tts').change();
  assert.equal(ui.element('voice-select').value,'Ethan');
  assert.equal(ui.element('voice-speed').value,'1');assert.equal(ui.element('voice-speed').disabled,true);
  await ui.element('connect').onclick();
  const body=JSON.parse(ui.requests.find(r=>r.url==='/api/settings').body);
  assert.equal(body.speech.cloud_voice,'Ethan');assert.equal(body.speech.speed,1);
  assert.equal(JSON.parse(saved['gork.speech']).speed,1.15);
});

test('voice preview skips answer, preserves editor and cancels stale playback',async()=>{
  const ui=workbench();await settle();await ui.element('connect').onclick();
  ui.element('interaction-mode').value='answer';ui.element('transcript').value='keep this';
  const preview=ui.element('voice-preview').onclick();await settle();
  assert.equal(ui.requests.some(r=>r.url==='/api/answer'),false);
  assert.equal(ui.element('transcript').value,'keep this');
  assert.match(JSON.parse(ui.requests.find(r=>r.url==='/api/tts').body).text,/试听/);
  await ui.element('stop').onclick();ui.waiting.shift()();await preview;
  assert.equal(ui.played.length,0);
});

test('service retry uses only local managed start endpoint',async()=>{
  const ui=workbench();await settle();await ui.element('voice-start').onclick();
  assert.equal(ui.requests.filter(r=>r.url==='/api/voice-service/start').length,1);
  assert.equal(ui.requests.some(r=>r.url==='/api/session'||r.url==='/api/tts'),false);
});

test('default consent is checked and applied on connect without changing providers', async()=>{
  const ui=workbench(); await settle();
  for(const id of ['audio-consent','text-consent','answer-consent']) assert.equal(ui.element(id).checked,true);
  ui.element('asr').value='local';ui.element('tts').value='cloud';
  await ui.element('connect').onclick();
  const settings=JSON.parse(ui.requests.find(r=>r.url==='/api/settings').body);
  assert.equal(settings.routing.asr,'local');assert.equal(settings.routing.tts,'cloud');
  assert.equal(settings.routing.allow_audio_upload,true);assert.equal(settings.routing.allow_text_upload,true);assert.equal(settings.allow_answer_upload,true);
});
test('saved revocation survives page initialization and reconnect', async()=>{
  const ui=workbench({'gork.audio-consent':'false','gork.answer-consent':'false'});await settle();
  for(let i=0;i<2;i++) {
    await ui.element('connect').onclick();
    assert.equal(ui.element('audio-consent').checked,false);assert.equal(ui.element('answer-consent').checked,false);
    await ui.element('release').onclick();
  }
});

test('actual UI handlers: 20 canceled TTS responses never start a player', async()=>{
  const ui=workbench(); await settle(); await ui.element('connect').onclick();
  ui.element('transcript').value='测试文字';
  for(let i=0;i<20;i++){
    const request=ui.element('speak').onclick(); await settle();
    assert.equal(ui.waiting.length,1);
    await ui.element('stop').onclick(); ui.waiting.shift()(); await request;
    assert.equal(ui.played.length,0);
  }
});
test('actual UI handlers: 20 active players stop before server cancellation', async()=>{
  const ui=workbench(); await settle(); await ui.element('connect').onclick();
  ui.element('transcript').value='测试文字';
  for(let i=0;i<20;i++){
    const request=ui.element('speak').onclick(); await settle(); ui.waiting.shift()(); await request;
    const player=ui.played.at(-1), oldEnded=player.onended;
    const cancel=ui.element('stop').onclick();
    assert.equal(player.stopped,true); assert.equal(player.onended,null);
    await cancel; const before=ui.requests.length; oldEnded();
    assert.equal(ui.requests.length,before);
  }
  assert.equal(ui.played.length,20);
});

test('new browser defaults use cloud ASR and TTS without starting a recording or cloud request', async()=>{
  const ui=workbench(); await settle();
  assert.equal(ui.element('asr').value,'cloud');
  assert.equal(ui.element('tts').value,'cloud');
  assert.equal(ui.element('robot-route-summary').textContent,'云端朗读');
  assert.equal(ui.element('auto-read').checked,true);
  assert.equal(ui.element('expression-follow').checked,true);
  assert.equal(ui.requests.some(r=>['/api/session','/api/tts','recorder:start'].includes(r.url)),false);
});

test('startup auto-connect creates one safe voice session without recording or takeover', async()=>{
  const ui=workbench({}, {autoConnectVoice:true});
  await settle(); await new Promise(resolve=>setTimeout(resolve,0)); await settle();
  assert.equal(ui.requests.filter(r=>r.url==='/api/session').length,1);
  assert.equal(ui.requests.filter(r=>r.url==='/api/settings').length,1);
  assert.equal(ui.requests.some(r=>['/api/tts','recorder:start'].includes(r.url)),false);
  assert.equal(ui.element('quick-connect').textContent,'语音已连接');
});

function reconnectTimers(ui){
  const timers=new Map();let serial=0;
  ui.context.setTimeout=(fn,delay)=>{timers.set(++serial,{fn,delay});return serial;};
  ui.context.clearTimeout=id=>timers.delete(id);
  return {timers,async fire(){const [id,value]=timers.entries().next().value;timers.delete(id);await value.fn();await settle();}};
}
test('temporary settings failure retries the owned session and uses the resumed generation',async()=>{
  let settingsFail=true;
  const options={onRequest(url,request){
    if(url==='/api/session'&&request.method==='POST')return {ok:true,json:async()=>({generation:7,resumed:true})};
    if(url==='/api/settings'&&settingsFail){settingsFail=false;return {ok:false,status:503,json:async()=>({error:{code:'VOICE_OFFLINE',message:'暂时离线'}})};}
  }};
  const ui=workbench({},options);await settle();const timing=reconnectTimers(ui);
  vm.runInContext('startupVoice.enabled=true',ui.context);
  await vm.runInContext('autoConnectVoice()',ui.context);
  assert.equal(timing.timers.size,1);assert.equal(ui.element('quick-connect').textContent,'连接语音');
  await timing.fire();assert.equal(ui.element('quick-connect').textContent,'语音已连接');
  assert.equal(JSON.parse(ui.requests.filter(r=>r.url==='/api/settings').at(-1).body).generation,8);
});
test('a lost session reconnects after successful startup, retaining tone and consent without playback',async()=>{
  let lost=false;
  const saved={'gork.cloud-defaults-v1':'true','gork.speech':JSON.stringify({cloud_voice:'Ethan',speaker_id:58,speed:1}),
    'gork.audio-consent':'false','gork.asr':'local','gork.text-consent':'true','gork.answer-consent':'false'};
  const ui=workbench(saved,{autoConnectVoice:true,onRequest(url,options){
    if(lost&&url==='/api/session'&&(!options.method||options.method==='GET'))return {ok:false,status:401,json:async()=>({error:{code:'VOICE_SESSION_INVALID',message:'失效'}})};
  }});
  await settle();await new Promise(resolve=>setTimeout(resolve,0));await settle();
  const timing=reconnectTimers(ui);lost=true;
  await vm.runInContext('heartbeat()',ui.context);
  assert.equal(timing.timers.size,1,'successful startup must not permanently disable recovery');
  lost=false;await timing.fire();
  assert.equal(ui.element('quick-connect').textContent,'语音已连接');
  const posts=ui.requests.filter(r=>r.url==='/api/session'&&r.body);
  assert.equal(posts.length,2);assert(posts.every(r=>JSON.parse(r.body).replace===false));
  const settings=JSON.parse(ui.requests.filter(r=>r.url==='/api/settings').at(-1).body);
  assert.equal(settings.speech.cloud_voice,'Ethan');assert.equal(settings.routing.allow_audio_upload,false);
  assert.equal(settings.allow_answer_upload,false);
  assert.equal(ui.requests.some(r=>['/api/asr','/api/tts','recorder:start'].includes(r.url)),false);
});
test('automatic retry continues beyond the old startup cap with backoff and stops on manual release or busy owner',async()=>{
  const options={autoConnectVoice:false};const ui=workbench({},options);await settle();
  vm.runInContext('startupVoice.enabled=true;startupVoice.attempts=60',ui.context);
  const timing=reconnectTimers(ui);
  options.onRequest=(url,request)=>url==='/api/session'&&request.method==='POST'?
    {ok:false,status:503,json:async()=>({error:{code:'VOICE_OFFLINE',message:'离线'}})}:undefined;
  await vm.runInContext('autoConnectVoice()',ui.context);
  assert.equal(timing.timers.size,1);assert.equal([...timing.timers.values()][0].delay,30000);
  await vm.runInContext('release()',ui.context);assert.equal(timing.timers.size,0);
  await vm.runInContext('refresh()',ui.context);assert.equal(timing.timers.size,0);
  options.onRequest=(url,request)=>url==='/api/session'&&request.method==='POST'?
    {ok:false,status:409,json:async()=>({error:{code:'SESSION_BUSY',message:'占用'}})}:undefined;
  await ui.element('connect').onclick();
  assert.equal(timing.timers.size,0,'busy owners are not taken over automatically');
});
test('late heartbeat and connection responses cannot undo a newer connection or explicit release',async()=>{
  const options={};const ui=workbench({},options);await settle();await ui.element('connect').onclick();
  let failHeartbeat;
  options.onRequest=(url,request)=>url==='/api/session'&&request.method==='GET'?new Promise(resolve=>{failHeartbeat=resolve;}):undefined;
  const old=vm.runInContext('heartbeat()',ui.context);await settle();
  await ui.element('connect').onclick();
  failHeartbeat({ok:false,status:401,json:async()=>({error:{code:'VOICE_SESSION_INVALID',message:'过期响应'}})});await old;
  assert.equal(ui.element('quick-connect').textContent,'语音已连接');
  let finishConnection;
  options.onRequest=(url,request)=>url==='/api/session'&&request.method==='POST'?new Promise(resolve=>{finishConnection=resolve;}):undefined;
  const pending=ui.element('connect').onclick();await settle();await ui.element('release').onclick();
  finishConnection({ok:true,json:async()=>({generation:9})});await pending;
  assert.equal(ui.element('quick-connect').textContent,'连接语音');
});
test('automatic recovery only starts a configured stopped manager, never a running or external service',async()=>{
  const options={};const ui=workbench({},options);await settle();const timing=reconnectTimers(ui);
  for(const mode of ['owned','external','starting','offline']){
    options.onRequest=url=>url==='/api/health'?{ok:true,json:async()=>({auto_connect_voice:true,
      voice_error:{code:'VOICE_OFFLINE',message:'离线'},voice_service:{mode,configured:true},robot:{},answer:{}})}:undefined;
    await vm.runInContext('refresh()',ui.context);
    vm.runInContext('connected=false;startupVoice.paused=false',ui.context);
    const before=ui.requests.filter(r=>r.url==='/api/voice-service/start').length;
    await vm.runInContext('autoConnectVoice()',ui.context);
    assert.equal(ui.requests.filter(r=>r.url==='/api/voice-service/start').length-before,mode==='offline'?1:0);
  }
  timing.timers.clear();
});

test('saved local route and independent consent revocations survive reload', async()=>{
  const saved={'gork.cloud-defaults-v1':'true','gork.tts':'local','gork.audio-consent':'false','gork.text-consent':'false','gork.answer-consent':'false'};
  const ui=workbench(saved); await settle();
  assert.equal(ui.element('tts').value,'local');
  assert.equal(ui.element('robot-route-summary').textContent,'本地朗读');
  for(const id of ['audio-consent','text-consent','answer-consent']) assert.equal(ui.element(id).checked,false);
  await ui.element('connect').onclick();
  const body=JSON.parse(ui.requests.find(r=>r.url==='/api/settings').body);
  assert.equal(body.routing.allow_audio_upload,false);
  assert.equal(body.routing.allow_text_upload,false);
  assert.equal(body.allow_answer_upload,false);
});

test('cloud-default migration replaces old routes once and preserves subsequent manual choices', async()=>{
  const saved={'gork.asr':'local','gork.tts':'local'};
  const first=workbench(saved);await settle();
  assert.equal(first.element('asr').value,'cloud');assert.equal(first.element('tts').value,'cloud');
  assert.equal(saved['gork.cloud-defaults-v1'],'true');
  saved['gork.asr']='local';saved['gork.tts']='local';
  const second=workbench(saved);await settle();
  assert.equal(second.element('asr').value,'local');assert.equal(second.element('tts').value,'local');
  const revoked=workbench({'gork.asr':'local','gork.tts':'local','gork.audio-consent':'false','gork.text-consent':'false'});await settle();
  assert.equal(revoked.element('asr').value,'local');assert.equal(revoked.element('tts').value,'local');
  assert.equal(revoked.element('audio-consent').checked,false);assert.equal(revoked.element('text-consent').checked,false);
  assert.equal(revoked.requests.some(r=>['/api/asr','/api/tts','recorder:start'].includes(r.url)),false);
  const full=workbench({'gork.asr':'local','gork.tts':'local'},{storageWritesFail:true});await settle();
  assert.equal(full.element('asr').value,'cloud');assert.equal(full.element('tts').value,'cloud');
});

test('revoking text upload switches cloud TTS to local immediately', async()=>{
  const ui=workbench(); await settle(); await ui.element('connect').onclick();
  ui.element('text-consent').checked=false; await ui.element('text-consent').change(); await settle();
  assert.equal(ui.element('tts').value,'local');
  assert.equal(ui.saved['gork.text-consent'],'false');
  assert.equal(JSON.parse(ui.requests.filter(r=>r.url==='/api/settings').at(-1).body).routing.allow_text_upload,false);
  assert.equal(JSON.parse(ui.requests.filter(r=>r.url==='/api/settings').at(-1).body).speech,null);
  assert.equal(ui.element('robot-route-summary').textContent,'本地朗读');
});

test('ordinary route draft leaves current playback path usable until Apply', async()=>{
  const ui=workbench(); await settle(); await ui.element('connect').onclick();
  ui.element('tts').value='local'; await ui.element('tts').change();
  assert.equal(ui.element('speak').disabled,true); // Empty editor, not a route block.
  ui.element('transcript').value='仍使用已应用设置'; ui.element('transcript').oninput();
  assert.equal(ui.element('speak').disabled,false);
  assert.equal(ui.element('robot-route-summary').textContent,'云端朗读');
  assert.equal(ui.requests.filter(r=>r.url==='/api/stop').length,0);
});

test('one composer sends Watch text without TTS and blocks overlong bubbles', async()=>{
  const ui=workbench({}, {robotConnected:true}); await settle(); await ui.element('workspace-acquire').onclick();
  ui.element('output-mode').value='bubble'; await ui.element('output-mode').change();
  ui.element('bubble-target').value='watch'; await ui.element('bubble-target').change();
  assert.equal(ui.element('bubble-target-control').hidden,false);
  ui.element('transcript').value='晚安'; ui.element('transcript').oninput();
  await ui.element('speak').onclick();
  const sends=ui.requests.filter(r=>r.url==='/api/character/bubble');
  assert.equal(sends.length,1);
  assert.equal(JSON.parse(sends[0].body).target,'watch');
  assert.equal(JSON.parse(sends[0].body).text,'晚安');
  assert.equal(ui.requests.filter(r=>r.url==='/api/tts').length,0);
  assert.equal(ui.requests.filter(r=>r.url==='/api/session').length,0);
  ui.element('transcript').value='这是超过二十四个汉字的文字，不能悄悄裁剪以后送到小人的屏幕上';
  ui.element('transcript').oninput();
  assert.equal(ui.element('speak').disabled,true);
  assert.match(ui.element('answer-status').textContent,/Watch 文字超限/);
  assert.equal(ui.requests.filter(r=>r.url==='/api/character/bubble').length,1);
});

test('unified display keeps desktop bubble and needs no Watch connection', async()=>{
  const ui=workbench(); await settle(); await ui.element('workspace-acquire').onclick();
  ui.element('output-mode').value='bubble'; ui.element('bubble-target').value='desktop';
  ui.element('transcript').value='桌面显示'.repeat(12); ui.element('transcript').oninput();
  assert.equal(ui.element('speak').disabled,false);
  await ui.element('speak').onclick();
  assert.equal(JSON.parse(ui.requests.find(r=>r.url==='/api/character/bubble').body).target,'desktop');
});

test('both display keeps long desktop text available when Watch is offline', async()=>{
  const ui=workbench();await settle();await ui.element('workspace-acquire').onclick();
  ui.element('output-mode').value='bubble';await ui.element('output-mode').change();
  assert.equal(ui.element('bubble-target').value,'both');
  ui.element('transcript').value='桌面完整文字'.repeat(10);ui.element('transcript').oninput();
  assert.equal(ui.element('speak').disabled,false);
  await ui.element('speak').onclick();
  const request=JSON.parse(ui.requests.find(r=>r.url==='/api/character/bubble').body);
  assert.equal(request.target,'both');assert.equal(request.text,ui.element('transcript').value);
  assert.equal(ui.requests.some(r=>r.url==='/api/tts'),false);
});

test('AI answer can be displayed on Watch without synthesizing audio', async()=>{
  const ui=workbench({}, {robotConnected:true}); await settle(); await ui.element('connect').onclick();
  ui.element('output-mode').value='bubble'; ui.element('interaction-mode').value='answer';
  ui.element('transcript').value='今天怎么样'; await ui.element('speak').onclick();
  const bubble=ui.requests.find(r=>r.url==='/api/character/bubble');
  assert.equal(JSON.parse(bubble.body).text,'单独的回答');
  assert.equal(ui.requests.filter(r=>r.url==='/api/answer').length,1);
  assert.equal(ui.requests.filter(r=>r.url==='/api/tts').length,0);
});

test('Watch speech uses delayed device audio, with no computer playback', async()=>{
  const ui=workbench({}, {robotConnected:true}); await settle(); await ui.element('connect').onclick();
  ui.element('output-mode').value='watch-audio'; ui.element('transcript').value='晚安'; ui.element('transcript').oninput();
  const request=ui.element('speak').onclick(); await settle();
  assert.equal(ui.requests.filter(r=>r.url==='/api/tts').length,1);
  ui.waiting.shift()(); await request;
  assert.equal(ui.requests.filter(r=>r.url==='/api/device/audio/speech').length,1);
  assert.equal(JSON.parse(ui.requests.find(r=>r.url==='/api/tts').body).watch_speech,true);
  assert.equal(ui.requests.find(r=>r.url==='/api/device/audio/speech').headers['X-Generation'],
    String(JSON.parse(ui.requests.find(r=>r.url==='/api/tts').body).generation));
  assert.equal(ui.played.length,0);
  assert.match(ui.element('message').textContent,/Watch 报告播放完成/);
});

test('AI answer is also deferred until Watch audio is ready', async()=>{
  const ui=workbench({}, {robotConnected:true}); await settle(); await ui.element('connect').onclick();
  ui.element('interaction-mode').value='answer';
  ui.element('output-mode').value='watch-audio'; ui.element('transcript').value='请回答'; ui.element('transcript').oninput();
  const request=ui.element('speak').onclick(); await settle(); ui.waiting.shift()(); await request;
  assert.equal(JSON.parse(ui.requests.find(r=>r.url==='/api/answer').body).watch_speech,true);
  const synthesis=JSON.parse(ui.requests.find(r=>r.url==='/api/tts').body);
  assert.equal(synthesis.watch_speech,true);
  assert.equal(synthesis.text,'单独的回答');
  assert.equal(ui.requests.filter(r=>r.url==='/api/device/audio/speech').length,1);
});

test('Watch speech waits for the new backend instead of showing text early', async()=>{
  const ui=workbench({}, {robotConnected:true,oldBackend:true}); await settle(); await ui.element('connect').onclick();
  ui.element('output-mode').value='watch-audio'; ui.element('transcript').value='你好'; ui.element('transcript').oninput();
  await ui.element('speak').onclick();
  assert.equal(ui.requests.filter(r=>r.url==='/api/tts').length,0);
  assert.equal(ui.requests.filter(r=>r.url==='/api/device/audio/speech').length,0);
  assert.match(ui.element('message').textContent,/请从托盘退出后重新打开/);
});

test('Watch speech does not report success when the audio task fails before sending', async()=>{
  const ui=workbench({}, {robotConnected:true,audioResult:{job_id:'test-job',running:false,stage:'error',error:'',bytes:0,total:69120}});
  await settle(); await ui.element('connect').onclick();
  ui.element('output-mode').value='watch-audio'; ui.element('transcript').value='晚安';
  const request=ui.element('speak').onclick(); await settle(); ui.waiting.shift()(); await request;
  assert.doesNotMatch(ui.element('message').textContent,/播放完成/);
  assert.match(ui.element('message').textContent,/音频任务失败/);
  assert.equal(ui.played.length,0);
});

test('Watch speech requires a played receipt rather than any finished task', async()=>{
  const ui=workbench({}, {robotConnected:true,audioResult:{job_id:'test-job',running:false,stage:'received',error:'',bytes:69120,total:69120}});
  await settle(); await ui.element('connect').onclick();
  ui.element('output-mode').value='watch-audio'; ui.element('transcript').value='晚安';
  const request=ui.element('speak').onclick(); await settle(); ui.waiting.shift()(); await request;
  assert.doesNotMatch(ui.element('message').textContent,/报告播放完成/);
  assert.match(ui.element('message').textContent,/尚未收到播放完成回执/);
});

test('stopped Watch speech never sends a late TTS result to the device', async()=>{
  const ui=workbench({}, {robotConnected:true}); await settle(); await ui.element('connect').onclick();
  ui.element('output-mode').value='watch-audio'; ui.element('transcript').value='晚安';
  const request=ui.element('speak').onclick(); await settle();
  await ui.element('stop').onclick(); ui.waiting.shift()(); await request;
  assert.equal(ui.requests.filter(r=>r.url==='/api/device/audio/speech').length,0);
});

test('revoking answer permission stops active route then applies independent consent', async()=>{
  const ui=workbench(); await settle(); await ui.element('connect').onclick();
  ui.element('interaction-mode').value='answer'; ui.element('answer-consent').checked=false;
  await ui.element('answer-consent').change();
  const stopIndex=ui.requests.findIndex(r=>r.url==='/api/stop');
  const lastSettings=ui.requests.findLastIndex(r=>r.url==='/api/settings');
  assert.ok(stopIndex>=0 && stopIndex<lastSettings);
  assert.equal(ui.element('interaction-mode').value,'read');
  assert.equal(JSON.parse(ui.requests[lastSettings].body).allow_answer_upload,false);
});

test('auto-read off keeps answer visible without TTS and does not alter editor', async()=>{
  const ui=workbench({'gork.auto-read':'false'}); await settle(); await ui.element('connect').onclick();
  ui.element('interaction-mode').value='answer'; ui.element('transcript').value='原始问题';
  await ui.element('speak').onclick();
  assert.equal(ui.requests.filter(r=>r.url==='/api/answer').length,1);
  assert.equal(JSON.parse(ui.requests.find(r=>r.url==='/api/answer').body).speech_pending,false);
  assert.equal(ui.requests.filter(r=>r.url==='/api/tts').length,0);
  assert.equal(ui.element('transcript').value,'原始问题');
  const rows=ui.element('chat-log').children;
  assert.equal(rows.length,2);
  assert.equal(rows[0].children[1].textContent,'原始问题');
  assert.equal(rows[1].children[1].textContent,'单独的回答');
});

test('composer uses one writing loop across answer, TTS and playback and clears it immediately at the end',async()=>{
  const entry={id:'motion-000000000001',name:'我的书写',scene:'writing',config:{}};
  const ui=workbench({}, {answerResult:{text:'回答',interaction_expression:entry},stateResult:{interaction_expression:entry}});
  await settle();await ui.element('connect').onclick();
  ui.element('interaction-mode').value='answer';ui.element('transcript').value='问题';
  const request=ui.element('speak').onclick();await settle();
  assert.equal(JSON.parse(ui.requests.find(r=>r.url==='/api/answer').body).speech_pending,true);
  assert.equal(ui.avatarStates.filter(s=>s.custom===entry.id).length,1);
  ui.waiting.shift()();await request;
  assert.equal(ui.avatarStates.filter(s=>s.custom===entry.id).length,1);
  ui.played[0].onended();await settle();
  assert.equal(typeof ui.avatarStates.at(-1),'string','completed playback ends the custom motion immediately');
});

test('new composer omits the speech continuation field when an older backend has no capability',async()=>{
  const ui=workbench({'gork.auto-read':'false'}, {answerSpeechContinuity:false});
  await settle();await ui.element('connect').onclick();
  ui.element('interaction-mode').value='answer';ui.element('transcript').value='问题';
  await ui.element('speak').onclick();
  const body=JSON.parse(ui.requests.find(r=>r.url==='/api/answer').body);
  assert.equal('speech_pending' in body,false);
});

test('tabs change only right-hand pages and keep one mounted avatar', async()=>{
  const ui=workbench(); await settle();
  const avatarCount=ui.avatarStates.length;
  for(const page of ['character','watch','settings','dialogue']) {
    ui.location.hash='#'+page; ui.events.hashchange();
    assert.equal(ui.pages.find(item=>item.dataset.page===page).hidden,false);
    assert.equal(ui.pages.filter(item=>!item.hidden).length,1);
  }
  assert.equal(ui.avatarStates.length,avatarCount);
  assert.equal(ui.tabs.filter(item=>item.tabIndex===0).length,1);
});

test('repeat record clicks start one capture while first request is pending', async()=>{
  const ui=workbench(); await settle(); await ui.element('connect').onclick();
  const first=ui.element('record').onclick(), second=ui.element('record').onclick();
  await Promise.all([first,second]);
  assert.equal(ui.requests.filter(r=>r.url==='recorder:start').length,1);
  await ui.element('stop').onclick();
});

test('repeat connect clicks create only one voice session', async()=>{
  const ui=workbench(); await settle();
  await Promise.all([ui.element('connect').onclick(),ui.element('quick-connect').onclick()]);
  assert.equal(ui.requests.filter(r=>r.url==='/api/session').length,1);
  assert.equal(ui.requests.filter(r=>r.url==='/api/settings').length,1);
});

test('desktop avatar switch uses bridge and reads back actual window state', async()=>{
  let visible=true; const calls=[];
  const ui=workbench({}, {desktop:{getAvatarVisible:async()=>visible,setAvatarVisible:async value=>{calls.push(value);visible=value;}}});
  await settle();
  assert.equal(ui.element('desktop-visible').disabled,false);
  assert.equal(ui.element('desktop-visible').checked,true);
  ui.element('desktop-visible').checked=false; await ui.element('desktop-visible').change();
  assert.deepEqual(calls,[false]);
  assert.equal(ui.element('desktop-visible').checked,false);
  assert.equal(ui.element('desktop-visible').disabled,false);
});

test('pointer follow switch defaults on, toggles immediately, restores saved off and recovers from failure', async()=>{
  let enabled=true,fail=false;const calls=[];
  const desktop={getPointerFollow:async()=>enabled,setPointerFollow:async value=>{calls.push(value);if(fail)throw Error('保存失败');enabled=value;}};
  const ui=workbench({}, {desktop});await settle();
  const toggle=ui.element('desktop-pointer-follow');
  assert.equal(toggle.checked,true);assert.equal(toggle.disabled,false);
  toggle.checked=false;await toggle.change();assert.equal(toggle.checked,false);assert.deepEqual(calls,[false]);
  const reopened=workbench({}, {desktop});await settle();assert.equal(reopened.element('desktop-pointer-follow').checked,false);
  fail=true;toggle.checked=true;await toggle.change();assert.equal(toggle.checked,false);assert.equal(toggle.disabled,false);
  fail=false;toggle.checked=true;await toggle.change();assert.equal(toggle.checked,true);
  assert.equal(ui.requests.some(r=>r.url==='/api/device'),false);
});

test('desktop size changes coalesce pending values and leave the web avatar untouched', async()=>{
  const calls=[], releases=[];
  const ui=workbench({}, {desktop:{getAvatarScale:async()=>100,setAvatarScale:value=>{calls.push(value);return new Promise(resolve=>releases.push(()=>resolve(value)));}}});
  await settle();
  assert.equal(ui.element('desktop-size').disabled,false);
  assert.equal(ui.element('desktop-size-value').textContent,'100%');
  const avatarCount=ui.avatarStates.length;
  for (const value of ['25','75','150']) { ui.element('desktop-size').value=value; ui.element('desktop-size').oninput(); }
  assert.deepEqual(calls,[25]);
  releases.shift()(); await settle(); assert.deepEqual(calls,[25,150]);
  releases.shift()(); await settle();
  assert.equal(ui.element('desktop-size-value').textContent,'150%');
  assert.equal(ui.avatarStates.length,avatarCount);
  assert.equal(ui.requests.some(r=>r.url==='/api/device'),false);
});

test('desktop always-on-top switch reads back the Electron window state', async()=>{
  let top=true; const calls=[];
  const ui=workbench({}, {desktop:{getAvatarAlwaysOnTop:async()=>top,setAvatarAlwaysOnTop:async value=>{calls.push(value);top=value;}}});
  await settle();
  assert.equal(ui.element('desktop-always-on-top').checked,true);
  assert.equal(ui.element('desktop-always-on-top').disabled,false);
  ui.element('desktop-always-on-top').checked=false;
  await ui.element('desktop-always-on-top').change();
  assert.deepEqual(calls,[false]);
  assert.equal(ui.element('desktop-always-on-top').checked,false);
  assert.equal(ui.element('desktop-always-on-top').disabled,false);
});

test('console shares automatic and preview animation starts with the floating avatar', async()=>{
  const scenes=[];
  const ui=workbench({}, {desktop:{setAvatarScene:async scene=>{scenes.push(scene);}}});
  await settle();
  assert.equal(scenes[0].expression,'idle');
  ui.element('character-expression').value='happy';
  ui.element('character-mode').value='once';
  await ui.element('character-preview').onclick();
  assert.equal(scenes.at(-1).expression,'happy');
  assert.equal(scenes.at(-1).mode,'once');
  assert.ok(Number.isFinite(scenes.at(-1).startedAt));
  ui.element('character-idle').onclick(); await settle();
  assert.equal(scenes.at(-1).expression,'idle');
});

test('logs tab opens without device requests',async()=>{
  const ui=workbench({}, {hash:'#logs'});await settle();
  assert.equal(ui.pages.find(p=>p.dataset.page==='logs').hidden,false);
  assert.equal(ui.pages.find(p=>p.dataset.page==='dialogue').hidden,true);
  assert.equal(ui.requests.some(r=>r.url.startsWith('/api/device')),false);
});

test('desktop bubble position loads and saves using the native bridge',async()=>{
  const calls=[];let position='above';
  const ui=workbench({}, {desktop:{getBubblePosition:async()=>position,setBubblePosition:async value=>{calls.push(value);position=value;return value;}}});
  await settle();assert.equal(ui.element('desktop-bubble-position').value,'above');
  ui.element('desktop-bubble-position').value='right';await ui.element('desktop-bubble-position').change();
  assert.deepEqual(calls,['right']);assert.equal(ui.element('desktop-bubble-position').value,'right');
  assert.equal(ui.requests.some(r=>r.url.includes('/device')),false);
});

function openExpressions(ui) {
  const menu=ui.element('expression-menu'); menu.open=true;
  for(const listener of menu.listeners.toggle) listener();
  return ui.element('expression-grid').children;
}
test('expression menu builds 23 real previews only when expanded and hover sends nothing',async()=>{
  const ui=workbench(); await settle();
  assert.equal(ui.element('expression-grid').children.length,0);
  const tiles=openExpressions(ui); assert.equal(tiles.length,23);
  tiles[1].listeners.pointerenter[0]();
  assert.equal(ui.avatarStates.at(-1),'happy');
  assert.equal(ui.requests.some(r=>r.url==='/api/character'),false);
  await tiles[1].onclick();
  assert.deepEqual(JSON.parse(ui.requests.find(r=>r.url==='/api/character').body),{expression:'happy',target:'both',mode:'once'});
  assert.equal(JSON.parse(ui.requests.find(r=>r.url==='/api/workspace').body).replace,false);
  assert.match(ui.element('expression-feedback').textContent,/桌面：已接收/);
});

test('custom library joins menu without playing; explicit clicks route to desktop, Watch and both',async()=>{
  const calls=[],entry={id:'motion-000000000001',name:'专注书写',scene:'writing',config:{}};
  const ui=workbench({}, {robotConnected:true,customEntries:[entry],desktop:{playCustomExpression:async(id,mode)=>calls.push({id,mode})}});await settle();
  const tiles=openExpressions(ui);assert.equal(tiles.length,24);
  assert.equal(tiles[23].dataset.expression,entry.id);assert.match(tiles[23].children[1].textContent,/专注书写.*自定义/);
  assert.equal(calls.length,0);assert.equal(ui.requests.some(r=>r.url==='/api/character'),false);
  tiles[23].listeners.pointerenter[0]();assert.equal(calls.length,0);
  assert.equal(ui.element('expression-target').value,'both');
  ui.element('expression-target').value='desktop';await ui.element('expression-target').change();
  await tiles[23].onclick();assert.deepEqual(calls,[{id:entry.id,mode:'once'}]);
  assert.deepEqual(JSON.parse(ui.requests.find(r=>r.url==='/api/character').body),{expression:entry.id,target:'desktop',mode:'once'});
  ui.element('expression-target').value='watch';await ui.element('expression-target').change();await tiles[23].onclick();
  assert.deepEqual(JSON.parse(ui.requests.filter(r=>r.url==='/api/character').at(-1).body),{expression:entry.id,target:'watch',mode:'once'});
  assert.equal(calls.length,1);
  ui.element('expression-target').value='both';await ui.element('expression-target').change();await tiles[23].onclick();
  assert.deepEqual(JSON.parse(ui.requests.filter(r=>r.url==='/api/character').at(-1).body),{expression:entry.id,target:'both',mode:'once'});
  assert.equal(calls.length,2);
});
test('Watch-only expression does not change desktop scene; both reports partial failure',async()=>{
  const scenes=[];const ui=workbench({}, {robotConnected:true,watchError:'设备忙',desktop:{setAvatarScene:async scene=>scenes.push(scene)}});await settle();
  const tiles=openExpressions(ui);scenes.length=0;
  ui.element('expression-target').value='watch';await ui.element('expression-target').change();
  ui.element('expression-mode').value='loop';await tiles[1].onclick();
  assert.equal(scenes.length,0);assert.equal(JSON.parse(ui.requests.find(r=>r.url==='/api/character').body).mode,'loop');
  ui.element('expression-target').value='both';await ui.element('expression-target').change();await tiles[1].onclick();
  assert.equal(scenes.at(-1).expression,'happy');
  assert.match(ui.element('expression-feedback').textContent,/桌面：已接收；Watch：设备忙/);
});
test('offline Watch and workspace conflict never send expressions or take over',async()=>{
  const ui=workbench({}, {workspaceBusy:true});await settle();const tiles=openExpressions(ui);
  ui.element('expression-target').value='watch';await ui.element('expression-target').change();await tiles[1].onclick();
  assert.match(ui.element('expression-feedback').textContent,/未连接/);
  assert.equal(ui.requests.some(r=>r.url==='/api/character'),false);
  ui.element('expression-target').value='desktop';await ui.element('expression-target').change();await tiles[1].onclick();
  assert.match(ui.element('expression-feedback').textContent,/未取得控制权/);
  assert.equal(ui.requests.some(r=>r.url==='/api/character'),false);
});
test('expression pending locks repeated sends and late result cannot restart desktop after global stop',async()=>{
  const scenes=[];const ui=workbench({}, {delayExpression:true,desktop:{setAvatarScene:async scene=>scenes.push(scene)}});await settle();
  const tiles=openExpressions(ui);const pending=tiles[1].onclick();await settle();
  await tiles[2].onclick();assert.equal(ui.requests.filter(r=>r.url==='/api/character').length,1);
  await ui.element('cost-stop').onclick();scenes.length=0;
  ui.waiting.shift()();await pending;
  assert.equal(scenes.some(s=>s.expression==='happy'),false);
  assert.match(ui.element('expression-feedback').textContent,/取消/);
});
test('collapsed menu disposes hover animation; reopening retains one set of tiles',async()=>{
  const ui=workbench();await settle();const tiles=openExpressions(ui);
  assert.equal(ui.previewMounts.filter(m=>m.options?.still).length,23);
  assert.ok(ui.previewMounts.filter(m=>m.options?.still).every(m=>m.disposed));
  tiles[1].listeners.focus[0]();const animated=ui.previewMounts.at(-1);assert.equal(animated.disposed,false);
  ui.element('expression-menu').open=false;
  ui.element('expression-menu').listeners.toggle[0]();assert.equal(animated.disposed,true);
  assert.equal(openExpressions(ui).length,23);
});
