import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {JSDOM} from 'jsdom';
const read=p=>fs.readFileSync(new URL('../'+p,import.meta.url),'utf8');
function setup(){
 const dom=new JSDOM(read('static/index.html'),{url:'http://localhost/#dialogue',runScripts:'outside-only'}),w=dom.window;
 w.HTMLElement.prototype.scrollBy=function({left}){this.scrollLeft+=left;this.dispatchEvent(new w.Event('scroll'));};
 w.eval(read('static/console-shell.js'));return {dom,w,get:id=>w.document.getElementById(id)};
}
test('status distinguishes configured, actual success, failure, expired, revoked and missing evidence',()=>{
 const {dom,w,get}=setup(),shell=w.GorkShell;
 const data={answer:{enabled:true,model:'deepseek-chat'},speech_output:{route:'cloud'},voice:{ready:true},capabilities:{cloud:{state:'configured',tts_model:'qwen3-tts-flash'}}};
 shell.health(data);assert.equal(get('service-answer').dataset.state,'configured');assert.match(get('service-tts-detail').textContent,/不代表云端已连通/);
 data.answer.observation={state:'success',at:Date.now()/1000};data.speech_output.observation={state:'error',at:Date.now()/1000,route:'cloud'};
 shell.health(data);assert.equal(get('service-answer').dataset.state,'ready');assert.equal(get('service-tts').dataset.state,'error');
 data.answer.observation.at-=360; shell.health(data);assert.equal(get('service-answer').dataset.state,'unknown');
 get('text-consent').checked=false;shell.health(data);assert.equal(get('service-tts').dataset.state,'paused');
 get('text-consent').checked=true;data.capabilities.cloud.state='missing_key';shell.health(data);assert.equal(get('service-tts').dataset.state,'offline');
 shell.unavailable();shell.session({connected:true,voiceLabel:'已连接',robotConnected:true,watchLink:'Wi-Fi'});
 for(const key of ['answer','tts','voice','watch'])assert.equal(get('service-'+key).dataset.state,'unknown');
 data.speech_output={route:'local'};data.capabilities.tts={state:'ready'};shell.health(data);assert.equal(get('service-tts').dataset.state,'ready');
 shell.health({});assert.equal(get('service-tts').dataset.state,'unknown');assert.equal(get('service-answer').dataset.state,'unknown');dom.window.close();
});
test('tab paging exposes overflow and disables ends; paging does not change selected page',()=>{
 const {dom,w,get}=setup(),nav=get('module-tabs');
 Object.defineProperties(nav,{clientWidth:{value:200},scrollWidth:{value:700}});w.dispatchEvent(new w.Event('resize'));
 assert(!get('tabs-next').hidden);assert(get('tabs-prev').disabled);assert(!get('tabs-next').disabled);
 get('tabs-next').click();assert.equal(nav.scrollLeft,150);assert.equal(w.location.hash,'#dialogue');assert(!get('tabs-prev').disabled);
 nav.scrollLeft=500;nav.dispatchEvent(new w.Event('scroll'));assert(get('tabs-next').disabled);
 get('tabs-prev').click();assert.equal(nav.scrollLeft,350);dom.window.close();
});
test('status details are keyboard dismissible and never inject provider strings as markup',()=>{
 const {dom,w,get}=setup();w.GorkShell.health({answer:{enabled:true,model:'<img src=x>'}});
 assert.equal(get('global-answer').querySelector('img'),null);get('service-answer').open=true;
 get('service-answer').dispatchEvent(new w.KeyboardEvent('keydown',{key:'Escape',bubbles:true}));
 assert(!get('service-answer').open);assert.equal(w.document.activeElement,get('service-answer').querySelector('summary'));dom.window.close();
});

test('Watch transport is visible, follows actual route and clears when disconnected or unknown',()=>{
 const {dom,w,get}=setup(),shell=w.GorkShell;
 for(const route of ['Wi-Fi','蓝牙']){shell.session({connected:true,robotConnected:true,watchLink:route+' '});assert.equal(get('watch-transport').textContent,route);}
 shell.session({robotConnected:false,watchLink:'Wi-Fi'});assert.equal(get('watch-transport').textContent,'未连接');
 shell.session({robotConnected:true,watchLink:''});assert.equal(get('watch-transport').textContent,'未知');
 shell.unavailable();assert.equal(get('watch-transport').textContent,'未知');dom.window.close();
});
