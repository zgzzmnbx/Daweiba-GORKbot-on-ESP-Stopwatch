import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {JSDOM} from 'jsdom';
import {Epoch} from '../static/pcm.js';
import {createDebugConsole} from '../static/debug-console.js';
import {createExpressionMenu} from '../static/expression-menu.js';
import {createAppearancePicker} from '../static/appearance-picker.js';
import {createWatchChat} from '../static/watch-chat.js';
const answerSetupFixture={prompt_configurable:true,revision:1,key_saved:false,model:'deepseek-flash',system_prompt:'直接回答核心问题。',max_chars:20,default_prompt:'默认简短风格。',default_max_chars:20,effective_prompt:'文字实际提示词。',watch_prompt:'Watch 实际提示词。'};
const read=file=>fs.readFileSync(new URL('../'+file,import.meta.url),'utf8');
const html=read('static/index.html'),themeCode=read('static/console-theme.js');

test('Watch replies retain per-turn voice identity and late polls do not rewrite an older reply',()=>{
  const written=[];const chat=createWatchChat((...args)=>written.push(args));
  const first={id:'first',recognized:'问题一',answer:'回答一',timings:{tts:1},voice:{rendered:'Ethan'}};
  chat.consume({history_id:'fixture',history_revision:1,turns:[first]});
  assert.match(written.at(-1)[2].timing,/音色 Ethan/);
  chat.consume({history_id:'fixture',history_revision:2,turns:[first,{id:'second',answer:'回答二',voice:{rendered:'Cherry'}}]});
  assert.equal(written.length,3);assert.match(written.at(-1)[2].timing,/音色 Cherry/);
  chat.consume({history_id:'fixture',history_revision:1,turns:[{...first,voice:{rendered:'Cherry'}}]});
  assert.equal(written.length,3);
});

test('Watch default enable waits for existing permission/session readiness; failed auto attempt is not retried by each poll',async()=>{
  const dom=new JSDOM(html,{url:'http://127.0.0.1:8879/',runScripts:'outside-only'}),w=dom.window;
  w.eval(read('static/network-ui.js'));let calls=0;
  const api=async(path,method,body)=>{assert.equal(path,'/watch/dialogue');assert.equal(body.enabled,true);calls++;throw Object.assign(new Error('denied'),{code:'ANSWER_UPLOAD_DENIED'});};
  const update=(ready,enabled=true)=>w.GorkNetworkUI.update(null,{enabled:false,stage:'disabled'},api,{enabled},answerSetupFixture,{ready,key:'session-1'});
  update(false);update(true,false);assert.equal(calls,0);
  update(true);await new Promise(yes=>setImmediate(yes));assert.equal(calls,1);
  for(let i=0;i<10;i++)update(true);
  assert.equal(calls,1);assert.match(w.document.getElementById('watch-dialogue-feedback').textContent,/允许向回答服务发送文字/);
  update(false);update(true);await new Promise(yes=>setImmediate(yes));assert.equal(calls,2);
  assert.equal(w.localStorage.length,0,'default intent must not write upload consents');w.close();
});

test('Watch manual off lasts for the current window; reopening defaults on despite an old saved off preference',async()=>{
  let calls=0;
  const first=new JSDOM(html,{url:'http://127.0.0.1:8879/',runScripts:'outside-only'}),w=first.window;
  w.eval(read('static/network-ui.js'));
  const api=async(path,method,body)=>{calls++;return {enabled:body.enabled,stage:body.enabled?'ready':'disabled',turns:[]};};
  w.GorkNetworkUI.update(null,{enabled:false,stage:'disabled'},api,{enabled:true},answerSetupFixture,{ready:true});
  await new Promise(yes=>setImmediate(yes));assert(w.document.getElementById('watch-dialogue-enable').checked);
  w.document.getElementById('watch-dialogue-enable').click();await new Promise(yes=>setImmediate(yes));
  assert.equal(w.localStorage.getItem('gork.watch-dialogue'),null);assert.equal(calls,2);
  for(let i=0;i<10;i++)w.GorkNetworkUI.update(null,{enabled:false,stage:'disabled'},api,{enabled:true},answerSetupFixture,{ready:true,key:'changed-session'});
  await new Promise(yes=>setImmediate(yes));assert.equal(calls,2,'manual off must survive health polls and readiness changes in this window');w.close();
  const second=new JSDOM(html,{url:'http://127.0.0.1:8879/',runScripts:'outside-only'}),v=second.window;
  v.localStorage.setItem('gork.watch-dialogue','false');v.eval(read('static/network-ui.js'));
  v.GorkNetworkUI.update(null,{enabled:false,stage:'disabled'},api,{enabled:true},answerSetupFixture,{ready:true});
  await new Promise(yes=>setImmediate(yes));assert.equal(calls,3);assert(v.document.getElementById('watch-dialogue-enable').checked);v.close();
});

