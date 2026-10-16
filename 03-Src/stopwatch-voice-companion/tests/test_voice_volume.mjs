import test from 'node:test';
import assert from 'node:assert/strict';
import {JSDOM} from 'jsdom';
import {createVoiceVolume} from '../static/voice-volume.js';
import {WavPlayer} from '../static/audio-client.js';

function setup(api,options={}){
  const document=new JSDOM('<input id="voice-volume" type="range" min="0" max="100" disabled><output id="voice-volume-label"></output>').window.document;
  const applied=[],errors=[];
  const ui=createVoiceVolume({document,api,hasWorkspace:()=>true,acquireWorkspace:async()=>true,apply:v=>applied.push(v),report:(...args)=>errors.push(args),...options});
  return {ui,applied,errors,input:document.getElementById('voice-volume'),label:document.getElementById('voice-volume-label')};
}
test('saved volume loads; input updates gain immediately; coalesced changes save the latest value',async()=>{
  let release;const calls=[];
  const f=setup(async(_path,method,body)=>{if(method!=='PUT')return {volume:37};calls.push(body.volume);if(calls.length===1)await new Promise(resolve=>release=resolve);return body;});
  await f.ui.load();assert.equal(f.input.value,'37');assert.equal(f.input.disabled,false);
  f.input.value='20';f.input.oninput();const saved=f.input.onchange();
  await Promise.resolve();f.input.value='80';f.input.oninput();assert.equal(f.applied.at(-1),80);
  release();await saved;assert.deepEqual(calls,[20,80]);assert.equal(f.label.textContent,'80%');
});
test('failure or occupied workspace restores confirmed volume; unknown read stays disabled',async()=>{
  const f=setup(async(_path,method)=>{if(method==='PUT')throw Error('保存失败');return {volume:40};});await f.ui.load();
  f.input.value='0';f.input.oninput();await f.input.onchange();assert.equal(f.input.value,'40');assert.equal(f.applied.at(-1),40);assert.equal(f.errors.at(-1)[1],true);
  const occupied=setup(async()=>({volume:60}),{hasWorkspace:()=>false,acquireWorkspace:async()=>false});await occupied.ui.load();occupied.input.value='10';occupied.input.oninput();await occupied.input.onchange();assert.equal(occupied.input.value,'60');
  const unknown=setup(async()=>{throw Error('offline');});await unknown.ui.load();assert.equal(unknown.input.disabled,true);assert.equal(unknown.label.textContent,'—');
});
test('WavPlayer uses a gain node for saved volume, live changes and mute without altering capture',async()=>{
  const gain={gain:{value:1},connect(destination){this.destination=destination;}},destination={};
  const source={connect(node){this.node=node;},start(){},stop(){},disconnect(){}};
  const context={destination,async resume(){},async decodeAudioData(){return {};},createBufferSource(){return source;},createGain(){return gain;},async close(){this.state='closed';}};
  const player=new WavPlayer(()=>context);player.setVolume(37);await player.play(new ArrayBuffer(0));
  assert.equal(source.node,gain);assert.equal(gain.destination,destination);assert.equal(gain.gain.value,.37);
  player.setVolume(0);assert.equal(gain.gain.value,0);player.stop();assert.equal(player.playing,false);assert.equal(player.gain,null);
});
