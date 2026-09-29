import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {JSDOM} from 'jsdom';
import {Epoch} from '../static/pcm.js';
import {createDebugConsole} from '../static/debug-console.js';
import {createExpressionMenu} from '../static/expression-menu.js';
import {createAppearancePicker} from '../static/appearance-picker.js';
const read=file=>fs.readFileSync(new URL('../'+file,import.meta.url),'utf8');
const html=read('static/index.html'),themeCode=read('static/console-theme.js');
async function setup(saved,blocked=false){
  const dom=new JSDOM(html,{url:'http://127.0.0.1:8879/#dialogue',runScripts:'outside-only',pretendToBeVisual:true}),w=dom.window;
  if(saved)w.localStorage.setItem('gork.console-theme',saved);
  if(blocked)Object.defineProperty(w,'localStorage',{get(){throw new Error('storage blocked');}});
  w.eval(themeCode);await new Promise(resolve=>setImmediate(resolve));
  return {dom,w,doc:w.document,get:id=>w.document.getElementById(id)};
}
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
  assert.ok(after.window.document.querySelectorAll('.mantine-Button-root').length>30);
  assert.equal(after.window.document.querySelectorAll('[data-page]').length,7);
  assert.equal(after.window.document.querySelector('.wordmark #header-version')?.textContent,'版本读取中');
  before.window.close();after.window.close();
});
test('theme switch preserves node identity, drafts, history, values, listeners and disabled state',async()=>{
  const ui=await setup(),{get,doc,w}=ui;
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
test('real generated DOM works with the shared controller; theme changes never duplicate requests or avatars',async()=>{
  const ui=await setup(),{w,get}=ui,requests=[];let mounts=0;
  Object.assign(w,{Epoch,TextEncoder,AbortController,AbortSignal,createDebugConsole,createExpressionMenu,createAppearancePicker,
    Recorder:class{stop(){}},WavPlayer:class{stop(){}},
    GorkAvatar:{mount(){mounts++;return {set(){},dispose(){}};}},
    setInterval:()=>0,
    fetch:async(url,options)=>{requests.push({url,options});return {ok:true,json:async()=>({auto_connect_voice:false,voice_url:'http://127.0.0.1:8899',voice_error:{message:'测试离线'},robot:{connected:false},answer:{enabled:false},workspace:{owned:false}})};}});
  w.eval(read('static/gork-catalog.js'));
  w.eval(read('static/app.js').replace(/^import .*;\r?\n/gm,''));await new Promise(resolve=>setImmediate(resolve));
  assert.equal(mounts,1);const baseline=requests.length;
  get('transcript').value='测试草稿';get('transcript').dispatchEvent(new w.Event('input'));
  assert.match(get('count').textContent,/4 \/ 300/);
  get('theme-toggle').click();get('theme-toggle').click();assert.equal(requests.length,baseline);assert.equal(mounts,1);
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
