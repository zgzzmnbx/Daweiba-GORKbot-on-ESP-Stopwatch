const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const desktop = path.resolve(__dirname, '..');

test('avatar visibility IPC accepts only the console sender and boolean state', () => {
  const handlers = new Map();
  const savedSizes = [];
  const electron = {
    app: {isPackaged:false,requestSingleInstanceLock:()=>true,getPath:()=>desktop,on(){},whenReady:()=>new Promise(()=>{})},
    screen: {getDisplayMatching:()=>({workArea:{x:0,y:0,width:1920,height:1080}})},
    ipcMain: {handle:(name,handler)=>handlers.set(name,handler)},
  };
  const scope = {module:{exports:{}},exports:{},__dirname:desktop,process,Buffer,URL,console,
    require(name){
      if(name==='electron') return electron;
      if(name==='./backend-manager') return {};
      if(name==='./window-state') return require('../window-state');
      if(name==='node:fs') return {...fs,writeFileSync:(_path,value)=>savedSizes.push(JSON.parse(value))};
      if(name==='./tray-icon') return require('../tray-icon');
      return require(name);
    },
  };
  const source = fs.readFileSync(path.join(desktop,'main.js'),'utf8');
  vm.runInNewContext(source+'\nmodule.exports.setWindows = (c,a) => { consoleWindow=c; avatarWindow=a; };',scope);
  const consoleContents = {}, outsider = {};
  let visible = true, alwaysOnTop = true, bounds = {x:1800,y:900,width:240,height:280};
  const sent = [];
  const avatar = {getBounds:()=>bounds,setBounds:value=>{bounds=value;},isDestroyed:()=>false,isVisible:()=>visible,showInactive:()=>{visible=true;},hide:()=>{visible=false;},isAlwaysOnTop:()=>alwaysOnTop,setAlwaysOnTop:value=>{alwaysOnTop=value;},webContents:{send:(...args)=>sent.push(args)}};
  scope.module.exports.setWindows({webContents:consoleContents},avatar);
  const get = handlers.get('gork:avatar-visible');
  const set = handlers.get('gork:set-avatar-visible');
  assert.equal(get({sender:consoleContents}),true);
  assert.throws(()=>get({sender:outsider}),/Only the console/);
  assert.throws(()=>set({sender:outsider},false),/Invalid visibility/);
  assert.throws(()=>set({sender:consoleContents},'false'),/Invalid visibility/);
  assert.equal(set({sender:consoleContents},false),false);
  assert.equal(get({sender:consoleContents}),false);
  assert.equal(set({sender:consoleContents},true),true);
  const getTop = handlers.get('gork:avatar-always-on-top'), setTop = handlers.get('gork:set-avatar-always-on-top');
  assert.equal(getTop({sender:consoleContents}),true);
  assert.throws(()=>getTop({sender:outsider}),/Only the console/);
  assert.throws(()=>setTop({sender:outsider},false),/Invalid avatar stacking/);
  assert.throws(()=>setTop({sender:consoleContents},'false'),/Invalid avatar stacking/);
  assert.equal(setTop({sender:consoleContents},false),false);
  assert.equal(getTop({sender:consoleContents}),false);
  assert.equal(savedSizes.at(-1).alwaysOnTop,false);
  assert.equal(setTop({sender:consoleContents},true),true);
  const getScale = handlers.get('gork:avatar-scale'), setScale = handlers.get('gork:set-avatar-scale');
  assert.equal(getScale({sender:consoleContents}),100);
  assert.throws(()=>getScale({sender:outsider}),/Only the console/);
  assert.throws(()=>setScale({sender:outsider},125),/Only the console/);
  for (const invalid of [0,24,151,NaN,Infinity,'125',100.5]) assert.throws(()=>setScale({sender:consoleContents},invalid));
  assert.equal(setScale({sender:consoleContents},150),150);
  assert.deepEqual(JSON.parse(JSON.stringify(bounds)),{x:1560,y:660,width:360,height:420});
  assert.equal(savedSizes.at(-1).width,360);
  assert.equal(setScale({sender:consoleContents},75),75);
  assert.equal(bounds.width,180); assert.equal(bounds.height,210);
  assert.equal(setScale({sender:consoleContents},25),25);
  assert.equal(bounds.width,60); assert.equal(bounds.height,70);
  assert.equal(visible,true);
  const setScene = handlers.get('gork:set-avatar-scene');
  assert.throws(()=>setScene({sender:outsider},{expression:'happy',mode:'loop'}),/Only the console/);
  assert.throws(()=>setScene({sender:consoleContents},{expression:'happy',mode:'bad'}),/Invalid avatar scene/);
  const startedAt = Date.now();
  const scene = setScene({sender:consoleContents},{expression:'happy',mode:'once',startedAt});
  assert.equal(scene.expression,'happy'); assert.equal(scene.mode,'once');
  assert.equal(scene.startedAt,startedAt); assert.equal(scene.revision,1);
  assert.equal(sent.at(-1)[0],'gork:state');
  assert.equal(sent.at(-1)[1].scene,scene);

});

test('preload exposes the visibility bridge', () => {
  const invokes = [];
  let bridge;
  const electron = {contextBridge:{exposeInMainWorld:(_name,value)=>{bridge=value;}},
    ipcRenderer:{invoke:async(...args)=>{invokes.push(args);return true;},on(){}}};
  vm.runInNewContext(fs.readFileSync(path.join(desktop,'preload.js'),'utf8'),{
    require:name=>name==='electron'?electron:require(name),Object,
  });
  return Promise.all([bridge.getAvatarVisible(),bridge.setAvatarVisible(false),bridge.getAvatarAlwaysOnTop(),bridge.setAvatarAlwaysOnTop(false),bridge.getAvatarScale(),bridge.setAvatarScale(125),bridge.setAvatarScene({expression:'happy',mode:'loop'})]).then(()=>{
    assert.deepEqual(invokes,[['gork:avatar-visible'],['gork:set-avatar-visible',false],['gork:avatar-always-on-top'],['gork:set-avatar-always-on-top',false],['gork:avatar-scale'],['gork:set-avatar-scale',125],['gork:set-avatar-scene',{expression:'happy',mode:'loop'}]]);
  });
});

test('avatar restores disabled always-on-top from the saved window state', () => {
  const options = [];
  class BrowserWindow {
    constructor(value) { options.push(value); this.webContents = {setWindowOpenHandler(){},on(){}}; }
    loadFile(){} once(){} on(){}
  }
  const electron = {
    app: {isPackaged:false,requestSingleInstanceLock:()=>true,getPath:()=>desktop,on(){},whenReady:()=>new Promise(()=>{})},
    BrowserWindow, screen: {getAllDisplays:()=>[{workArea:{x:0,y:0,width:1920,height:1080}}]},
    ipcMain: {handle(){}},
  };
  const scope = {module:{exports:{}},exports:{},__dirname:desktop,process,Buffer,URL,console,
    require(name){
      if(name==='electron') return electron;
      if(name==='node:fs') return {...fs,readFileSync:()=>JSON.stringify({x:100,y:100,width:180,height:210,alwaysOnTop:false})};
      if(name==='./backend-manager') return {};
      if(name==='./window-state') return require('../window-state');
      if(name==='./tray-icon') return require('../tray-icon');
      return require(name);
    },
  };
  vm.runInNewContext(fs.readFileSync(path.join(desktop,'main.js'),'utf8')+'\nmodule.exports.createAvatar = createAvatar;',scope);
  scope.module.exports.createAvatar();
  assert.equal(options[0].alwaysOnTop,false);
  assert.equal(options[0].width,180);
});