test('prompt draft survives polls; preview is saved content and reset does not write or replace Key',async()=>{
  const dom=new JSDOM(html,{url:'http://127.0.0.1:8879/',runScripts:'outside-only'}),w=dom.window,get=id=>w.document.getElementById(id),calls=[];
  w.eval(read('static/network-ui.js'));
  const api=async(...args)=>{calls.push(args);return {...answerSetupFixture,revision:2,system_prompt:args[2].system_prompt,max_chars:args[2].max_chars,watch_prompt:'新保存的实际提示词',key_saved:true,capability:{enabled:true}};};
  w.GorkNetworkUI.update(null,{enabled:false,stage:'disabled'},api,{enabled:true},{...answerSetupFixture,key_saved:true});
  assert.equal(get('answer-setup-prompt').value,answerSetupFixture.system_prompt);
  assert.equal(get('answer-setup-preview').value,answerSetupFixture.watch_prompt);assert(get('answer-setup-preview').readOnly);
  get('answer-setup-prompt').value='我的简短风格';get('answer-setup-prompt').dispatchEvent(new w.Event('input'));
  get('answer-setup-max-chars').value='12';get('answer-setup-max-chars').dispatchEvent(new w.Event('input'));
  w.GorkNetworkUI.update(null,null,api,{enabled:true},{...answerSetupFixture,key_saved:true,model:'deepseek-v4-pro'});
  assert.equal(get('answer-setup-prompt').value,'我的简短风格');assert.equal(get('answer-setup-max-chars').value,'12');
  assert.equal(calls.length,0);get('answer-setup-save').click();await new Promise(yes=>setImmediate(yes));
  assert.equal(calls[0][2].api_key,'');assert.equal(calls[0][2].system_prompt,'我的简短风格');assert.equal(calls[0][2].max_chars,12);
  assert.equal(get('answer-setup-preview').value,'新保存的实际提示词');
  w.GorkNetworkUI.update(null,null,api,{enabled:true},answerSetupFixture);
  assert.equal(get('answer-setup-preview').value,'新保存的实际提示词','stale health must not undo save');
  assert.equal(get('answer-setup-prompt').value,'我的简短风格');
  get('answer-setup-reset').click();assert.equal(calls.length,1);
  assert.equal(get('answer-setup-prompt').value,answerSetupFixture.default_prompt);assert.equal(get('answer-setup-max-chars').value,'20');
  get('answer-setup-max-chars').value='4';get('answer-setup-save').click();assert.equal(calls.length,1);
  assert.match(get('answer-setup-status').textContent,/5～300/);dom.window.close();
});

test('Watch turns enter current chat safely; polls update rather than duplicate, repeats remain distinct and stale cleared snapshots are ignored',async()=>{
  const dom=new JSDOM(html,{url:'http://127.0.0.1:8879/',runScripts:'outside-only'}),w=dom.window,get=id=>w.document.getElementById(id);
  Object.assign(w,{Epoch,TextEncoder,AbortController,AbortSignal,createDebugConsole,createExpressionMenu,createAppearancePicker,createWatchChat,
    Recorder:class{stop(){}},WavPlayer:class{stop(){}},GorkAvatar:{mount(){return {set(){},dispose(){}};}},setInterval:()=>0,
    fetch:async()=>({ok:true,json:async()=>({auto_connect_voice:false,voice_url:'http://127.0.0.1:8899',robot:{connected:false},answer:{enabled:false},workspace:{owned:false}})})});
  w.eval(read('static/gork-catalog.js'));
  w.eval(read('static/app.js').replace(/^import .*;\r?\n/gm,'')+'\nwindow.consumeWatch=s=>watchChat.consume(s);window.clearWatch=s=>{watchChat.clear(s);watchRows.clear();$("chat-log").replaceChildren();};');
  await new Promise(yes=>setImmediate(yes));
  const snapshot={history_id:'fixture',history_revision:1,turns:[{id:'one',recognized:'你好',answer:'',timings:{asr:.07}}]};
  w.consumeWatch(snapshot);w.consumeWatch(snapshot);
  assert.equal(get('chat-log').querySelectorAll('.chat-message').length,1);
  snapshot.history_revision=2;snapshot.turns[0].answer='<img src=x onerror=alert(1)>';snapshot.turns[0].timings.answer=.65;
  w.consumeWatch(snapshot);w.consumeWatch(snapshot);
  assert.equal(get('chat-log').querySelectorAll('.chat-message').length,2);assert.equal(get('chat-log').querySelector('img'),null);
  snapshot.history_revision=3;snapshot.turns[0].answer='新的简短回答';w.consumeWatch(snapshot);
  assert.equal(get('chat-log').querySelectorAll('.chat-message').length,2);assert.match(get('chat-log').textContent,/新的简短回答/);
  snapshot.history_revision=4;snapshot.turns.push({id:'two',recognized:'你好',answer:'我在。',timings:{}});w.consumeWatch(snapshot);
  assert.equal(get('chat-log').querySelectorAll('.chat-message').length,4);
  w.clearWatch({history_id:'fixture',history_revision:5});w.consumeWatch(snapshot);
  assert.equal(get('chat-log').children.length,0,'late health response must not restore a cleared conversation');
  w.consumeWatch({...snapshot,history_revision:6,turns:[{id:'three',recognized:'新问题',answer:'新回答',timings:{}}]});
  assert.equal(get('chat-log').querySelectorAll('.chat-message').length,2);dom.window.close();
});
test('USB provisioning is selected, clears password and submits only after explicit click',async()=>{
  const dom=new JSDOM(html,{url:'http://127.0.0.1:8879/',runScripts:'outside-only'}),w=dom.window,doc=w.document;
  const calls=[];w.eval(read('static/network-ui.js'));
  w.GorkNetworkUI.update({revision:3,route:'offline',policy:'auto_wifi_first',power:'auto'},null,async(...args)=>{calls.push(args);return {};});
  assert.equal(doc.getElementById('network-provision-via').value,'usb');
  assert.equal(calls.length,0);
  doc.getElementById('network-password').value='dummy-private-input';doc.getElementById('network-configure').click();
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(doc.getElementById('network-password').value,'');
  assert.equal(calls.length,1);assert.equal(calls[0][2].via,'usb');assert.equal(calls[0][2].revision,3);
  assert(!doc.body.textContent.includes('dummy-private-input'));dom.window.close();
});
async function setup(saved,blocked=false,savedColor,savedScheme){
  const dom=new JSDOM(html,{url:'http://127.0.0.1:8879/#dialogue',runScripts:'outside-only',pretendToBeVisual:true}),w=dom.window;
  if(saved)w.localStorage.setItem('gork.console-theme',saved);
  if(savedColor)w.localStorage.setItem('gork.console-color',savedColor);
  if(savedScheme)w.localStorage.setItem('gork.console-scheme',savedScheme);
  if(blocked)Object.defineProperty(w,'localStorage',{get(){throw new Error('storage blocked');}});
  w.eval(themeCode);await new Promise(resolve=>setImmediate(resolve));
  return {dom,w,doc:w.document,get:id=>w.document.getElementById(id)};
}

