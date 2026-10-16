const test=require('node:test'),assert=require('node:assert/strict'),{EventEmitter}=require('node:events');
const {createIndicatorWindow,placement}=require('../indicator-window');
const {bubblePlacement}=require('../bubble-window');
test('speech positions clear the stable numeric strip and respect selected side when space exists',()=>{
 const area={x:0,y:0,width:1920,height:1080};
 for(const scale of [.25,.76,1,1.5])for(const side of ['above','below','left','right']){
  const a={x:700,y:350,width:240*scale,height:280*scale},strip=placement(a,area,5);
  const {bounds:b,side:chosen}=bubblePlacement(a,area,'Codex 额度下降2个百分点',side,strip);
  assert(b.x+b.width<=strip.x||b.x>=strip.x+strip.width||b.y+b.height<=strip.y||b.y>=strip.y+strip.height);
  assert.equal(chosen,side);
 }
});
test('dragging numbers moves avatar, keeps strip nearby, persists avatar and rolls back on cancel or failure',()=>{
 const avatar=new EventEmitter();avatar.webContents=new EventEmitter();let win,cursor={x:0,y:0},saves=0,fail=false,shown=true,settings={mode:'bubbles',items:['proxy']};
 let bounds={x:600,y:300,width:240,height:280};
 avatar.isDestroyed=()=>false;avatar.isVisible=()=>shown;avatar.isMinimized=()=>false;avatar.isAlwaysOnTop=()=>true;avatar.getBounds=()=>bounds;
 avatar.setBounds=b=>{bounds={...b};avatar.emit('move');};
 class Window extends EventEmitter{constructor(){super();win=this;this.webContents={send:(_n,rows)=>this.rows=rows,setWindowOpenHandler(){},on(){}};}isDestroyed(){return false;}loadFile(){}setBounds(b){this.bounds=b;}getBounds(){return this.bounds;}isVisible(){return this.visible;}showInactive(){this.visible=true;}hide(){this.visible=false;}setAlwaysOnTop(){}destroy(){this.emit('closed');}}
 const area={x:0,y:0,width:1920,height:1080};
 const panel=createIndicatorWindow({BrowserWindow:Window,avatar,screen:{getDisplayMatching:b=>({workArea:b.x<0?{...area,x:-1920}:area}),getCursorScreenPoint:()=>cursor},getSettings:()=>settings,onDragEnd(){if(fail)throw Error('save failed');saves++;},timers:{setInterval:()=>1,clearInterval(){}}});
 avatar.emit('show');win.emit('ready-to-show');assert.equal(win.visible,false,'traffic-only strip hidden while disabled');
 panel.traffic({enabled:true});const initial={...win.bounds},start={...bounds};
 assert.throws(()=>panel.dragRequest({phase:'start',id:1}),/origin/);
 cursor={x:initial.x+10,y:initial.y+10};panel.dragRequest({phase:'start',id:1});cursor={x:cursor.x+120,y:cursor.y-80};panel.dragRequest({phase:'move',id:1});
 assert.equal(bounds.x,start.x+120);assert.equal(bounds.y,start.y-80);assert.deepEqual(win.bounds,placement(bounds,area,1));
 const moved={...win.bounds};panel.traffic({enabled:true});assert.deepEqual(win.bounds,moved);
 assert.equal(panel.dragRequest({phase:'end',id:1}).dragged,true);assert.equal(saves,1);
 const saved={...bounds},strip={...win.bounds};cursor={x:strip.x+10,y:strip.y+10};panel.dragRequest({phase:'start',id:2});cursor.x+=2;assert.equal(panel.dragRequest({phase:'end',id:2}).dragged,false);assert.equal(saves,1);assert.deepEqual(bounds,saved);
 cursor={x:strip.x+10,y:strip.y+10};panel.dragRequest({phase:'start',id:3});cursor.x+=150;panel.dragRequest({phase:'move',id:3});panel.dragRequest({phase:'cancel',id:3});assert.deepEqual(bounds,saved);
 cursor={x:strip.x+10,y:strip.y+10};panel.dragRequest({phase:'start',id:4});cursor.x+=150;fail=true;assert.throws(()=>panel.dragRequest({phase:'end',id:4}),/save failed/);assert.deepEqual(bounds,saved);fail=false;
 cursor={x:strip.x+10,y:strip.y+10};panel.dragRequest({phase:'start',id:5});cursor={x:-800,y:500};panel.dragRequest({phase:'end',id:5});assert(bounds.x<0,'negative secondary display coordinates remain valid');
 cursor={x:win.bounds.x+10,y:win.bounds.y+10};panel.dragRequest({phase:'start',id:6});shown=false;avatar.emit('hide');shown=true;avatar.emit('show');assert.equal(panel.dragRequest({phase:'end',id:6}).cancelled,true);
 panel.traffic({enabled:false});assert.equal(win.visible,false);assert.deepEqual(settings.items,['proxy'],'disabled traffic preserves selection');
 panel.traffic({enabled:true});assert.equal(win.visible,true);assert.equal(win.rows[0].key,'proxy');
 panel.destroy();
});
