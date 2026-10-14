const test=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs'),path=require('node:path');
const {EventEmitter}=require('node:events');
const {createTokenWindow,tokenPlacement}=require('../token-window');
const desktop=path.resolve(__dirname,'..');

test('independent token card remains readable at 25/100/150 percent and all screen edges',()=>{
  for(const area of [{x:0,y:0,width:1920,height:1040},{x:-1280,y:-200,width:1280,height:720},{x:0,y:0,width:390,height:540}])
    for(const scale of [.25,1,1.5])for(const edge of [false,true]){
      const {bounds:b}=tokenPlacement({x:edge?area.x+area.width-240*scale:area.x,
        y:edge?area.y+area.height-280*scale:area.y,width:240*scale,height:280*scale},area);
      assert.equal(b.width,276);assert.equal(b.height,480);
      assert(b.x>=area.x&&b.y>=area.y&&b.x+b.width<=area.x+area.width&&b.y+b.height<=area.y+area.height);
    }
});

function fixture(){
  const avatar=new EventEmitter();let visible=true,top=false,win;
  avatar.isDestroyed=()=>false;avatar.isVisible=()=>visible;avatar.isAlwaysOnTop=()=>top;
  avatar.getBounds=()=>({x:100,y:100,width:60,height:70});
  class Window extends EventEmitter{
    constructor(options){super();this.options=options;this.visible=false;this.webContents={send:(_name,value)=>this.payload=value,setWindowOpenHandler(){},on(){}};win=this;}
    setIgnoreMouseEvents(value){this.ignore=value;}loadFile(){}isDestroyed(){return false;}
    setBounds(value){this.bounds=value;}setAlwaysOnTop(value){this.top=value;}isVisible(){return this.visible;}
    showInactive(){this.visible=true;}hide(){this.visible=false;}destroy(){this.visible=false;this.emit('closed');}
  }
  const ticks=new Map(),releases=[];let reads=0;
  const card=createTokenWindow({BrowserWindow:Window,screen:{getDisplayMatching:()=>({workArea:{x:0,y:0,width:1920,height:1080}})},
    avatar,preferences:{sandbox:true},readUsage:()=>{reads++;return new Promise(resolve=>releases.push(resolve));},
    timers:{setInterval(fn,delay){assert.equal(delay,20000);ticks.set(1,fn);return 1;},clearInterval(id){ticks.delete(id);}}});
  return {avatar,card,ticks,releases,reads:()=>reads,win:()=>win,visible(value){visible=value;},top(value){top=value;}};
}
const settle=()=>new Promise(resolve=>setImmediate(resolve));
test('hover is lazy, accepts detail clicks without focus, polls once and stops after both surfaces leave',async()=>{
  const f=fixture();assert.equal(f.win(),undefined);assert.equal(f.reads(),0);
  f.card.setHover(true);await settle();const win=f.win();assert.equal(win.options.focusable,false);assert.equal(win.ignore,false);
  assert.equal(win.visible,false);win.emit('ready-to-show');assert.equal(win.visible,true);
  f.card.setHover(true);assert.equal(f.reads(),1);assert.equal(f.ticks.size,1);
  f.releases.shift()({status:'available',total_tokens:1100});await settle();assert.equal(win.payload.total_tokens,1100);
  f.top(true);f.card.sync();assert.equal(win.top,true);
  f.card.setHover(true,'card');f.card.setHover(false,'avatar');assert.equal(win.visible,true,'crossing onto card keeps details clickable');
  f.card.setHeight(610);assert.equal(win.bounds.height,610);assert.equal(f.card.owns(win.webContents),true);
  f.card.setHeight(-1);assert.equal(win.bounds.height,610);
  f.avatar.emit('hide');assert.equal(win.visible,false);assert.equal(f.ticks.size,0);
  f.card.setHover(true);await settle();f.card.setHover(false);f.releases.shift()({status:'available',total_tokens:9999});await settle();
  assert.equal(win.visible,false,'late response must not reopen the card');f.card.destroy();assert.equal(f.avatar.listenerCount('move'),0);
});
test('card formats exact totals, missing and stale values without converting missing to zero',()=>{
  let receive;const nodes=new Map();const element=()=>({textContent:'',title:'',children:[],parentElement:{dataset:{}},append(...items){this.children.push(...items);},replaceChildren(){this.children=[];},setAttribute(){}});
  const get=id=>{if(!nodes.has(id))nodes.set(id,element());return nodes.get(id);};
  const context={document:{getElementById:get,createElement:element,body:{dataset:{}}},window:{gorkDesktop:{onTokenUsage:fn=>{receive=fn;}}},Date,Number};
  vm.runInNewContext(fs.readFileSync(path.join(desktop,'token-card.js'),'utf8'),context);
  receive({status:'available',date:'2026-10-14',total_tokens:7605730,input_tokens:7572222,output_tokens:33508,cache_tokens:7012736,request_count:41,sampled_at:'2026-10-14T12:00:00+08:00'});
  assert.equal(get('token-total').textContent,'7.61M');assert.equal(get('token-total').title,'7,605,730 tokens');
  assert.equal(get('token-output').textContent,'33.5K');assert.match(get('token-date').textContent,/10-14/);
  receive({status:'missing',total_tokens:null});assert.equal(get('token-total').textContent,'—');assert.match(get('token-status').textContent,/未找到/);
  receive({status:'unavailable',stale:true,total_tokens:1100});assert.equal(get('token-total').textContent,'1.1K');assert.match(get('token-status').textContent,/上次统计/);
  receive({status:'available',total_tokens:0,request_count:0});assert.equal(get('token-total').textContent,'0');
  receive({quota:{status:'available',buckets:{weekly:{name:'Codex',windows:[{name:'7 天（10080 分钟）',duration_minutes:10080,remaining_percent:0,resets_at:1792080000}]}}}});
  assert.equal(get('quota-windows').children.length,1,'actual single window, no invented five-hour window');
  assert.equal(get('quota-windows').children[0].children[0].children[0].textContent,'0%');
  assert.match(get('quota-detail-windows').children[0].textContent,/重置.*北京时间/);
  receive({quota:{status:'unavailable',stale:true,buckets:{weekly:{windows:[{name:'窗口 1',remaining_percent:null}]}}}});
  assert.equal(get('quota-windows').children[0].children[0].children[0].textContent,'—');
  assert.match(get('quota-status').textContent,/上次额度/);
  receive({quota:{status:'api_key_account',buckets:{}}});assert.equal(get('quota-windows').children.length,0);
  assert.match(get('quota-status').textContent,/API Key/);
  receive({quota:{status:'network_error',buckets:{}}});assert.match(get('quota-notice').textContent,/网络连接失败/);
  receive({quota:{status:'timeout',buckets:{}}});assert.match(get('quota-notice').textContent,/超时/);
});

