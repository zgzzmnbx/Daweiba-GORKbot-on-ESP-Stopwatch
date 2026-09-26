const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const desktop=path.resolve(__dirname,'..'),web=path.resolve(desktop,'../stopwatch-voice-companion/static');
test('web and desktop share identical renderer/catalog and pinned Watch poses',()=>{
  for(const name of ['gork-avatar.js','gork-catalog.js']) assert.equal(fs.readFileSync(path.join(web,name),'utf8'),fs.readFileSync(path.join(desktop,name),'utf8'));
  const scope={window:{}};vm.runInNewContext(fs.readFileSync(path.join(web,'gork-catalog.js'),'utf8'),scope);
  const source=JSON.parse(fs.readFileSync(path.resolve(desktop,'../stopwatch-grok-avatar/assets/source-grok-bot/avatar-studio-project.json'),'utf8'));
  assert.equal(JSON.stringify(scope.window.GorkCatalog.expressions),JSON.stringify(source.expressions));
  assert.equal(scope.window.GorkCatalog.sequences.length,23);
});
test('all catalog poses project to finite capsule geometry within the body',()=>{
  const scope={window:{}};
  for(const name of ['gork-catalog.js','gork-avatar.js']) vm.runInNewContext(fs.readFileSync(path.join(web,name),'utf8'),scope);
  for(const pose of scope.window.GorkCatalog.expressions) for(const side of [-1,1]) {
    const eye=scope.window.GorkAvatar.eye(pose,side);
    assert.ok(Object.values(eye).every(Number.isFinite));assert.ok(eye.w>0&&eye.h>0);
    assert.ok(Math.hypot(eye.x-500,eye.y-500)+Math.max(eye.w,eye.h)/2<500);
  }
});

test('a late desktop listener draws the same animation position from a shared start time',()=>{
  function renderer(initialWall,initialClock) {
    const calls=[]; let wall=initialWall,clock=initialClock,frame;
    const ctx={setTransform(){},clearRect(){},beginPath(){},arc(){},fill(){},save(){},translate(x,y){calls.push([x,y]);},rotate(){},moveTo(){},lineTo(){},stroke(){},restore(){}};
    const canvas={clientWidth:100,getContext:()=>ctx};
    const scope={window:{devicePixelRatio:1},performance:{now:()=>clock},Date:{now:()=>wall},requestAnimationFrame:fn=>{frame=fn;return 1;},cancelAnimationFrame(){}};
    vm.runInNewContext(fs.readFileSync(path.join(web,'gork-catalog.js'),'utf8'),scope);
    vm.runInNewContext(fs.readFileSync(path.join(web,'gork-avatar.js'),'utf8'),scope);
    const face=scope.window.GorkAvatar.mount(canvas);
    return {set:(expression,startedAt)=>face.set(expression,{startedAt,force:true}),draw:(nextWall,nextClock)=>{wall=nextWall;clock=nextClock;frame(clock);return calls.slice(-2);}};
  }
  const consoleFace=renderer(1000,100), desktopFace=renderer(1250,600);
  consoleFace.set('happy',1000); desktopFace.set('happy',1000);
  assert.deepEqual(consoleFace.draw(1500,600),desktopFace.draw(1500,850));
});

test('still thumbnails render distinct real poses without scheduling animation frames',()=>{
  let frames=0;const strokes=[];
  const ctx={setTransform(){},clearRect(){strokes.length=0;},beginPath(){},arc(...args){strokes.push(args);},fill(){},save(){},translate(x,y){strokes.push([x,y]);},rotate(angle){strokes.push(angle);},moveTo(...args){strokes.push(args);},lineTo(...args){strokes.push(args);},stroke(){strokes.push(this.lineWidth);},restore(){}};
  const scope={window:{devicePixelRatio:1},performance:{now:()=>0},Date,requestAnimationFrame:()=>{frames++;},cancelAnimationFrame(){}};
  for(const name of ['gork-catalog.js','gork-avatar.js']) vm.runInNewContext(fs.readFileSync(path.join(web,name),'utf8'),scope);
  const samples=[];
  for(const sequence of scope.window.GorkCatalog.sequences) {
    const canvas={clientWidth:54,getContext:()=>ctx};
    scope.window.GorkAvatar.mount(canvas,scope.window.GorkCatalog,{still:true,expression:sequence.id}).dispose();
    assert.equal(canvas.width,54);samples.push(JSON.stringify(strokes));
  }
  assert.equal(frames,0);assert.equal(new Set(samples).size,new Set(scope.window.GorkCatalog.sequences.map(s=>s.steps[0].expressionId)).size);
});
