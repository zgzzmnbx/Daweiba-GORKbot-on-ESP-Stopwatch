import test from 'node:test';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {createAppearancePicker} from '../static/appearance-picker.js';
const library=createRequire(import.meta.url)('../../gork-desktop/gork-appearance.js');
function setup(bridge,saved={}) {
 const elements=new Map(),changes=[];
 function node(){return {children:[],attrs:{},listeners:{},append(...items){this.children.push(...items);},setAttribute(k,v){this.attrs[k]=v;},addEventListener(k,f){this.listeners[k]=f;}};}
 const get=id=>{if(!elements.has(id))elements.set(id,node());return elements.get(id);};
 const api=createAppearancePicker({getElementById:get,createElement:node},{library,renderer:{mount(){return {dispose(){}};}},catalog:{},storage:{getItem:k=>saved[k],setItem:(k,v)=>saved[k]=v},bridge,onChange:v=>changes.push(v)});
 const open=()=>{get('appearance-menu').open=true;get('appearance-menu').listeners.toggle();return get('appearance-grid').children;};
 return {get,open,changes,saved,api};
}
test('picker changes presets/colors, remembers reload and restores Gork without device calls',async()=>{
 const ui=setup();const cards=ui.open();assert.equal(cards.length,10);
 await cards[3].onclick();assert.equal(ui.changes.at(-1).id,'citrus');
 ui.get('appearance-body').value='#abcdef';await ui.get('appearance-body').onchange();
 assert.equal(ui.changes.at(-1).bodyColor,'#abcdef');
 const reloaded=setup(undefined,ui.saved);assert.equal(reloaded.changes.at(-1).id,'citrus');
 await ui.get('appearance-reset').onclick();assert.equal(ui.changes.at(-1).id,'gork');
});
test('native saved selection wins at startup; failed writes retain the existing appearance',async()=>{
 const ui=setup({getAppearance:async()=>({id:'freddy'}),setAppearance:async()=>{throw new Error('disk');}});
 await ui.api.ready;assert.equal(ui.changes.at(-1).id,'freddy');
 await ui.open()[2].onclick();assert.equal(ui.changes.at(-1).id,'freddy');
 assert.match(ui.get('appearance-feedback').textContent,/失败/);
});
test('late native read cannot replace an explicit choice and native writes are serialized',async()=>{
 let read,write,calls=0;
 const ui=setup({getAppearance:()=>new Promise(r=>read=r),setAppearance:()=>{calls++;return new Promise(r=>write=r);}});
 const cards=ui.open(),pending=cards[2].onclick();await cards[3].onclick();assert.equal(calls,1);
 write({id:'freddy'});await pending;read({id:'gork'});await ui.api.ready;
 assert.equal(ui.changes.at(-1).id,'freddy');
});
