const test = require('node:test');
const assert = require('node:assert/strict');
const {EventEmitter} = require('node:events');
const {registerQuitCleanup} = require('../quit-manager');
const settle = () => new Promise(resolve => setImmediate(resolve));

function fakeApp() {
  const app=new EventEmitter();app.exits=0;app.blocked=0;
  app.quit=()=>{let blocked=false;app.emit('before-quit',{preventDefault(){blocked=true;app.blocked++;}});if(!blocked)app.exits++;};
  return app;
}
test('Electron quit waits for task cancellation and owned server stop, even after repeated quit requests',async()=>{
  const app=fakeApp(),events=[];let releaseStop,releaseBackend;
  registerQuitCleanup(app,{prepare:()=>events.push('prepare'),stopAll:()=>{events.push('cancel');return new Promise(resolve=>releaseStop=resolve);},stopBackend:()=>{events.push('backend');return new Promise(resolve=>releaseBackend=resolve);}});
  app.quit();app.quit();await settle();
  assert.equal(app.exits,0);assert.deepEqual(events,['prepare','cancel']);
  releaseStop();await settle();assert.equal(app.exits,0);assert.deepEqual(events,['prepare','cancel','backend']);
  releaseBackend();await settle();assert.equal(app.exits,1);assert.equal(app.blocked,2);
});
test('shutdown failures still stop owned backend once and finish quitting without exposing exception details',async()=>{
  const app=fakeApp(),events=[],warnings=[];
  registerQuitCleanup(app,{prepare:()=>{throw Error('private-diagnostic');},stopAll:async()=>{throw Error('private-diagnostic');},stopBackend:async()=>events.push('backend'),warn:text=>warnings.push(text)});
  app.quit();await settle();assert.deepEqual(events,['backend']);assert.equal(app.exits,1);
  assert.equal(warnings.length,2);assert(!warnings.join('').includes('private-diagnostic'));
});
