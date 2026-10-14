import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {JSDOM} from 'jsdom';
import {createExternalUI} from '../static/external-ui.js';
const html=fs.readFileSync(new URL('../static/index.html',import.meta.url),'utf8');
function fixture(){
 const dom=new JSDOM(html,{url:'http://127.0.0.1:8766/#external'}),doc=dom.window.document,calls=[];
 let data={clients:[],paused:false,pending:0,current:{},receipts:[],current_sound_target:'watch'};
 const api=async(path,method='GET',body)=>{calls.push({path,method,body});if(path==='/external/overview')return data;if(path==='/external/clients')return {token:'test-private-token'};return {}};
 const ui=createExternalUI({document:doc,api,hasWorkspace:()=>true,acquireWorkspace:async()=>true,clipboard:async text=>calls.push({copy:text})});
 return {dom,doc,ui,calls,get:id=>doc.getElementById(id),setData:value=>{data=value}};
}
test('program defaults disabled with no audio, editing preserves drafts during polling',async()=>{
 const f=fixture();f.get('external-add').click();
 assert.equal(f.get('external-enabled').checked,false);assert.equal(f.get('external-speech-watch').checked,false);
 f.get('external-source').value='astra';f.get('external-label').value='智算';
 await f.ui.refresh();assert.equal(f.get('external-label').value,'智算');
 await f.get('external-editor').onsubmit({preventDefault(){}});
 assert.deepEqual(f.calls.find(c=>c.method==='POST').body,{source:'astra',label:'智算',enabled:false,display_targets:['desktop','watch'],speech_targets:[],max_priority:2});
 assert.equal(f.get('external-token').type,'password');assert.equal(f.get('external-token').value,'test-private-token');
 assert.equal(f.dom.window.localStorage.length,0);assert(!f.get('external-feedback').textContent.includes('test-private-token'));
 f.ui.destroy();assert.equal(f.get('external-token').value,'');f.dom.window.close();
});
test('receipt uses text nodes, separate delivery results and owner scoped cancellation',async()=>{
 const f=fixture(),receipt={source:'astra',event_id:'event:1',stage:'opaque',task_id:'t',attempt:'a',accepted_at:new Date().toISOString(),status:'partial',request:{text:'<img onerror=attack>'},delivery:{desktop:'displayed',watch:'offline',speech:'upload_not_allowed'}};
 f.ui.paint({clients:[{source:'astra',label:'智算',enabled:true,display_targets:['desktop'],speech_targets:[]}],paused:true,current:{},receipts:[receipt]});
 assert.equal(f.get('external-receipts').querySelector('img'),null);
 assert.match(f.get('external-receipts').textContent,/Watch：未连接/);
 assert.equal(f.get('external-resume').hidden,false);
 f.get('external-receipts').querySelector('button').click();await new Promise(r=>setTimeout(r));
 assert(f.calls.some(c=>c.path==='/external/owner-cancel'&&c.body.source==='astra'&&c.body.event_id==='event:1'));
 f.ui.destroy();f.dom.window.close();
});
test('invalid source never submits, conflicts leave editable policy intact',async()=>{
 const f=fixture();f.get('external-add').click();f.get('external-source').value='Bad Source';f.get('external-label').value='名称';
 await f.get('external-editor').onsubmit({preventDefault(){}});assert.equal(f.calls.length,0);assert.equal(f.get('external-editor').hidden,false);
 f.ui.destroy();f.dom.window.close();
});

test('legacy source conflict has a visible setup action without changing permissions',()=>{
 const f=fixture();
 f.ui.paint({clients:[{source:'astra',label:'智算',enabled:false,display_targets:['desktop','watch'],speech_targets:[]}],poll_source:'astra',current:{},receipts:[]});
 assert.match(f.get('external-clients').textContent,/先关闭兼容轮询/);
 const action=[...f.get('external-clients').querySelectorAll('button')].find(b=>b.textContent==='打开兼容轮询设置');
 assert(action);action.click();assert.equal(f.get('sentinel-legacy').open,true);
 assert.equal(f.calls.length,0);assert.equal(f.get('external-enabled').checked,false);
 f.ui.paint({clients:[{source:'astra',label:'智算',enabled:false,display_targets:['desktop','watch'],speech_targets:[]}],poll_source:null,current:{},receipts:[]});
 assert.match(f.get('external-clients').textContent,/调试信号才能被接收/);
 assert(!f.get('external-clients').textContent.includes('旧轮询正在使用'));
 f.ui.destroy();f.dom.window.close();
});
