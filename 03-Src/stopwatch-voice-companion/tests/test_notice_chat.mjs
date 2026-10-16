import test from 'node:test';
import assert from 'node:assert/strict';
import {JSDOM} from 'jsdom';
import {createNoticeChat} from '../static/notice-chat.js';
import {createHeaderTools} from '../static/header-tools.js';
const stamp='2026-10-14T10:00:00Z';
const receipt=(changes={})=>({source:'astra',event_id:'1',accepted_at:stamp,status:'queued',request:{text:'表内金额 100 元'},...changes});
const snapshot=receipts=>({clients:[{source:'astra',label:'造价智算 Astra'}],receipts});
test('receipts ordered, source labels, status updates deduplicated, no status regression',()=>{
  const rows=[],chat=createNoticeChat((...args)=>rows.push(args));
  const data=snapshot([receipt({event_id:'2'}),receipt()]);chat.consume(data);chat.consume(data);
  assert.equal(rows.length,2);assert.equal(rows[0][2].id,'notice:astra:1');
  assert.equal(rows[0][2].source,'造价智算 Astra');assert.match(rows[0][2].timing,/排队中/);
  chat.consume(snapshot([receipt({status:'completed'})]));
  assert.equal(rows.length,3);assert.equal(rows[2][2].id,rows[0][2].id);assert.match(rows[2][2].timing,/已完成/);
  chat.consume(snapshot([receipt()]));assert.equal(rows.length,3);
});
test('clear suppresses old and late snapshots, allows new events; blank expressions skipped',()=>{
  const rows=[],chat=createNoticeChat((...args)=>rows.push(args),()=>Date.parse(stamp)+1000);
  chat.clear();chat.consume(snapshot([receipt(),receipt({event_id:'late'}),receipt({accepted_at:'bad'})]));assert.equal(rows.length,0);
  chat.consume(snapshot([receipt({event_id:'new',accepted_at:'2026-10-14T10:01:00Z'}),receipt({request:{text:''}})]));assert.equal(rows.length,1);
});
function tools(api,options={}){
  const document=new JSDOM('<button id="header-notifications"></button><button id="header-codex"></button>').window.document;
  const reports=[];const toolbar=createHeaderTools({document,api,hasWorkspace:()=>true,acquireWorkspace:async()=>true,onCodex:()=>{},refreshExternal:async()=>{},report:(...args)=>reports.push(args),...options});
  return {toolbar,reports,get:id=>document.getElementById(id)};
}
test('notification toggle pauses/resumes only, failure keeps last confirmed state',async()=>{
  const calls=[],ui=tools(async(path)=>{calls.push(path);if(path.endsWith('pause'))return {paused:true};throw Error('服务暂时不可用');});
  ui.toolbar.paintExternal({paused:false});const button=ui.get('header-notifications');
  await button.onclick();assert.equal(button.getAttribute('aria-checked'),'false');
  await button.onclick();assert.equal(button.getAttribute('aria-checked'),'false');assert.deepEqual(calls,['/external/pause','/external/resume']);assert.equal(ui.reports.at(-1)[1],true);
});
test('Codex shortcut uses latest saved settings and leaves drafts outside request; no forced takeover',async()=>{
  const calls=[],saved={enabled:false,mode:'specific',thread_id:'thread',target:'watch',sound:false,sound_target:'pc',threshold:17,bucket_id:'quota',ring_mode:'hover',drop_step:3,drop_animation:false,history:['private'],quota:{}};
  const ui=tools(async(path,method,body)=>{calls.push({path,method,body});return method==='PUT'?body:saved;});
  ui.toolbar.paintCodex(saved);await ui.get('header-codex').onclick();
  assert.deepEqual(calls[1].body,{...Object.fromEntries(Object.entries(saved).filter(([k])=>!['history','quota'].includes(k))),enabled:true});
  assert.equal(ui.get('header-codex').getAttribute('aria-checked'),'true');
  const blocked=tools(async()=>assert.fail('must not request'),{hasWorkspace:()=>false,acquireWorkspace:async()=>false});blocked.toolbar.paintCodex(saved);await blocked.get('header-codex').onclick();assert.equal(blocked.get('header-codex').getAttribute('aria-checked'),'false');
});
