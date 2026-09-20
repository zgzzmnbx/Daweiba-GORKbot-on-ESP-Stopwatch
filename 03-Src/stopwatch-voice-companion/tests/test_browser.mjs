import test from 'node:test';
import assert from 'node:assert/strict';
import {toPCM16, Epoch} from '../static/pcm.js';
import fs from 'node:fs';
import vm from 'node:vm';
import {webcrypto} from 'node:crypto';

test('48k stereo-downmixed floats become real 16k mono PCM WAV', () => {
  const wav = toPCM16([new Float32Array(4800).fill(.5)], 48000), view = new DataView(wav);
  assert.equal(wav.byteLength, 44 + 3200);
  assert.equal(view.getUint32(24, true), 16000);
  assert.equal(view.getUint16(22, true), 1);
  assert.equal(view.getUint16(34, true), 16);
  assert.equal(view.getInt16(44, true), 16384);
});
test('sample saturation and 30-second maximum', () => {
  const view = new DataView(toPCM16([Float32Array.of(2, -2)], 16000));
  assert.equal(view.getInt16(44, true),32767); assert.equal(view.getInt16(46,true),-32768);
  assert.equal(toPCM16([new Float32Array(16000*31)],16000).byteLength,960044);
});
test('20 intermediate stops invalidate old playback/HTTP generations', () => {
  const epoch = new Epoch();
  for (let i=0; i<20; i++) {
    const old = epoch.next(), oldSignal = epoch.abort.signal;
    epoch.next(); assert.equal(epoch.valid(old), false); assert.equal(oldSignal.aborted, true);
  }
});

function workbench() {
  const elements = new Map(), waiting = [], played = [], requests = [];
  const element = id => {
    if (!elements.has(id)) elements.set(id, {value:'',textContent:'',checked:false,addEventListener(){},getTracks(){return [];}});
    return elements.get(id);
  };
  class AudioContext {
    constructor(){this.state='running';}
    async resume(){} async suspend(){} async close(){this.state='closed';}
    async decodeAudioData(){return {};}
    createBufferSource(){const player={stopped:false,connect(){},disconnect(){},start(){played.push(this);},stop(){this.stopped=true;}};return player;}
  }
  const context = vm.createContext({
    toPCM16,Epoch,AbortController,AbortSignal,DOMException,ArrayBuffer,performance,AudioContext,
    crypto:webcrypto,document:{getElementById:element,body:{dataset:{}}},window:{addEventListener(){}},
    setInterval:()=>0,clearInterval(){},clearTimeout(){},setTimeout,console,
    async fetch(url, options){
      requests.push({url,body:options.body});
      if(url==='/api/tts') return await new Promise(resolve=>waiting.push(()=>resolve({ok:true,arrayBuffer:async()=>new ArrayBuffer(44)})));
      return {ok:true,json:async()=>url==='/api/health'?{voice:{ready:true},voice_url:'local',robot:{}}:{generation:0,robot:{}}};
    }
  });
  const script = fs.readFileSync(new URL('../static/app.js', import.meta.url),'utf8').replace(/^import .*;\r?\n/, '');
  vm.runInContext(script,context);
  return {element,waiting,played,requests};
}
const settle = () => new Promise(resolve=>setImmediate(resolve));

test('actual UI handlers: 20 canceled TTS responses never start a player', async()=>{
  const ui=workbench(); await settle(); await ui.element('connect').onclick();
  ui.element('transcript').value='测试文字';
  for(let i=0;i<20;i++){
    const request=ui.element('speak').onclick(); await settle();
    assert.equal(ui.waiting.length,1);
    await ui.element('stop').onclick(); ui.waiting.shift()(); await request;
    assert.equal(ui.played.length,0);
  }
});
test('actual UI handlers: 20 active players stop before server cancellation', async()=>{
  const ui=workbench(); await settle(); await ui.element('connect').onclick();
  ui.element('transcript').value='测试文字';
  for(let i=0;i<20;i++){
    const request=ui.element('speak').onclick(); await settle(); ui.waiting.shift()(); await request;
    const player=ui.played.at(-1), oldEnded=player.onended;
    const cancel=ui.element('stop').onclick();
    assert.equal(player.stopped,true); assert.equal(player.onended,null);
    await cancel; const before=ui.requests.length; oldEnded();
    assert.equal(ui.requests.length,before);
  }
  assert.equal(ui.played.length,20);
});