async function startupWatchController({consent=true,busy=false,answer=true}={}){
  const ui=await setup(),{w}=ui,requests=[];
  let enabled=false;
  w.localStorage.setItem('gork.watch-dialogue','false');
  w.localStorage.setItem('gork.answer-consent',String(consent));
  Object.assign(w,{Epoch,TextEncoder,AbortController,AbortSignal,createDebugConsole,createExpressionMenu,createAppearancePicker,createWatchChat,
    Recorder:class{stop(){}},WavPlayer:class{stop(){}},
    GorkAvatar:{mount(){return {set(){},dispose(){}};}},setInterval:()=>0,
    fetch:async(url,options={})=>{
      requests.push({url,options});
      if(url==='/api/session'&&busy)return {ok:false,status:409,json:async()=>({error:{code:'SESSION_BUSY',message:'另一窗口正在使用'}})};
      if(url==='/api/watch/dialogue')enabled=JSON.parse(options.body).enabled;
      // Same shape as the production health endpoint: no workspace ownership field.
      const health={version:'0.20.22-dev',auto_connect_voice:true,voice_url:'http://127.0.0.1:8899',voice:{ready:true},
        robot:{connected:true},watch_dialogue:{enabled,stage:enabled?'ready':'disabled'},answer:{enabled:answer},
        answer_setup:answerSetupFixture,capabilities:{protocol_version:1,tts:{speakers:[{id:3,label:'本地'}]}}};
      return {ok:true,json:async()=>url==='/api/health'?health:url==='/api/watch/dialogue'?health.watch_dialogue:{generation:0}};
    }});
  w.eval(read('static/gork-catalog.js'));w.eval(read('static/network-ui.js'));
  w.eval(read('static/app.js').replace(/^import .*;\r?\n/gm,'')+'\nwindow.pollHealthForTest=refresh;');
  for(let i=0;i<5;i++)await new Promise(resolve=>setTimeout(resolve,5));
  return {...ui,requests};
}

test('production startup enables Watch with the real health shape after acquiring session and applying settings',async()=>{
  const ui=await startupWatchController(),{w,get,requests}=ui;
  try{
    assert.equal(requests.filter(r=>r.url==='/api/session').length,1,'startup acquires the existing session');
    assert.equal(requests.filter(r=>r.url==='/api/settings').length,1,'startup applies the saved settings');
    const enables=requests.filter(r=>r.url==='/api/watch/dialogue');
    assert.equal(enables.length,1);assert.equal(JSON.parse(enables[0].options.body).enabled,true);
    assert(get('watch-dialogue-enable').checked);assert.match(get('watch-dialogue-status').textContent,/等待按键/);
    for(let i=0;i<3;i++)await w.pollHealthForTest();
    assert.equal(requests.filter(r=>r.url==='/api/watch/dialogue').length,1,'polling does not duplicate enable');
    get('watch-dialogue-enable').click();await new Promise(resolve=>setImmediate(resolve));
    for(let i=0;i<3;i++)await w.pollHealthForTest();
    assert.equal(requests.filter(r=>r.url==='/api/watch/dialogue').length,2,'manual off remains off for this window');
    assert.equal(get('watch-dialogue-enable').checked,false);
    assert(!requests.some(r=>/\/(asr|tts|answer|device\/audio)/.test(r.url)),'startup never captures or sends a question');
  }finally{w.close();}
});

