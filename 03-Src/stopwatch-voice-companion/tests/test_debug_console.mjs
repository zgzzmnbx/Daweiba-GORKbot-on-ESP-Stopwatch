import test from 'node:test';
import assert from 'node:assert/strict';
import {createDebugConsole} from '../static/debug-console.js';

function setup(saved = {}, copyText) {
  const nodes = new Map();
  const make = () => ({dataset:{},children:[],value:'',scrollTop:0,scrollHeight:100,clientHeight:100,
    append(row){this.children.push(row);row.remove=()=>{this.children.splice(this.children.indexOf(row),1);};},
    replaceChildren(...items){this.children=items;}});
  const doc = {getElementById(id){if(!nodes.has(id))nodes.set(id,make());return nodes.get(id);},createElement:make};
  const storage = {getItem:k=>saved[k],setItem:(k,v)=>saved[k]=v};
  const terminal = createDebugConsole(doc,storage,copyText);
  return {terminal,nodes,saved};
}
test('terminal defaults dark, persists only theme, restores light',()=>{
  const {nodes,saved}=setup();
  assert.equal(nodes.get('debug-console').dataset.theme,'dark');
  nodes.get('debug-theme').value='light';nodes.get('debug-theme').onchange();
  assert.deepEqual(saved,{'gork.debug-theme':'light'});
  assert.equal(setup(saved).nodes.get('debug-console').dataset.theme,'light');
});
test('terminal deduplicates each channel and bounds memory/DOM to 120 rows',()=>{
  const {terminal,nodes}=setup();
  terminal.push('BLE','connected');terminal.push('VOICE','ready');terminal.push('BLE','connected');
  assert.equal(nodes.get('debug-log').children.length,3);
  for(let i=0;i<200;i++)terminal.push('UI',`status ${i}`);
  assert.equal(nodes.get('debug-log').children.length,120);
  assert.match(nodes.get('debug-log').children.at(-1).textContent,/status 199/);
  nodes.get('debug-clear').onclick();assert.equal(nodes.get('debug-log').children.length,0);
});
test('terminal uses literal text and does not drag reader away from history',()=>{
  const {terminal,nodes}=setup();const log=nodes.get('debug-log');
  log.scrollHeight=500;log.clientHeight=100;log.scrollTop=20;
  terminal.push('UI','<img onerror=alert(1)>',true);
  assert.equal(log.scrollTop,20);assert.equal(log.children.at(-1).innerHTML,undefined);
  assert.match(log.children.at(-1).textContent,/<img/);
  log.scrollTop=400;terminal.push('UI','next');assert.equal(log.scrollTop,500);
});
test('blocked storage does not prevent terminal initialization',()=>{
  const doc={getElementById:()=>({dataset:{},replaceChildren(){},append(){}}),createElement:()=>({})};
  assert.doesNotThrow(()=>createDebugConsole(doc,{getItem(){throw Error();},setItem(){throw Error();}}));
});

test('expanded logs filter and copy current results, clear both views',async()=>{
  let copied='';const {terminal,nodes}=setup({},async text=>{copied=text;});
  terminal.push('BLE','已连接');terminal.push('SERVICE','离线');terminal.push('DEVICE','操作失败',true);
  const filter=nodes.get('logs-filter');filter.value='ble';filter.onchange();
  assert.equal(nodes.get('logs-full').children.length,2);
  await nodes.get('logs-copy').onclick();assert.match(copied,/BLE/);assert.doesNotMatch(copied,/SERVICE/);
  filter.value='error';filter.onchange();assert.equal(nodes.get('logs-full').children.length,2);
  nodes.get('logs-clear').onclick();assert.equal(nodes.get('debug-log').children.length,0);
  terminal.push('BLE','已连接');assert.equal(nodes.get('debug-log').children.length,1);
});
test('scrolling up pauses follow and new rows preserve history position',()=>{
  const {terminal,nodes}=setup();const full=nodes.get('logs-full'),follow=nodes.get('logs-follow');
  full.scrollHeight=600;full.clientHeight=100;full.scrollTop=50;full.onscroll();
  assert.equal(follow.checked,false);terminal.push('BLE','已连接');assert.equal(full.scrollTop,50);
  follow.checked=true;follow.onchange();assert.equal(full.scrollTop,600);
});
test('clipboard failure is visible and never clears logs',async()=>{
  const {nodes}=setup({},async()=>{throw Error('denied');});
  await nodes.get('logs-copy').onclick();assert.match(nodes.get('logs-feedback').textContent,/复制失败/);
  assert.equal(nodes.get('debug-log').children.length,1);
});
