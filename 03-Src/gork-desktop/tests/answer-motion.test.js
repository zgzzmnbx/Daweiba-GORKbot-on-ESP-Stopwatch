const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const desktop=path.resolve(__dirname,'..');
test('answer custom snapshot reaches desktop once per revision and ends with the answer',async()=>{
 const entry={id:'motion-000000000001',name:'我的书写',scene:'writing',config:{fixture:true}};
 let data={phase:'generating',character:{auto:true,expression:entry.id,mode:'loop',custom_motion:entry,revision:200001}};
 const electron={app:{isPackaged:false,requestSingleInstanceLock:()=>true,getPath:()=>desktop,on(){},whenReady:()=>new Promise(()=>{})},ipcMain:{on(){},handle(){}},screen:{}};
 const scope={module:{exports:{}},exports:{},__dirname:desktop,process,Buffer,URL,console,AbortSignal,fetch:async()=>({json:async()=>data}),
  require(name){if(name==='electron')return electron;if(name==='./backend-manager')return {};
   if(name==='node:fs')return {...fs,existsSync:()=>false};
   return require(name.startsWith('./')?path.join(desktop,name):name);}};
 vm.runInNewContext(fs.readFileSync(path.join(desktop,'main.js'),'utf8')+'\nmodule.exports.poll=pollState;module.exports.state=()=>sharedState;',scope);
 await scope.module.exports.poll();const first=scope.module.exports.state().scene;
 assert.equal(first.custom,entry);assert.equal(first.expression,entry.id);assert.equal(first.mode,'loop');
 await scope.module.exports.poll();assert.equal(scope.module.exports.state().scene.revision,first.revision);
 assert.equal(scope.module.exports.state().scene.startedAt,first.startedAt,'polls preserve the start of the same animation');
 const question={id:'motion-000000000002',name:'我的疑惑',scene:'question',config:{fixture:true}};
 data={phase:'listening',character:{auto:true,expression:question.id,mode:'loop',custom_motion:question,revision:200002}};
 await scope.module.exports.poll();assert.equal(scope.module.exports.state().scene.custom,question);
 data={phase:'speaking',character:{auto:true,expression:entry.id,mode:'loop',custom_motion:entry,revision:200003}};
 await scope.module.exports.poll();assert.equal(scope.module.exports.state().scene.custom,entry);
 data={phase:'ready',character:{auto:false,expression:'idle',mode:'loop',bubble:'答案',revision:1}};
 await scope.module.exports.poll();assert.equal(scope.module.exports.state().scene?.custom,undefined);
 assert.equal(scope.module.exports.state().character.bubble,'答案');
});
