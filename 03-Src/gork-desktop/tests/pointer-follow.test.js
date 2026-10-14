const test=require('node:test'),assert=require('node:assert/strict');
const {EventEmitter}=require('node:events');
const {createPointerLook}=require('../gork-pointer');
const {createCursorTracker}=require('../cursor-tracker');
function lookFixture() {
  let now=0,enabled=true;
  const pose={headX:0,headY:0,headZ:3,eye:'unchanged'};
  const look=createPointerLook({now:()=>now,enabled:()=>enabled,
    viewport:()=>({width:1920,height:1080}),rect:()=>({left:10,top:20,width:200,height:200})});
  return {look,pose,advance(ms=16){now+=ms;return look.apply(pose);},enable(value){enabled=value;}};
}
test('pointer look turns smoothly in both axes, caps its speed, and preserves the pose',()=>{
  const f=lookFixture();f.look.update({clientX:2000,clientY:-2000});
  const first=f.advance();assert(first.headX>0&&first.headY>0);
  assert(Math.hypot(first.headX,first.headY)<=90*.016);
  let pose;for(let n=0;n<100;n++)pose=f.advance();
  assert(pose.headX>27&&pose.headX<=28);assert(pose.headY>34&&pose.headY<=35);
  assert.deepEqual(f.pose,{headX:0,headY:0,headZ:3,eye:'unchanged'});
  assert.equal(pose.headZ,3);assert.equal(pose.eye,'unchanged');
  f.look.update({clientX:-2000,clientY:2000});
  const reversed=f.advance();assert(Math.hypot(reversed.headX-pose.headX,reversed.headY-pose.headY)<=90*.016+.01);
  for(let n=0;n<100;n++)pose=f.advance();assert(pose.headX< -27&&pose.headY< -34);
});
test('stationary cursor expires; disabling, hiding and reset remove stale look immediately',()=>{
  const f=lookFixture();f.look.update({clientX:2000,clientY:120});
  for(let n=0;n<100;n++)f.advance();
  for(let n=0;n<250;n++)f.advance();assert.strictEqual(f.advance(),f.pose);
  f.look.update({clientX:2000,clientY:120});for(let n=0;n<50;n++)f.advance();
  f.enable(false);assert.strictEqual(f.advance(),f.pose);
  f.look.update({clientX:-2000,clientY:120});f.enable(true);assert.strictEqual(f.advance(),f.pose);
  f.look.update({clientX:2000,clientY:120});f.advance();f.look.update(null);assert.strictEqual(f.advance(),f.pose);
});
test('touch and non-finite input do not activate follow; desktop display size determines sensitivity',()=>{
  const f=lookFixture();
  for(const input of [{clientX:500,clientY:500,pointerType:'touch'},{clientX:NaN,clientY:0},{clientX:0,clientY:Infinity}])f.look.update(input);
  assert.strictEqual(f.advance(),f.pose);
  f.look.update({clientX:446,clientY:120,viewport:{width:1920,height:1080}});
  let pose;for(let n=0;n<100;n++)pose=f.advance();assert(Math.abs(pose.headY-17.5)<.1);
});
function trackerFixture() {
  const win=new EventEmitter();win.webContents=new EventEmitter();const sent=[];
  win.webContents.send=(...args)=>sent.push(args);
  let visible=false,minimized=false,destroyed=false,point={x:-1100,y:300};
  let bounds={x:-1200,y:200,width:240,height:280},reads=0,next=0;
  win.isVisible=()=>visible;win.isMinimized=()=>minimized;win.isDestroyed=()=>destroyed;win.getContentBounds=()=>bounds;
  const ticks=new Map(),display={x:-1920,y:0,width:1920,height:1080};
  const screen={getCursorScreenPoint:()=>{reads++;return point;},getDisplayMatching:()=>({bounds:display,scaleFactor:1.5})};
  const tracker=createCursorTracker(win,screen,{timers:{setInterval(fn,ms){assert.equal(ms,50);ticks.set(++next,fn);return next;},clearInterval(id){ticks.delete(id);}}});
  return {win,sent,tracker,ticks,reads:()=>reads,tick:()=>{for(const fn of ticks.values())fn();},
    show(){visible=true;win.emit('show');},hide(){visible=false;win.emit('hide');},
    minimize(){minimized=true;win.emit('minimize');},restore(){minimized=false;win.emit('restore');},
    move(p){point=p;},bounds(b){bounds=b;},destroy(){destroyed=true;win.emit('closed');}};
}
test('global cursor works outside avatar with negative monitor origin, DIP, move/resize and reload',()=>{
  const f=trackerFixture();f.tick();assert.equal(f.reads(),0);
  f.show();assert.deepEqual(f.sent.at(-1),['gork:pointer',{clientX:100,clientY:100,viewport:{width:1920,height:1080}}]);
  const count=f.sent.length;f.tick();assert.equal(f.sent.length,count,'stationary samples must not renew 2.2s activity');
  f.move({x:500,y:700});f.tick();assert.equal(f.sent.at(-1)[1].clientX,1700,'mouse outside avatar still delivered');
  f.bounds({x:-1000,y:200,width:360,height:420});f.tick();assert.equal(f.sent.at(-1)[1].clientX,1500);
  f.win.webContents.emit('did-finish-load');assert.equal(f.ticks.size,1);
  assert.equal(f.sent.length,count+3,'reload gets current cursor without stacking timers');f.tracker.dispose();
});
test('hide/minimize/disabled/closed stop sampling; show/restore/enable resume one timer',()=>{
  const f=trackerFixture();f.show();assert.equal(f.ticks.size,1);
  f.hide();assert.equal(f.ticks.size,0);assert.equal(f.sent.at(-1)[1],null);
  const reads=f.reads();f.tick();assert.equal(f.reads(),reads);
  f.show();f.minimize();assert.equal(f.ticks.size,0);f.restore();assert.equal(f.ticks.size,1);
  f.tracker.setEnabled(false);assert.equal(f.ticks.size,0);f.show();assert.equal(f.ticks.size,0);
  f.tracker.setEnabled(true);assert.equal(f.ticks.size,1);f.destroy();assert.equal(f.ticks.size,0);
  f.show();assert.equal(f.ticks.size,0);assert.equal(f.win.listenerCount('show'),0);
});
