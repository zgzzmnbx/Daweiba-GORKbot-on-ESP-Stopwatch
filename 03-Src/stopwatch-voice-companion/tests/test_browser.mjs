import test from 'node:test';
import assert from 'node:assert/strict';
import {toPCM16, Epoch} from '../static/pcm.js';
import fs from 'node:fs';
import vm from 'node:vm';
import {webcrypto} from 'node:crypto';
import {createDebugConsole} from '../static/debug-console.js';

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
  const elements = new Map(), waiting = [], played = [], requests = [], events = {}, avatarStates = [];
  const nodes = name => ({nodeName:name, children:[], dataset:{}, listeners:{}, hidden:false,
    classList:{toggle(){}},setAttribute(){},focus(){this.focused=true;},remove(){this.removed=true;},
    append(...items){this.children.push(...items);},replaceChildren(...items){this.children=items;this.options=[];this.value='';},
    addEventListener(type,fn){(this.listeners[type] ||= []).push(fn);},
    async keydown(event){for(const fn of this.listeners.keydown || []) await fn(event);}});
  const element = id => {
    if (!elements.has(id)) elements.set(id, {...nodes('div'),value:id==='asr'?'local':id==='interaction-mode'?'read':'',textContent:'',checked:false,options:[],
      async change(){for(const fn of this.listeners.change || []) await fn(); if(this.onchange) await this.onchange();},
      add(option){this.options.push(option);if(this.options.length===1)this.value=option.value;},getTracks(){return [];}});
    return elements.get(id);
  };
  const pages = ['dialogue','character','watch','settings','logs'].map(page=>Object.assign(nodes('section'),{dataset:{page}}));
  const tabs = ['dialogue','character','watch','settings','logs'].map(page=>Object.assign(nodes('a'),{dataset:{pageLink:page}}));
  const location = {hash:uiOptions.hash || '#dialogue'};
  const desktop = uiOptions.desktop;
  class AudioContext {
    constructor(){this.state='running';}
    async resume(){} async suspend(){} async close(){this.state='closed';}
    async decodeAudioData(){return {};}
    createBufferSource(){const player={stopped:false,connect(){},disconnect(){},start(){played.push(this);},stop(){this.stopped=true;}};return player;}
  }
  const context = vm.createContext({
    toPCM16,Epoch,AbortController,AbortSignal,DOMException,ArrayBuffer,TextEncoder,performance,AudioContext,createDebugConsole,
    Recorder:class{async start(){requests.push({url:'recorder:start'});return true;}finish(){return new ArrayBuffer(44);}stop(){}},
    WavPlayer:class{constructor(){this.playing=false;}async play(_bytes,onended){this.playing=true;this.onended=onended;return true;}stop(){this.playing=false;}},
    Option:class{constructor(label,value){this.label=label;this.value=value;}},
    crypto:webcrypto,location,history:{replaceState(_a,_b,hash){location.hash=hash;}},
    document:{getElementById:element,createElement:nodes,querySelectorAll:selector=>selector==='[data-page]'?pages:selector==='[data-page-link]'?tabs:[],body:{dataset:{}}},
    window:{GorkAvatar:{mount(){return {set:state=>avatarStates.push(state)};}},gorkDesktop:desktop,
      addEventListener(name,fn){events[name]=fn;},localStorage:{getItem:key=>saved[key]??null,setItem:(key,value)=>{saved[key]=value;}}},
    setInterval:()=>0,clearInterval(){},clearTimeout,setTimeout,console,
    async fetch(url, options){
      requests.push({url,body:options.body});
      if(url==='/api/tts') return await new Promise(resolve=>waiting.push(()=>resolve({ok:true,arrayBuffer:async()=>new ArrayBuffer(44)})));
      return {ok:true,json:async()=>url==='/api/health'?{auto_connect_voice:uiOptions.autoConnectVoice === true,voice:{ready:true},voice_url:'local',robot:{connected:uiOptions.robotConnected === true},answer:{enabled:true},
        capabilities:{protocol_version:1,tts:{speakers:[{id:3,label:'local 3'},{id:58,label:'local 58'}]},
          cloud:{request_voice:true,voices:[{id:'Cherry',label:'Cherry'},{id:'Ethan',label:'Ethan'}]}}}:url==='/api/answer'?{text:'单独的回答'}:
        url==='/api/character/bubble'?{desktop:{requested:true,accepted:true},watch:{requested:true,accepted:true,receipt:'OK:TEXT'}}:
        url==='/api/device/audio/play'?{job_id:'test-job'}:
        url==='/api/device/audio'?(uiOptions.audioResult || {job_id:'test-job',running:false,stage:'played',bytes:44,total:44}):{generation:0,robot:{}}};
    }
  });
  const script = fs.readFileSync(new URL('../static/app.js', import.meta.url),'utf8').replace(/^import .*;\r?\n/gm, '');
  vm.runInContext(script,context);
  return {element,waiting,played,requests,pages,tabs,location,events,avatarStates,saved};
}
const settle = () => new Promise(resolve=>setImmediate(resolve));

test('voice catalogue, saved preferences and cloud speed restriction',async()=>{
  const saved={'gork.tts':'local','gork.speech':JSON.stringify({speaker_id:58,cloud_voice:'Ethan',speed:1.15})};
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

test('new browser defaults use local ASR, cloud TTS and no automatic request', async()=>{
  const ui=workbench(); await settle();
  assert.equal(ui.element('asr').value,'local');
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

test('saved local route and independent consent revocations survive reload', async()=>{
  const saved={'gork.tts':'local','gork.audio-consent':'false','gork.text-consent':'false','gork.answer-consent':'false'};
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
  assert.equal(ui.requests.filter(r=>r.url==='/api/device/audio/play').length,1);
  assert.equal(ui.played.length,0);
  assert.match(ui.element('message').textContent,/Watch 报告播放完成/);
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
  assert.equal(ui.requests.filter(r=>r.url==='/api/device/audio/play').length,0);
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
  assert.equal(ui.requests.filter(r=>r.url==='/api/tts').length,0);
  assert.equal(ui.element('transcript').value,'原始问题');
  const rows=ui.element('chat-log').children;
  assert.equal(rows.length,2);
  assert.equal(rows[0].children[1].textContent,'原始问题');
  assert.equal(rows[1].children[1].textContent,'单独的回答');
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