test('slow official quota does not block token totals, and late quota never reopens a hidden card',async()=>{
  let resolveQuota;const f=fixture();
  // Use a second manager with quota available, retaining the same fake window class.
  f.card.setHover(true);const Window=f.win().constructor;f.card.destroy();
  const card=createTokenWindow({BrowserWindow:Window,screen:{getDisplayMatching:()=>({workArea:{x:0,y:0,width:1920,height:1080}})},
    avatar:f.avatar,preferences:{},readUsage:async()=>({status:'available',total_tokens:42}),
    readQuota:()=>new Promise(resolve=>{resolveQuota=resolve;}),timers:{setInterval(){return 1;},clearInterval(){}}});
  card.setHover(true);await settle();const win=f.win();win.emit('ready-to-show');
  assert.equal(win.payload.total_tokens,42);assert.equal(win.payload.quota.status,'loading');
  card.setHover(false);resolveQuota({status:'available',buckets:{}});await settle();
  assert.equal(win.visible,false);card.destroy();
});
test('real hover handlers debounce leave, support focus/Escape, and dispose subscriptions',()=>{
  const root=new EventEmitter(),avatar=new EventEmitter(),doc=new EventEmitter();const timers=new Map(),sent=[];let id=0;
  for(const node of [root,avatar,doc]){node.addEventListener=node.on.bind(node);node.removeEventListener=node.removeListener.bind(node);}
  avatar.contains=target=>target===avatar;root.document=doc;
  const context={window:root,setTimeout(fn){timers.set(++id,fn);return id;},clearTimeout(value){timers.delete(value);}};
  vm.runInNewContext(fs.readFileSync(path.join(desktop,'token-hover.js'),'utf8'),context);
  let reset,removed=false;
  const hover=root.GorkTokenHover.attach(avatar,{setTokenHover:async value=>{sent.push(value);},onTokenReset(fn){reset=fn;return ()=>{removed=true;};}});
  avatar.emit('pointerenter');avatar.emit('pointerenter');assert.deepEqual(sent,[true]);
  avatar.emit('pointerleave');avatar.emit('pointerenter');assert.equal(timers.size,0);
  avatar.emit('keydown',{key:'Escape'});assert.deepEqual(sent,[true,false]);
  avatar.emit('focusin');avatar.emit('focusout',{relatedTarget:avatar});assert.equal(timers.size,0);
  avatar.emit('focusout',{relatedTarget:null});for(const fn of timers.values())fn();assert.deepEqual(sent,[true,false,true,false]);
  avatar.emit('pointerenter');reset();avatar.emit('pointermove');assert.deepEqual(sent.slice(-3),[true,false,true],'restore reconciles on move even if Chromium keeps its old hover target');
  hover.dispose();assert.equal(avatar.listenerCount('pointerenter'),0);assert.equal(doc.listenerCount('visibilitychange'),0);assert.equal(removed,true);
});
