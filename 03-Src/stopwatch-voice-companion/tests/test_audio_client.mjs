import test from 'node:test';
import assert from 'node:assert/strict';
import {WavPlayer} from '../static/audio-client.js';

test('WavPlayer stops an active source before it can report a late completion', async () => {
  let source;
  const context = {state:'running',destination:{},resume:async()=>{},decodeAudioData:async()=>({}),close:async()=>{},createBufferSource(){
    source={connect(){},disconnect(){},start(){},stop(){this.stopped=true;}}; return source;
  }};
  let ended = 0;
  const player = new WavPlayer(() => context);
  await player.play(new ArrayBuffer(44), () => ended++);
  const late = source.onended;
  player.stop(); late();
  assert.equal(source.stopped, true); assert.equal(ended, 0); assert.equal(player.playing, false);
});
