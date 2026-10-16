import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {JSDOM} from 'jsdom';
import {createWatchVolume} from '../static/watch-volume.js';
const html=fs.readFileSync(new URL('../static/index.html',import.meta.url),'utf8');
function setup(api){
 const dom=new JSDOM(html),document=dom.window.document,get=id=>document.getElementById(id),messages=[];
 const ui=createWatchVolume({document,api,report:(...args)=>messages.push(args)});
 return {dom,get,ui,messages,ready:{connected:true,owned:true,busy:false,route:'wifi'}};
}
test('both Watch sliders sync on drag; only release sends once and PC slider stays unchanged',async()=>{
 const calls=[],f=setup(async(...args)=>{calls.push(args);return 'OK:SOUND';});f.ui.update(f.ready);
 assert.equal(f.get('header-watch-volume-label').textContent,'—');assert.equal(calls.length,0);
 const a=f.get('header-watch-volume'),b=f.get('sound-volume'),pc=f.get('voice-volume').value;
 a.value='65';a.oninput();assert.equal(b.value,'65');assert.equal(calls.length,0);
 await a.onchange();assert.deepEqual(calls,[['/device/sound/volume','PUT',{volume:65}]]);
 assert.match(f.get('header-watch-volume-hint').textContent,/已确认/);
 b.value='0';b.oninput();await b.onchange();assert.equal(a.value,'0');assert.equal(f.get('header-watch-volume-label').textContent,'0%');
 assert.equal(f.get('voice-volume').value,pc);f.dom.window.close();
});
test('offline, unowned and audio busy never send; failure is unknown and can retry',async()=>{
 let calls=0,fail=true;const f=setup(async()=>{calls++;if(fail)throw Error('private payload');});const a=f.get('header-watch-volume');
 for(const state of [{...f.ready,connected:false},{...f.ready,owned:false},{...f.ready,busy:true}]){f.ui.update(state);assert(a.disabled);await a.onchange();}
 assert.equal(calls,0);f.ui.update(f.ready);a.value='40';await a.onchange();assert.equal(calls,1);
 assert.equal(f.get('header-watch-volume-label').textContent,'—');assert.match(f.get('sound-volume-hint').textContent,/未确认/);
 assert(!JSON.stringify(f.messages).includes('private'));fail=false;a.value='50';await a.onchange();assert.equal(f.get('sound-volume-label').textContent,'50%');f.dom.window.close();
});
test('single in-flight writer ignores old acknowledgement after disconnect and route change',async()=>{
 let release,calls=0;const f=setup(()=>{calls++;return new Promise(resolve=>release=resolve);});f.ui.update(f.ready);
 const a=f.get('header-watch-volume');a.value='80';const pending=a.onchange();assert(a.disabled);assert(f.get('sound-volume').disabled);
 await f.get('sound-volume').onchange();assert.equal(calls,1);
 f.ui.update({...f.ready,connected:false});f.ui.update({...f.ready,route:'ble'});
 release();await pending;assert.equal(f.messages.length,0);assert.equal(f.get('sound-volume-label').textContent,'—');assert(!a.disabled);f.dom.window.close();
});
