const test=require('node:test'),assert=require('node:assert/strict'),{EventEmitter}=require('node:events');
const model=require('../indicator-model'),{createIndicatorWindow,placement}=require('../indicator-window');
const {tokenPlacement,createTokenWindow}=require('../token-window');
test('hover details yield to the persistent strip at small sizes and both desktop edges',()=>{
 const area={x:0,y:0,width:1920,height:1080},a={x:1700,y:15,width:144,height:168};
 const strip=placement(a,area,3),oldCard=tokenPlacement(a,area,185).bounds;
 assert.deepEqual(placement(a,area,3,[oldCard]),strip,'temporary cards never displace the persistent strip');
 for(const scale of [.25,.6,.76,1,1.5])for(const count of [1,3,5])for(const x of [0,1700])for(const height of [240,480]){
  const avatar={x,y:200,width:240*scale,height:280*scale};
  const fixed=placement(avatar,area,count),card=tokenPlacement(avatar,area,height,fixed).bounds;
  assert(card.x+card.width<=fixed.x||card.x>=fixed.x+fixed.width||card.y+card.height<=fixed.y||card.y>=fixed.y+fixed.height,'card clears fixed numeric strip');
  assert.deepEqual(placement(avatar,area,count),fixed);
 }
});
test('real window controllers keep numeric bounds across hover, expansion, data updates and dismissal',async()=>{
 const a=new EventEmitter();a.webContents=new EventEmitter();let card,strip,depth=0;const created=[];
 a.isDestroyed=()=>false;a.isVisible=()=>true;a.isMinimized=()=>false;a.isAlwaysOnTop=()=>true;a.getBounds=()=>({x:1700,y:200,width:182,height:213});
 class Window extends EventEmitter{
  constructor(){super();created.push(this);this.webContents={send(){},setWindowOpenHandler(){},on(){}};}
  isDestroyed(){return false;}setIgnoreMouseEvents(){}loadFile(){}getBounds(){return this.bounds;}setBounds(b){this.bounds=b;}getBounds(){return this.bounds;}setAlwaysOnTop(){}isVisible(){return this.visible;}showInactive(){this.visible=true;}hide(){this.visible=false;}destroy(){this.emit('closed');}
 }
 const shared={BrowserWindow:Window,screen:{getDisplayMatching:()=>({workArea:{x:0,y:0,width:1920,height:1080}})},avatar:a,readUsage:async()=>({status:'available',total_tokens:100}),readQuota:async()=>({status:'available',buckets:{}}),timers:{setInterval:()=>1,clearInterval(){}}};
 strip=createIndicatorWindow({...shared,getSettings:()=>({mode:'bubbles',items:['quota','tokens','proxy']}),onLayout(){assert(++depth<3,'layout callbacks must not cycle');card?.sync();depth--;}});
 card=createTokenWindow({...shared,getIndicatorBounds:()=>strip.visibleBounds()});
 a.emit('show');created[0].emit('ready-to-show');strip.traffic({enabled:true});await new Promise(r=>setImmediate(r));
 const original={...created[0].bounds};
 for(let i=0;i<3;i++){
  card.setHover(true);if(i===0)created[1].emit('ready-to-show');await new Promise(r=>setImmediate(r));
  for(const height of [240,480,240]){card.setHeight(height);strip.traffic({enabled:true});assert.deepEqual(created[0].bounds,original);}
  card.setHover(false);assert.deepEqual(created[0].bounds,original);
 }
 card.destroy();strip.destroy();
});
test('indicator selections preserve empty choice, reject invalid writes and normalize old state',()=>{
 assert.equal(model.normalize(null).mode,'bubbles');assert.deepEqual(model.normalize({mode:'menu',items:[]}),{mode:'menu',items:[]});
 assert.equal(model.valid({mode:'bubbles',items:['tokens','tokens']}),false);assert.equal(model.valid({mode:'other',items:[]}),false);assert.equal(model.valid({mode:'menu',items:['secret']}),false);
});
test('numbers distinguish unavailable and zero; quotas use actual minimum and expired values stay unknown',()=>{
 const settings={mode:'bubbles',items:model.keys},data={traffic:{enabled:true,physical:{status:'available',up_speed:1024,down_speed:1024},clash:{status:'available',latest:{proxy_up_speed:0,proxy_down_speed:0},routes:{PROXY:{upload:0,download:1024}}}},tokens:{status:'available',total_tokens:66120000},quota:{status:'available',buckets:{x:{windows:[{name:'5小时',remaining_percent:50},{name:'7天',remaining_percent:84}]}}}};
 const rows=model.rows(settings,data);assert.deepEqual(rows.map(r=>r.text),['1.00KB','50%','66.1M','2.00K/s','0/s']);assert.match(rows[1].title,/5小时/);
 data.quota.stale=true;data.tokens.stale=true;data.traffic.enabled=false;
 assert(model.rows(settings,data).every(row=>row.text==='—'));assert(model.rows(settings).every(row=>row.text==='—'));
});
test('five selected bubbles fit desktop edges independently of 25–150 percent avatar scale',()=>{
 for(const factor of [.25,.6,.76,1,1.5])for(const count of [1,3,5])for(const edge of [false,true]){
  const area={x:-1920,y:-200,width:1920,height:1080},a={x:edge?-60:-1900,y:edge?800:-200,width:240*factor,height:280*factor};
  const b=placement(a,area,count);assert(b.x>=area.x&&b.y>=area.y&&b.x+b.width<=0&&b.y+b.height<=880);
 }
 const area={x:0,y:0,width:1920,height:1080},a={x:600,y:300,width:240,height:280};
 const below=placement(a,area,5);assert.deepEqual(placement(a,area,5,[below]),below,'even speech updates cannot displace numeric bubbles');
});
const tick=()=>new Promise(r=>setImmediate(r));
test('selected-only polling, late result rejection, mode changes and visibility cleanup',async()=>{
 const a=new EventEmitter();a.webContents=new EventEmitter();let visible=true,settings={mode:'bubbles',items:['tokens']},win,reads=0,quotas=0,release;const timers=new Map();
 a.isDestroyed=()=>false;a.isVisible=()=>visible;a.isMinimized=()=>false;a.isAlwaysOnTop=()=>true;a.getBounds=()=>({x:50,y:50,width:60,height:70});
 class Window extends EventEmitter{constructor(){super();this.webContents={send:(_n,v)=>this.rows=v,setWindowOpenHandler(){},on(){}};win=this;}isDestroyed(){return false;}loadFile(){}setBounds(b){this.bounds=b;}getBounds(){return this.bounds;}setAlwaysOnTop(){}isVisible(){return this.visible;}showInactive(){this.visible=true;}hide(){this.visible=false;}destroy(){this.emit('closed');}}
 const panel=createIndicatorWindow({BrowserWindow:Window,screen:{getDisplayMatching:()=>({workArea:{x:0,y:0,width:1000,height:800}})},avatar:a,getSettings:()=>settings,readUsage:()=>{reads++;return new Promise(r=>release=r);},readQuota:async()=>{quotas++;return {};},timers:{setInterval(fn){timers.set(1,fn);return 1;},clearInterval(id){timers.delete(id);}}});
 a.emit('show');win.emit('ready-to-show');await tick();assert.equal(reads,1);assert.equal(quotas,0);
 visible=false;a.emit('hide');release({status:'available',total_tokens:100});await tick();assert.equal(win.visible,false);assert.equal(timers.size,0);
 visible=true;a.emit('show');await tick();release({status:'available',total_tokens:200});await tick();assert.equal(win.rows[0].text,'200');
 settings={mode:'menu',items:['tokens']};panel.changed();assert.equal(win.visible,false);assert.equal(timers.size,0);
 settings={mode:'bubbles',items:[]};panel.changed();assert.equal(win.visible,false);
 settings={mode:'bubbles',items:['quota']};panel.changed();await tick();assert.equal(quotas,1);assert.equal(reads,2);
 panel.destroy();assert.equal(timers.size,0);assert.equal(a.listenerCount('show'),0);
});

test('traffic toggle hides only traffic metrics and restores the original selection',()=>{
 const settings={mode:'bubbles',items:['vpn','quota','tokens','network','proxy']};
 assert.deepEqual(model.rows(settings,{traffic:{enabled:false}}).map(r=>r.key),['quota','tokens']);
 assert.deepEqual(model.rows(settings).map(r=>r.key),['quota','tokens']);
 assert.deepEqual(model.rows(settings,{traffic:{enabled:true}}).map(r=>r.key),settings.items);
 assert.deepEqual(model.rows({mode:'bubbles',items:['network']},{traffic:{enabled:false}}),[]);
});
