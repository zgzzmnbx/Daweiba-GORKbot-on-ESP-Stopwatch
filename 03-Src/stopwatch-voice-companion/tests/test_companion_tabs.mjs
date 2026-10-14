import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {JSDOM} from 'jsdom';
const html=fs.readFileSync(new URL('../static/index.html',import.meta.url),'utf8');
const code=fs.readFileSync(new URL('../static/companion-tabs.js',import.meta.url),'utf8');
function fixture(saved){
 const dom=new JSDOM(html,{url:'http://127.0.0.1:8899',runScripts:'outside-only'}),w=dom.window;
 w.requestAnimationFrame=fn=>fn();if(saved)w.localStorage.setItem('gork.companion-tab',saved);w.eval(code);
 return {dom,w,get:id=>w.document.getElementById(id)};
}
test('tabs are exclusive, preserve controls and log contents without network calls',()=>{
 const {dom,w,get}=fixture();let calls=0;w.fetch=()=>{calls++;};
 assert.equal(get('companion-panel-expressions').hidden,false);assert.equal(get('companion-panel-logs').hidden,true);
 get('expression-target').value='watch';get('expression-mode').value='loop';get('debug-log').textContent='kept log';
 get('companion-tab-logs').click();
 assert.equal(get('companion-panel-expressions').hidden,true);assert.equal(get('companion-panel-logs').hidden,false);
 assert.equal(get('expression-menu').open,false);
 get('companion-tab-expressions').click();assert.equal(get('expression-menu').open,true);
 assert.equal(get('expression-target').value,'watch');assert.equal(get('expression-mode').value,'loop');
 assert.equal(get('debug-log').textContent,'kept log');assert.equal(calls,0);dom.window.close();
});
test('arrow/Home/End activation updates focus, aria and roving tab order',()=>{
 const {dom,w,get}=fixture(),first=get('companion-tab-expressions'),last=get('companion-tab-logs');
 first.dispatchEvent(new w.KeyboardEvent('keydown',{key:'ArrowRight',bubbles:true,cancelable:true}));
 assert.equal(last.getAttribute('aria-selected'),'true');assert.equal(first.tabIndex,-1);assert.equal(last.tabIndex,0);assert.equal(w.document.activeElement,last);
 last.dispatchEvent(new w.KeyboardEvent('keydown',{key:'Home',bubbles:true}));assert.equal(w.document.activeElement,first);
 first.dispatchEvent(new w.KeyboardEvent('keydown',{key:'End',bubbles:true}));assert.equal(w.document.activeElement,last);dom.window.close();
});
test('saved tab restores; invalid saved values return to expressions',()=>{
 for(const [saved,expected] of [['logs','logs'],['bad','expressions']]){
  const {dom,w,get}=fixture(saved);
  assert.equal(get('companion-tab-'+expected).getAttribute('aria-selected'),'true');assert.equal(w.localStorage.getItem('gork.companion-tab'),expected);
  assert.equal(w.localStorage.length,1);dom.window.close();
 }
});
test('returning to logs preserves a manually scrolled position',()=>{
 const {dom,get}=fixture('logs'),log=get('debug-log');
 Object.defineProperty(log,'scrollHeight',{get:()=>500});Object.defineProperty(log,'clientHeight',{get:()=>100});
 log.scrollTop=100;get('companion-tab-expressions').click();log.scrollTop=0;
 get('companion-tab-logs').click();assert.equal(log.scrollTop,100);dom.window.close();
});
