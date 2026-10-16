import test from 'node:test';import assert from 'node:assert/strict';import fs from 'node:fs';import {JSDOM} from 'jsdom';
const tick=()=>new Promise(r=>setTimeout(r,0));
test('settings persist choices, preserve empty selection and revert failed writes; browser remains disabled',async()=>{
 const source=fs.readFileSync(new URL('../static/indicator-settings.js',import.meta.url),'utf8'),html=fs.readFileSync(new URL('../static/index.html',import.meta.url),'utf8');
 const dom=new JSDOM(html,{runScripts:'outside-only'}),w=dom.window,d=w.document;let saved={mode:'bubbles',items:['tokens']},fail=false;
 w.gorkDesktop={getIndicatorSettings:async()=>saved,setIndicatorSettings:async value=>{if(fail)throw Error('fixture');saved=value;return value;}};w.eval(source);await tick();
 const inputs=[...d.querySelectorAll('#desktop-indicator-items input')],mode=d.getElementById('desktop-indicator-mode');
 const token=inputs.find(i=>i.value==='tokens');token.checked=false;token.dispatchEvent(new w.Event('change'));await tick();assert.equal(saved.items.length,0);
 fail=true;mode.value='menu';mode.dispatchEvent(new w.Event('change'));await tick();assert.equal(mode.value,'bubbles');assert.match(d.getElementById('desktop-indicator-hint').textContent,/保存失败/);
 fail=false;mode.value='menu';mode.dispatchEvent(new w.Event('change'));await tick();assert(d.getElementById('desktop-indicator-items').disabled);assert.equal(saved.mode,'menu');w.close();
 const browser=new JSDOM(html,{runScripts:'outside-only'});browser.window.eval(source);await tick();assert(browser.window.document.getElementById('desktop-indicator-mode').disabled);browser.window.close();
});