test('production startup does not enable Watch without consent, session ownership or answer capability',async()=>{
  for(const options of [{consent:false},{busy:true},{answer:false}]){
    const ui=await startupWatchController(options);
    try{
      await ui.w.pollHealthForTest();await new Promise(resolve=>setImmediate(resolve));
      assert.equal(ui.requests.filter(r=>r.url==='/api/watch/dialogue').length,0,JSON.stringify(options));
      assert.equal(ui.get('watch-dialogue-enable').checked,false);
      if(options.consent===false)assert.equal(ui.w.localStorage.getItem('gork.answer-consent'),'false');
    }finally{ui.w.close();}
  }
});
test('network status describes each transport and preserves open forms and focused drafts',()=>{
  const dom=new JSDOM(html,{url:'http://127.0.0.1:8879/',runScripts:'outside-only'}),w=dom.window,doc=w.document,get=id=>doc.getElementById(id),calls=[];
  w.eval(read('static/network-ui.js'));
  const api=async(...args)=>{calls.push(args);return {};};
  const network={revision:5,route:'wifi',wifi_connected:true,ble_connected:false,address:'10.33.72.225',policy:'auto_wifi_first',power:'auto',device:{source:'unknown',effective_power:1,state:'authenticated PC'}};
  w.GorkNetworkUI.update(network,{enabled:false,stage:'disabled'},api);
  assert.equal(get('network-state').textContent,'Wi-Fi 已连接');
  assert.equal(get('network-ble-state').textContent,'未连接');
  assert.equal(get('network-power-state').textContent,'未知 / 性能');
  assert.equal(get('network-current-address').textContent,'10.33.72.225');
  assert(!get('network-detail').textContent.includes('authenticated PC'));
  assert(get('network-feedback').hidden);assert(!get('network-provision').open);
  assert(get('network-ssid').classList.contains('mantine-Input-input'));
  assert(get('network-password').classList.contains('mantine-Input-input'));
  get('network-provision').open=true;get('network-policy').focus();get('network-policy').value='wifi_only';get('network-ssid').value='local draft';
  w.GorkNetworkUI.update({...network,route:'offline',wifi_connected:false,error:'热点暂时不可用'},null,api);
  assert.equal(get('network-state').textContent,'设备离线');assert.equal(get('network-detail').textContent,'热点暂时不可用');
  assert.equal(get('network-policy').value,'wifi_only');assert.equal(get('network-ssid').value,'local draft');assert(get('network-provision').open);
  assert.equal(calls.length,0,'state refresh must never reconnect or provision');dom.window.close();
});
test('Watch control is inside composer with no duplicate result panel and keeps help folded',async()=>{
  const dom=new JSDOM(html,{url:'http://127.0.0.1:8879/',runScripts:'outside-only'}),w=dom.window,get=id=>w.document.getElementById(id),calls=[];
  w.eval(read('static/network-ui.js'));const api=async(...args)=>{calls.push(args);return {};};
  w.GorkNetworkUI.update(null,{enabled:false,stage:'disabled'},api);
  assert(w.document.querySelector('.composer .watch-dialogue'));assert.equal(get('watch-dialogue-results'),null);assert(!get('watch-dialogue-enable').checked);
  get('watch-dialogue-enable').click();await new Promise(resolve=>setImmediate(resolve));
  assert.deepEqual(JSON.parse(JSON.stringify(calls)),[['/watch/dialogue','POST',{enabled:true}]]);
  w.GorkNetworkUI.update(null,{enabled:true,stage:'ready'},api);
  assert.equal(get('watch-dialogue-status').textContent,'等待按键');assert(get('watch-dialogue-shorten').hidden);assert(!w.document.querySelector('.watch-dialogue-help').open);
  w.GorkNetworkUI.update(null,{enabled:true,stage:'speech_not_played',recognized:'你好',answer:'<img src=x onerror=alert(1)>',timings:{asr:.25}},api);
  assert(!get('watch-dialogue-shorten').hidden);assert(!w.document.querySelector('.watch-dialogue-help').open);
  assert(!w.document.body.innerHTML.includes('<img src="x"'),'results are no longer duplicated in the control');
  w.document.querySelector('.watch-dialogue-help').open=true;
  w.GorkNetworkUI.update(null,{enabled:false,stage:'cancelled',recognized:'你好'},api);
  assert(w.document.querySelector('.watch-dialogue-help').open);assert.equal(calls.length,1);dom.window.close();
});
test('Watch enable blocks missing AI and keeps request failures beside the switch across polls',async()=>{
  const dom=new JSDOM(html,{url:'http://127.0.0.1:8879/',runScripts:'outside-only'}),w=dom.window,get=id=>w.document.getElementById(id);
  w.eval(read('static/network-ui.js'));
  let reject,resolve,calls=0;
  const api=()=>{calls++;return new Promise((yes,no)=>{resolve=yes;reject=no;});};
  const disabled={enabled:false,stage:'disabled'},ready={enabled:true,stage:'ready',turns:[]};
  w.GorkNetworkUI.update(null,disabled,api,{enabled:false,reason:'未配置回答服务'});
  assert(get('watch-dialogue-enable').disabled);assert(!get('watch-dialogue-feedback').hidden);
  assert.match(get('watch-dialogue-feedback').textContent,/未配置回答服务/);
  get('watch-dialogue-enable').click();assert.equal(calls,0,'blocked control cannot send an enable request');
  w.GorkNetworkUI.update(null,disabled,api,{enabled:true});get('watch-dialogue-enable').click();
  assert.equal(calls,1);assert(get('watch-dialogue-enable').disabled);assert(get('watch-dialogue-enable').checked);
  w.GorkNetworkUI.update(null,disabled,api,{enabled:true});
  assert(get('watch-dialogue-enable').checked,'health polling must not overwrite pending user intent');
  assert.match(get('watch-dialogue-status').textContent,/正在更新/);
  reject(Object.assign(new Error('dummy-secret-provider-message'),{code:'ANSWER_UPLOAD_DENIED'}));
  await new Promise(yes=>setImmediate(yes));
  assert(!get('watch-dialogue-enable').checked);assert(!get('watch-dialogue-enable').disabled);
  assert.match(get('watch-dialogue-feedback').textContent,/允许向回答服务发送文字/);
  w.GorkNetworkUI.update(null,disabled,api,{enabled:true});
  assert.match(get('watch-dialogue-feedback').textContent,/允许向回答服务发送文字/);
  assert(!w.document.body.textContent.includes('dummy-secret-provider-message'));
  get('watch-dialogue-enable').click();resolve(ready);await new Promise(yes=>setImmediate(yes));
  assert(get('watch-dialogue-enable').checked);assert(get('watch-dialogue-feedback').hidden);
  assert.equal(get('watch-dialogue-status').textContent,'等待按键');
  get('watch-dialogue-enable').click();reject(new Error('offline'));await new Promise(yes=>setImmediate(yes));
  assert(get('watch-dialogue-enable').checked,'a rejected stop must not claim delegation is disabled');
  assert(!get('watch-dialogue-feedback').hidden);dom.window.close();
});
test('DeepSeek key is sent only by explicit save, cleared immediately and never rendered or persisted in browser storage',async()=>{
  const dom=new JSDOM(html,{url:'http://127.0.0.1:8879/',runScripts:'outside-only'}),w=dom.window,get=id=>w.document.getElementById(id),calls=[];
  w.eval(read('static/network-ui.js'));
  const api=async(...args)=>{calls.push(args);return {...answerSetupFixture,capability:{enabled:true},key_saved:true};};
  w.GorkNetworkUI.update(null,{enabled:false,stage:'disabled'},api,{enabled:false,reason:'未配置回答服务'},answerSetupFixture);
  assert.equal(calls.length,0);assert(get('watch-dialogue-enable').disabled);
  get('answer-setup-key').value='dummy-private-key';get('answer-setup-save').click();
  assert.equal(get('answer-setup-key').value,'');await new Promise(yes=>setImmediate(yes));
  assert.equal(calls.length,1);assert.equal(calls[0][0],'/answer/config');assert.equal(calls[0][1],'POST');
  assert.equal(calls[0][2].api_key,'dummy-private-key');assert(!get('watch-dialogue-enable').disabled);
  assert(!w.document.body.textContent.includes('dummy-private-key'));assert.equal(w.localStorage.length,0);
  assert.equal(get('answer-setup-key').type,'password');assert(get('answer-setup-key').classList.contains('mantine-Input-input'));
  assert.match(w.document.querySelector('.watch-key-guide').textContent,/G2 \/ A/);dom.window.close();
});
test('AI config refuses old backend before sending Key, names missing endpoint and preserves in-flight save',async()=>{
  const dom=new JSDOM(html,{url:'http://127.0.0.1:8879/',runScripts:'outside-only'}),w=dom.window,get=id=>w.document.getElementById(id);
  w.eval(read('static/network-ui.js'));let calls=0,finish;
  const api=()=>{calls++;return new Promise((yes,no)=>{finish=no;});};
  const watch={enabled:false,stage:'disabled'},answer={enabled:false},setup=answerSetupFixture;
  w.GorkNetworkUI.update(null,watch,api,answer);
  get('answer-setup-key').value='dummy-key-stays-local';get('answer-setup-save').click();
  assert.equal(calls,0);assert(get('answer-setup-save').disabled);
  assert.equal(get('answer-setup-key').value,'dummy-key-stays-local');
  assert.match(get('answer-setup-status').textContent,/系统托盘/);assert.match(get('answer-setup-status').textContent,/退出/);
  w.GorkNetworkUI.update(null,watch,api,answer,setup);get('answer-setup-save').click();
  assert.equal(calls,1);assert.equal(get('answer-setup-key').value,'');
  w.GorkNetworkUI.update(null,watch,api,answer,setup);
  assert(get('answer-setup-save').disabled,'polls must not enable a second concurrent save');
  assert.match(get('answer-setup-status').textContent,/正在保存/);
  finish(Object.assign(new Error('private-upstream-error'),{status:404}));await new Promise(yes=>setImmediate(yes));
  assert.match(get('answer-setup-status').textContent,/后台尚未加载/);assert(get('answer-setup-save').disabled);
  assert(!w.document.body.textContent.includes('private-upstream-error'));dom.window.close();
});
test('BLE card never reports Wi-Fi as BLE connected or presents a stale failure as current connectivity',()=>{
  const dom=new JSDOM(html,{runScripts:'outside-only'}),w=dom.window,get=id=>w.document.getElementById(id);
  const source=read('static/app.js'),start=source.indexOf('function paintRobot(robot)'),end=source.indexOf('\nasync function previewSound',start);
  w.$=get;w.debugConsole={push(){}};w.render=()=>{};w.workspace=true;
  w.eval('let robotConnected=false;'+source.slice(start,end));
  w.paintRobot({connected:true,enabled:true,error:'没有符合策略的已认证通道',network:{ble_connected:false,wifi_connected:true}});
  assert.equal(get('robot-status').textContent,'未连接');assert(!get('receipt').textContent.includes('没有符合策略'));
  w.paintRobot({connected:true,enabled:true,receipt:'OK:TEXT',network:{ble_connected:true}});
  assert.equal(get('robot-status').textContent,'已连接');assert.match(get('receipt').textContent,/OK:TEXT/);dom.window.close();
});
test('repeated Wi-Fi health polls retain BLE diagnostics without reporting device operations as failed',()=>{
  const dom=new JSDOM(html,{url:'http://127.0.0.1:8879/',runScripts:'outside-only'}),w=dom.window,get=id=>w.document.getElementById(id);
  const source=read('static/app.js'),start=source.indexOf('function paintRobot(robot)'),end=source.indexOf('\nasync function previewSound',start);
  w.$=get;w.debugConsole=createDebugConsole(w.document,w.localStorage);w.render=()=>{};w.workspace=true;
  w.eval('let robotConnected=false;'+source.slice(start,end));
  const status={connected:true,enabled:true,error:'',operation_error:'',ble_error:'BLE GATT discovery failed',receipt:'OK:TEXT',network:{route:'wifi',ble_connected:false,wifi_connected:true}};
  for(let i=0;i<100;i++)w.paintRobot(status);
  assert.equal(get('debug-log').children.length,4,'SYS + connection + receipt + BLE fault only once');
  assert(!get('debug-log').textContent.includes('设备操作异常'));
  assert(get('watch-diagnostics').textContent.includes('BLE GATT discovery failed'));
  assert.equal(get('robot-status').textContent,'未连接');assert(get('receipt').textContent.includes('OK:TEXT'));
  w.paintRobot({...status,error:'command timed out',operation_error:'command timed out'});
  assert.equal(get('debug-log').children.length,5);assert(get('debug-log').textContent.includes('设备操作异常'));
  assert(get('watch-diagnostics').textContent.includes('command timed out'));
  w.paintRobot({...status,ble_error:'',network:{...status.network,ble_connected:true}});
  assert.equal(get('debug-log').children.length,7);assert.equal(get('robot-status').textContent,'已连接');
  assert(!get('watch-diagnostics').textContent.includes('GATT'));
  w.paintRobot({...status,connected:false,network:{route:'offline',wifi_connected:false,ble_connected:false}});
  assert(get('debug-log').textContent.includes('StopWatch 未连接'));dom.window.close();
});
test('Mantine shell keeps every legacy control once, with compatible native types and strict CSP',()=>{
  const before=new JSDOM(read('ui/console.html')),after=new JSDOM(html);
  for(const old of before.window.document.querySelectorAll('[id]')){
    const found=after.window.document.querySelectorAll(`[id="${old.id}"]`);assert.equal(found.length,1,old.id);
    if(['INPUT','SELECT','TEXTAREA','BUTTON','CANVAS','DETAILS'].includes(old.tagName)){
      assert.equal(found[0].tagName,old.tagName,old.id);if(old.tagName==='INPUT')assert.equal(found[0].type,old.type,old.id);
    }
  }
  assert.equal(after.window.document.querySelectorAll('[style],style,[data-disabled]').length,0);
  for(const el of after.window.document.querySelectorAll('script[src],link[href]'))assert.match(el.getAttribute('src')||el.getAttribute('href'),/^\/static\//);
  const sourceScripts=[...before.window.document.querySelectorAll('body script[src]')].map(n=>n.getAttribute('src'));
  const generatedScripts=[...after.window.document.querySelectorAll('body script[src]')].map(n=>n.getAttribute('src'));
  assert.deepEqual(generatedScripts,sourceScripts,'UI build must preserve the custom player, previews and dependency order');
  assert(sourceScripts.includes('/static/motion/desktop-adapter.js'));
  assert.ok(after.window.document.querySelectorAll('.mantine-Button-root').length>30);
  assert.equal(after.window.document.querySelectorAll('[data-page]').length,9);
  assert.equal(after.window.document.querySelector('.wordmark #header-version')?.textContent,'版本读取中');
  before.window.close();after.window.close();
});
test('theme switch preserves node identity, drafts, history, values, listeners and disabled state',async()=>{
  const ui=await setup(),{get,doc,w}=ui;
  assert.equal(get('theme-toggle').closest('#page-settings')?.id,'page-settings');
  assert.equal(doc.querySelector('.app-header #theme-toggle'),null);
  assert.equal(get('theme-color-menu').closest('.app-header')?.className,'app-header');
  const draft=get('transcript'),face=get('gork-face'),history=get('chat-log');draft.value='主题切换保留草稿';
  history.textContent='已有的对话';get('tts').value='local';get('auto-read').checked=false;get('speak').disabled=false;
  get('appearance-menu').open=true;let called=0;draft.addEventListener('input',()=>called++);
  for(let i=0;i<8;i++)get('theme-toggle').click();
  assert.equal(doc.documentElement.dataset.consoleTheme,'mantine');assert.equal(get('transcript'),draft);assert.equal(get('gork-face'),face);assert.equal(get('chat-log'),history);
  assert.equal(draft.value,'主题切换保留草稿');assert.equal(history.textContent,'已有的对话');assert.equal(get('tts').value,'local');assert.equal(get('auto-read').checked,false);assert.equal(get('speak').disabled,false);assert.equal(get('appearance-menu').open,true);
  draft.dispatchEvent(new w.Event('input'));assert.equal(called,1);assert.equal(w.location.hash,'#dialogue');
  ui.dom.window.close();
});
test('theme preference restores before app startup and blocked storage does not break switching',async()=>{
  for(const [saved,expected] of [['classic','classic'],['mantine','mantine'],['unknown','mantine']]){
    const ui=await setup(saved);assert.equal(ui.doc.documentElement.dataset.consoleTheme,expected);
    assert.equal(ui.get('classic-style').media,expected==='classic'?'all':'not all');
    assert.equal(ui.get('mantine-components').media,expected==='mantine'?'all':'not all');
    ui.get('theme-toggle').click();assert.equal(ui.w.localStorage.getItem('gork.console-theme'),expected==='classic'?'mantine':'classic');ui.w.close();
  }
  const ui=await setup(undefined,true);ui.get('theme-toggle').click();assert.equal(ui.doc.documentElement.dataset.consoleTheme,'classic');ui.w.close();
});
test('dark mode persists with palette, restores on load, and preserves classic appearance',async()=>{
  const ui=await setup('mantine',false,'blue','dark'),{w,doc,get}=ui;
  assert.equal(doc.documentElement.dataset.consoleScheme,'dark');
  assert.equal(doc.documentElement.dataset.mantineColorScheme,'dark');
  assert.equal(get('color-scheme-toggle').textContent,'浅色模式');
  assert.equal(get('color-scheme-toggle').getAttribute('aria-pressed'),'true');
  const draft=get('transcript');draft.value='暗色草稿';
  get('theme-toggle').click();
  assert.equal(doc.documentElement.dataset.consoleTheme,'classic');
  assert.equal(doc.documentElement.dataset.mantineColorScheme,'light');
  get('theme-toggle').click();
  assert.equal(doc.documentElement.dataset.mantineColorScheme,'dark');
  get('color-scheme-toggle').click();
  assert.equal(doc.documentElement.dataset.consoleScheme,'light');
  assert.equal(w.localStorage.getItem('gork.console-scheme'),'light');
  assert.equal(get('transcript'),draft);assert.equal(draft.value,'暗色草稿');
  get('theme-toggle').click();get('color-scheme-toggle').click();
  assert.equal(doc.documentElement.dataset.consoleTheme,'mantine');
  assert.equal(doc.documentElement.dataset.mantineColorScheme,'dark');
  assert.equal(doc.documentElement.dataset.consoleColor,'blue');
  assert.equal(w.localStorage.getItem('gork.console-scheme'),'dark');w.close();
  const invalid=await setup(undefined,false,undefined,'unknown');
  assert.equal(invalid.doc.documentElement.dataset.consoleScheme,'light');invalid.w.close();
  const blocked=await setup(undefined,true);
  blocked.get('color-scheme-toggle').click();
  assert.equal(blocked.doc.documentElement.dataset.mantineColorScheme,'dark');blocked.w.close();
});
test('palette selection persists, changes classic to Mantine, and preserves the live controls',async()=>{
  const ui=await setup('classic',false,'blue'),{w,doc,get}=ui;
  assert.equal(doc.documentElement.dataset.consoleColor,'blue');
  assert.equal(doc.querySelector('input[name="console-color"]:checked').value,'blue');
  const draft=get('transcript'),menu=get('theme-color-menu');draft.value='保留文字';menu.open=true;
  const violet=doc.querySelector('input[name="console-color"][value="violet"]');violet.checked=true;
  violet.dispatchEvent(new w.Event('change',{bubbles:true}));
  assert.equal(doc.documentElement.dataset.consoleTheme,'mantine');
  assert.equal(doc.documentElement.dataset.consoleColor,'violet');
  assert.equal(w.localStorage.getItem('gork.console-color'),'violet');
  assert.equal(w.localStorage.getItem('gork.console-theme'),'mantine');
  assert.equal(menu.open,false);assert.equal(get('transcript'),draft);assert.equal(draft.value,'保留文字');
  get('theme-toggle').click();assert.equal(doc.documentElement.dataset.consoleTheme,'classic');
  get('theme-toggle').click();assert.equal(doc.documentElement.dataset.consoleColor,'violet');
  w.close();
  const invalid=await setup(undefined,false,'#ff0000');
  assert.equal(invalid.doc.documentElement.dataset.consoleColor,'gork');invalid.w.close();
  const blocked=await setup(undefined,true);
  const blue=blocked.doc.querySelector('input[name="console-color"][value="blue"]');blue.checked=true;blue.dispatchEvent(new blocked.w.Event('change',{bubbles:true}));
  assert.equal(blocked.doc.documentElement.dataset.consoleColor,'blue');blocked.w.close();
});
test('real generated DOM works with the shared controller; theme changes never duplicate requests or avatars',async()=>{
  const ui=await setup(),{w,get}=ui,requests=[];let mounts=0,mainMounts=0;
  Object.assign(w,{Epoch,TextEncoder,AbortController,AbortSignal,createDebugConsole,createExpressionMenu,createAppearancePicker,createWatchChat,
    Recorder:class{stop(){}},WavPlayer:class{stop(){}},
    GorkAvatar:{mount(canvas){mounts++;if(canvas.id==='gork-face')mainMounts++;return {set(){},dispose(){}};}},
    setInterval:()=>0,
    fetch:async(url,options)=>{requests.push({url,options});return {ok:true,json:async()=>({auto_connect_voice:false,voice_url:'http://127.0.0.1:8899',voice_error:{message:'测试离线'},robot:{connected:false},answer:{enabled:false},workspace:{owned:false}})};}});
  w.eval(read('static/gork-catalog.js'));
  w.eval(read('static/app.js').replace(/^import .*;\r?\n/gm,'')+'\nwindow.setHeaderTestState=(voice,watch)=>{connected=voice;robotConnected=watch;render("ready");};');await new Promise(resolve=>setImmediate(resolve));
  assert.equal(mainMounts,1);assert.equal(mounts,1+get('expression-grid').children.length);const baseline=requests.length,initialMounts=mounts;
  assert.equal(get('global-voice').dataset.state,'offline');assert.equal(get('global-watch').dataset.state,'offline');
  w.setHeaderTestState(true,true);
  assert.equal(get('global-voice').dataset.state,'ready');assert.equal(get('global-watch').dataset.state,'ready');
  assert.match(get('global-watch').textContent,/已连接/);
  w.setHeaderTestState(false,false);
  assert.equal(get('global-voice').dataset.state,'offline');assert.equal(get('global-watch').dataset.state,'offline');
  get('transcript').value='测试草稿';get('transcript').dispatchEvent(new w.Event('input'));
  assert.match(get('count').textContent,/4 \/ 300/);
  get('theme-toggle').click();get('theme-toggle').click();assert.equal(requests.length,baseline);assert.equal(mounts,initialMounts);assert.equal(mainMounts,1);
  const blue=get('theme-color-menu').querySelector('input[value="blue"]');blue.checked=true;blue.dispatchEvent(new w.Event('change',{bubbles:true}));
  assert.equal(w.document.documentElement.dataset.consoleColor,'blue');assert.equal(requests.length,baseline);assert.equal(mounts,initialMounts);assert.equal(get('transcript').value,'测试草稿');
  get('auto-read').click();assert.equal(w.localStorage.getItem('gork.auto-read'),'false');
  get('output-mode').value='bubble';get('output-mode').dispatchEvent(new w.Event('change'));assert.equal(get('bubble-target-control').hidden,false);
  await get('character-acquire').onclick();get('bubble-target').value='desktop';get('bubble-target').dispatchEvent(new w.Event('change'));
  assert.equal(get('speak').disabled,false);assert.equal(get('speak').hasAttribute('data-disabled'),false);
  await get('speak').onclick();await new Promise(resolve=>setImmediate(resolve));
  const bubbleCalls=requests.filter(r=>r.url==='/api/character/bubble');assert.equal(bubbleCalls.length,1);
  assert.equal(JSON.parse(bubbleCalls[0].options.body).text,'测试草稿');
  const transcript=get('chat-log').textContent;assert.match(transcript,/测试草稿/);
  const sent=requests.length;get('theme-toggle').click();assert.equal(get('chat-log').textContent,transcript);assert.equal(requests.length,sent);
  w.location.hash='#settings';w.dispatchEvent(new w.Event('hashchange'));assert.equal(get('page-settings').hidden,false);assert.equal(get('page-dialogue').hidden,true);
  get('text-consent').click();await new Promise(resolve=>setImmediate(resolve));assert.equal(w.localStorage.getItem('gork.text-consent'),'false');assert.equal(get('tts').value,'local');
  ui.w.close();
});
