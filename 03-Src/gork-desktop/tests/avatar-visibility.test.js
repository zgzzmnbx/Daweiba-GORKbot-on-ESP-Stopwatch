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
    ipcMain: {on(){},handle:(name,handler)=>handlers.set(name,handler)},
  };
  const scope = {module:{exports:{}},exports:{},__dirname:desktop,process,Buffer,URL,console,
    require(name){
      if(name==='electron') return electron;
      if(name==='./backend-manager') return {};
      if(name==='./bubble-window') return {...require('../bubble-window'),createBubbleWindow:()=>({sync(){},hide(){},update(){}})};
      if(name==='./window-state') return require('../window-state');
      if(name==='node:fs') return {...fs,writeFileSync:(_path,value)=>savedSizes.push(JSON.parse(value))};
      if(name==='./bubble-window') return {...require('../bubble-window'),createBubbleWindow:()=>({sync(){},hide(){},update(){}})};
      if(name==='./gork-appearance') return require('../gork-appearance');
      if(name==='./tray-icon') return require('../tray-icon');
      return require(name.startsWith('./')?path.join(desktop,name):name);
    },
  };
  const source = fs.readFileSync(path.join(desktop,'main.js'),'utf8');
  vm.runInNewContext(source+'\nmodule.exports.setWindows = (c,a) => { consoleWindow=c; avatarWindow=a; };',scope);
  const consoleContents = {}, outsider = {};
  let visible = true, alwaysOnTop = true, bounds = {x:1800,y:900,width:240,height:280};
  const sent = [];
  const avatar = {getBounds:()=>bounds,setBounds:value=>{bounds=value;},isDestroyed:()=>false,isVisible:()=>visible,showInactive:()=>{visible=true;},hide:()=>{visible=false;},isAlwaysOnTop:()=>alwaysOnTop,setAlwaysOnTop:value=>{alwaysOnTop=value;},webContents:{send:(...args)=>sent.push(args)}};
  scope.module.exports.setWindows({webContents:consoleContents},avatar);
  const drag=handlers.get('gork:indicator-drag');
  assert.throws(()=>drag({sender:consoleContents},{phase:'start',id:1}),/Only indicators/);
  assert.throws(()=>drag({sender:outsider},{phase:'start',id:1}),/Only indicators/);
  const tokenHover = handlers.get('gork:token-hover');
  assert.throws(()=>tokenHover({sender:outsider},true),/Invalid token hover/);
  assert.throws(()=>tokenHover({sender:consoleContents},true),/Invalid token hover/);
  assert.throws(()=>tokenHover({sender:avatar.webContents},'true'),/Invalid token hover/);
  assert.equal(tokenHover({sender:avatar.webContents},true),true);
  assert.equal(tokenHover({sender:avatar.webContents},false),true);
  assert.throws(()=>handlers.get('gork:token-height')({sender:consoleContents},300),/Invalid token height/);
  assert.throws(()=>handlers.get('gork:hide-token-card')({sender:consoleContents}),/Invalid token dismiss/);
  const getPointer = handlers.get('gork:pointer-follow'), setPointer = handlers.get('gork:set-pointer-follow');
  assert.equal(getPointer({sender:consoleContents}),true,'new preference defaults on');
  assert.throws(()=>getPointer({sender:outsider}),/Only the console/);
  assert.throws(()=>setPointer({sender:outsider},false),/Invalid pointer/);
  for(const value of ['false',0,null])assert.throws(()=>setPointer({sender:consoleContents},value),/Invalid pointer/);
  assert.equal(setPointer({sender:consoleContents},false),false);
  assert.equal(savedSizes.at(-1).pointerFollow,false);
  assert.equal(sent.at(-1)[1].pointerFollow,false);
  assert.equal(setPointer({sender:consoleContents},true),true);
  const getLook=handlers.get('gork:get-appearance'), setLook=handlers.get('gork:set-appearance');
  assert.equal(getLook({sender:consoleContents}).id,'gork');
  assert.throws(()=>getLook({sender:outsider}),/Only the console/);
  assert.throws(()=>setLook({sender:outsider},{id:'kirby'}),/Only the console/);
  const look=setLook({sender:consoleContents},{id:'kirby',bodyColor:'#123456',eyeColor:'bad'});
  assert.equal(look.id,'kirby');assert.equal(look.bodyColor,'#123456');
  assert.equal(savedSizes.at(-1).appearance.id,'kirby');
  assert.equal(sent.at(-1)[1].appearance.id,'kirby');
  const getIndicators=handlers.get('gork:indicator-settings'),setIndicators=handlers.get('gork:set-indicator-settings');
  assert.throws(()=>getIndicators({sender:outsider}),/Only the console/);
  assert.throws(()=>setIndicators({sender:outsider},{mode:'bubbles',items:[]}),/Invalid/);
  assert.throws(()=>setIndicators({sender:consoleContents},{mode:'bubbles',items:['wrong']}),/Invalid/);
  setIndicators({sender:consoleContents},{mode:'menu',items:['vpn','tokens']});
  assert.equal(savedSizes.at(-1).indicatorSettings.mode,'menu');
  assert.equal(savedSizes.at(-1).indicatorSettings.items.join(','),'vpn,tokens');
  vm.runInContext("globalThis.originalSaveState=saveState;saveState=()=>{throw Error('disk unavailable')}",scope);
  assert.throws(()=>setIndicators({sender:consoleContents},{mode:'bubbles',items:[]}),/disk unavailable/);
  assert.equal(getIndicators({sender:consoleContents}).mode,'menu');
  vm.runInContext("saveState=globalThis.originalSaveState",scope);
  const getPosition=handlers.get('gork:bubble-position'), setPosition=handlers.get('gork:set-bubble-position');
  assert.equal(getPosition({sender:consoleContents}),'above');
  assert.throws(()=>getPosition({sender:outsider}),/Only the console/);
  assert.throws(()=>setPosition({sender:outsider},'left'),/Invalid/);
  assert.throws(()=>setPosition({sender:consoleContents},'bad'),/Invalid/);
  assert.equal(setPosition({sender:consoleContents},'left'),'left');
  assert.equal(savedSizes.at(-1).bubblePosition,'left');
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
    ipcMain: {on(){},handle(){}},
  };
  const scope = {module:{exports:{}},exports:{},__dirname:desktop,process,Buffer,URL,console,
    require(name){
      if(name==='electron') return electron;
      if(name==='node:fs') return {...fs,readFileSync:()=>JSON.stringify({x:100,y:100,width:180,height:210,alwaysOnTop:false,pointerFollow:false,indicatorSettings:{mode:'menu',items:[]},indicatorOffset:{x:-80,y:140},bubblePosition:'below',appearance:{id:'freddy',bodyColor:'#123456'}})};
      if(name==='./backend-manager') return {};
      if(name==='./window-state') return require('../window-state');
      if(name==='./bubble-window') return require('../bubble-window');
      if(name==='./gork-appearance') return require('../gork-appearance');
      if(name==='./tray-icon') return require('../tray-icon');
      return require(name.startsWith('./')?path.join(desktop,name):name);
    },
  };
  vm.runInNewContext(fs.readFileSync(path.join(desktop,'main.js'),'utf8')+'\nmodule.exports.createAvatar = createAvatar; module.exports.position = () => bubblePosition; module.exports.look = () => appearance; module.exports.pointer = () => pointerFollow; module.exports.indicators = () => indicatorSettings;',scope);
  scope.module.exports.createAvatar();
  assert.equal(scope.module.exports.indicators().mode,'menu');assert.equal(scope.module.exports.indicators().items.length,0);
  assert.equal(options[0].alwaysOnTop,false);
  assert.equal(options[0].width,180);
  assert.equal(scope.module.exports.position(),'below');
  assert.equal(scope.module.exports.look().id,'freddy');
  assert.equal(scope.module.exports.look().bodyColor,'#123456');
  assert.equal(scope.module.exports.pointer(),false,'explicit off preference survives restart');
});
