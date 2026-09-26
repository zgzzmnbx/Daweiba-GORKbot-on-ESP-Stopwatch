const test = require('node:test'), assert = require('node:assert/strict');
const fs = require('node:fs'), vm = require('node:vm'), path = require('node:path');
const {bubblePlacement,createBubbleWindow} = require('../bubble-window');
test('readable bubble stays on screen at avatar scales 25 to 150 and negative display coordinates',()=>{
  for (const area of [{x:0,y:0,width:1920,height:1040},{x:-1280,y:-200,width:1280,height:720},{x:0,y:0,width:390,height:540}]) {
    for(const scale of [.25,1,1.5]) for(const edge of [false,true]) {
      const a={x:edge?area.x+area.width-240*scale:area.x,y:area.y+area.height-280*scale,width:240*scale,height:280*scale};
      const {bounds:b}=bubblePlacement(a,area);
      assert.equal(b.width,328);assert.ok(b.x>=area.x&&b.y>=area.y);
      assert.ok(b.x+b.width<=area.x+area.width&&b.y+b.height<=area.y+area.height);
    }
  }
  assert.equal(bubblePlacement({x:1700,y:500,width:60,height:70},{x:0,y:0,width:1920,height:1080}).side,'above');
});
test('bubble lifecycle follows avatar visibility, dismiss, new message, clear and topmost',()=>{
  let win, visible=true, top=false;
  class Window {
    constructor(options){this.options=options;this.events={};this.visible=false;this.webContents={send:(_c,v)=>this.payload=v,setWindowOpenHandler(){},on(){}};win=this;}
    on(e,f){this.events[e]=f;} once(e,f){this.on(e,f);} loadFile(){} isDestroyed(){return false;}
    setBounds(b){this.bounds=b;}setAlwaysOnTop(v){this.top=v;}isVisible(){return this.visible;}
    showInactive(){this.visible=true;}hide(){this.visible=false;}destroy(){this.events.closed?.();}
  }
  const c=createBubbleWindow({BrowserWindow:Window,screen:{getDisplayMatching:()=>({workArea:{x:0,y:0,width:1920,height:1080}})},
    avatar:{isDestroyed:()=>false,isVisible:()=>visible,isAlwaysOnTop:()=>top,getBounds:()=>({x:100,y:100,width:60,height:70})},preferences:{sandbox:true}});
  c.update({bubble:'你好',revision:1});assert.equal(win.visible,false);win.events['ready-to-show']();
  assert.equal(win.visible,true);assert.equal(win.top,false);assert.equal(win.payload.text,'你好');assert.equal(c.owns(win.webContents),true);assert.equal(c.owns({}),false);
  c.dismiss();c.update({bubble:'你好',revision:1});assert.equal(win.visible,false);
  c.update({bubble:'新消息',revision:2});assert.equal(win.visible,true);
  visible=false;c.sync();assert.equal(win.visible,false);
  visible=true;top=true;c.sync();assert.equal(win.top,true);assert.equal(win.visible,true);
  c.update({bubble:'',revision:3});assert.equal(win.visible,false);c.destroy();
  const old = win; c.update({bubble:'late',revision:4});assert.equal(win,old);assert.equal(win.visible,false);
});
test('avatar renders scene state without referencing an out-of-scope manual variable',()=>{
  let render;
  const nodes=new Map();const get=id=>{if(!nodes.has(id))nodes.set(id,{addEventListener(){}});return nodes.get(id);};
  const context={document:{getElementById:get},window:{GorkAvatar:{mount:()=>({set(){}})},gorkDesktop:{getState:()=>Promise.resolve({mode:'idle',scene:{revision:1,expression:'idle'}}),onState:f=>{render=f;}}}};
  vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../avatar.js'),'utf8'),context);
  assert.doesNotThrow(()=>render({mode:'happy',scene:{revision:2,expression:'happy'},character:{bubble:'hi'}}));
  assert.equal(get('status').textContent,'就绪');
});
test('bubble uses literal text and preserves scroll position across state polls',()=>{
  let render;const speech={textContent:'',scrollTop:0};
  const context={document:{getElementById:id=>id==='speech'?speech:{},body:{dataset:{},style:{setProperty(){}}},addEventListener(){}},window:{gorkDesktop:{onBubble:f=>{render=f;}}}};
  vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../bubble.js'),'utf8'),context);
  render({text:'<img src=x onerror=alert(1)>'});assert.equal(speech.innerHTML,undefined);
  speech.scrollTop=50;render({text:speech.textContent});assert.equal(speech.scrollTop,50);
  render({text:'新消息'});assert.equal(speech.scrollTop,0);
});

test('default is above, all four preferred sides work, and top-edge fallback preserves tail alignment',()=>{
  const area={x:0,y:0,width:1920,height:1080}, avatar={x:600,y:400,width:240,height:280};
  assert.equal(bubblePlacement(avatar,area).side,'above');
  for(const side of ['above','below','left','right']) assert.equal(bubblePlacement(avatar,area,'hi',side).side,side);
  const nearTop=bubblePlacement({...avatar,y:0},area);
  assert.equal(nearTop.side,'below');assert.ok(nearTop.bounds.y>=280);
  const nearLeft=bubblePlacement({x:0,y:400,width:60,height:70},area);
  assert.equal(nearLeft.bounds.x,0);assert.equal(nearLeft.anchor,34);
  assert.equal(bubblePlacement(avatar,area,'hi','bad').side,'above');
});
