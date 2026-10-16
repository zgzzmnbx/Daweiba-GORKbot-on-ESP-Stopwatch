const test=require('node:test'),assert=require('node:assert/strict'),{EventEmitter}=require('node:events');
const {createTrafficRelay}=require('../traffic-relay');
test('avatar hidden drops late read; restore resumes; dispose stops relay',async()=>{
  const a=new EventEmitter();a.webContents=new EventEmitter();let visible=true,calls=0,resolve;const sent=[];
  a.isDestroyed=()=>false;a.isVisible=()=>visible;a.isMinimized=()=>false;a.webContents.send=(...args)=>sent.push(args);
  const relay=createTrafficRelay({avatar:a,read:()=>{calls++;return new Promise(r=>resolve=r);},interval:10});
  a.emit('show');assert.equal(calls,1);visible=false;a.emit('hide');resolve({enabled:true});await new Promise(r=>setTimeout(r,20));assert.equal(sent.length,0);
  visible=true;a.emit('show');assert.equal(calls,2);resolve({enabled:false});await new Promise(r=>setTimeout(r,1));assert.equal(sent[0][1].enabled,false);
  relay.dispose();await new Promise(r=>setTimeout(r,20));assert.equal(calls,2);
});
