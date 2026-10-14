const test=require('node:test'),assert=require('node:assert/strict');
const {createMotionBridge}=require('../motion-bridge');
const Config=require('../motion/gork-config');
test('saved motion delivery validates sender, revision, renderer ACK and failures',async()=>{
 const handlers={},listeners={},consoleContents={},avatarContents={};let applied=0,last;
 avatarContents.send=(_event,value)=>{last=value;};
 const bridge=createMotionBridge({ipcMain:{handle:(k,f)=>handlers[k]=f,on:(k,f)=>listeners[k]=f},getConsole:()=>({webContents:consoleContents}),getAvatar:()=>({isDestroyed:()=>false,webContents:avatarContents}),fetchRecord:async()=>({revision:3,id:'motion-000000000001',scene:'writing',config:Config.defaults()}),onApplied:()=>applied++,timeoutMs:25});
 const apply=handlers['gork:apply-motion-config'],ack=listeners['gork:motion-applied'];
 await assert.rejects(apply({sender:{}},3),/Only the console/);
 await assert.rejects(apply({sender:consoleContents},'idle'),/Invalid/);
 await assert.rejects(apply({sender:consoleContents},'motion-000000000001','unknown'),/Invalid/);
 let pending=apply({sender:consoleContents},'motion-000000000001','loop');await new Promise(r=>setImmediate(r));
 ack({sender:{}},{requestId:last.requestId,revision:3,ok:true});assert.equal(applied,0);
 ack({sender:avatarContents},{requestId:last.requestId,revision:3,ok:true});assert.equal((await pending).applied,true);assert.equal(applied,1);
 pending=apply({sender:consoleContents},'motion-000000000001','once');await new Promise(r=>setImmediate(r));ack({sender:avatarContents},{requestId:last.requestId,ok:false,error:'renderer failed'});await assert.rejects(pending,/应用失败/);assert.equal(applied,1);
 await assert.rejects(apply({sender:consoleContents},'motion-000000000001'),/超时/);bridge.dispose();
});
