const test=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs'),path=require('node:path');
test('custom ACK echo preserves playback; a new command or renderer reload plays once',async()=>{
 function boot(){let render,receive;const plays=[],acks=[],sets=[],nodes=new Map();
  const get=id=>{if(!nodes.has(id))nodes.set(id,{dataset:{},addEventListener(){}});return nodes.get(id);};
  const scope={document:{getElementById:get},window:{GorkDesktopSceneAdapter:{mount:()=>({set:(...args)=>sets.push(args),playCustom:(...args)=>plays.push(args)})},gorkDesktop:{getState:()=>Promise.resolve({mode:'idle'}),onState:f=>{render=f;},onMotionConfig:f=>{receive=f;},motionApplied:ack=>acks.push(ack)}}};
  vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../avatar.js'),'utf8'),scope);return {plays,acks,sets,render:s=>render(s),receive:d=>receive(d)};
 }
 const ui=boot();await Promise.resolve();const record={id:'motion-000000000001',revision:4};const scene={expression:record.id,mode:'loop',startedAt:1000,requestId:7};
 ui.receive({record,scene,requestId:7});assert.equal(ui.plays.length,1);assert.equal(ui.acks[0].ok,true);
 const state={scene:{...scene,custom:record,revision:1}};for(let i=0;i<50;i++)ui.render(state);assert.equal(ui.plays.length,1,'500ms shared-state echo must not remount after ACK');
 ui.render({scene:{...scene,custom:record,revision:2,requestId:8}});assert.equal(ui.plays.length,2,'new replay command must play');
 ui.render({scene:{expression:'idle',mode:'loop',revision:3}});assert.equal(ui.sets.at(-1)[0],'idle');
 const reloaded=boot();await Promise.resolve();reloaded.render(state);assert.equal(reloaded.plays.length,1,'fresh renderer must consume shared snapshot');
});
