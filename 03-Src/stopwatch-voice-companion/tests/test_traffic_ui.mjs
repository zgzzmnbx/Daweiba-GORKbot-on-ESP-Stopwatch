import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {JSDOM} from 'jsdom';
import {createTrafficUI,bytes} from '../static/traffic-ui.js';
const tick=()=>new Promise(resolve=>setTimeout(resolve,10));
function setup(api,owner=true){
  const dom=new JSDOM(fs.readFileSync(new URL('../static/index.html',import.meta.url),'utf8'),{url:'http://localhost/#traffic',pretendToBeVisual:true});
  const errors=[],ui=createTrafficUI({document:dom.window.document,api,acquireWorkspace:async()=>false,hasWorkspace:()=>owner,report:e=>errors.push(e)});
  return {dom,ui,errors,$:id=>dom.window.document.getElementById(id),close(){ui.dispose();dom.window.close();}};
}
const state={enabled:true,physical:{status:'available',down_speed:1024,up_speed:0},clash:{status:'unavailable'},processes:[{name:'<img src=x onerror=bad()>',upload:2,download:3,proxy:5,direct:0}]};
test('unknown differs from zero; unsafe names are text; failed source hides speed',async()=>{
  const f=setup(async()=>state);await tick();
  assert.equal(f.$('traffic-physical-down').textContent,'1.0 KiB/s');
  assert.equal(f.$('traffic-proxy-down').textContent,'—');
  assert.equal(f.$('traffic-rows').querySelector('img'),null);
  assert.ok(f.$('traffic-rows').textContent.includes('<img'));
  assert.equal(bytes(0),'0 B');assert.equal(bytes(null),'—');f.close();
});
test('occupied workspace cannot toggle; success saves once and hides sampling',async()=>{
  const writes=[];const denied=setup(async(p,m,b)=>{if(m)writes.push(b);return state;},false);await tick();
  await denied.$('header-traffic').onclick();assert.equal(writes.length,0);assert.ok(denied.errors[0].includes('控制权'));denied.close();
  let current=state;const f=setup(async(p,m,b)=>{if(m){writes.push(b);current={...state,enabled:b.enabled};}return current;});await tick();
  await f.$('header-traffic').onclick();await tick();assert.equal(writes.length,1);assert.equal(f.$('header-traffic').getAttribute('aria-checked'),'false');f.close();
});
test('late poll after disposal never repaints or restarts timer',async()=>{
  let release;const f=setup(()=>new Promise(resolve=>release=resolve));f.ui.dispose();release(state);await tick();
  assert.equal(f.$('header-traffic').disabled,true);f.close();
});
