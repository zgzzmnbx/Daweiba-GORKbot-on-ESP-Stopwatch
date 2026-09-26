const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const source=fs.readFileSync(path.resolve(__dirname,'../../stopwatch-voice-companion/static/gork-avatar.js'),'utf8');
function renderer(options={},reduced=false,wall=10000) {
  let clock=0,frame,last,frames=0,cancelled=0;
  const pose={id:'rest',headX:0,headY:0,headZ:0};
  const seq=id=>({id,steps:[{expressionId:'rest',transitionMs:400,holdMs:600,transition:'smooth'}],blink:{enabled:false}});
  const catalog={expressions:[pose],sequences:['idle','happy','thinking'].map(seq)};
  const scope={window:{devicePixelRatio:1,matchMedia:()=>({matches:reduced}),GorkAppearance:{normalize:value=>({id:value?.id||'gork'}),draw:(_,pose)=>{last={...pose};}}},performance:{now:()=>clock},Date:{now:()=>wall},requestAnimationFrame:fn=>{frame=fn;return ++frames;},cancelAnimationFrame:()=>cancelled++};
  vm.runInNewContext(source,scope);
  const face=scope.window.GorkAvatar.mount({clientWidth:100,getContext:()=>({setTransform(){},clearRect(){}})},catalog,options);
  return {face,pose,api:scope.window.GorkAvatar,draw:t=>{clock=t;frame(t);return last;},get last(){return last;},get frames(){return frames;},get cancelled(){return cancelled;}};
}
test('idle look pauses, turns in both directions, holds and smoothly returns within bounds',()=>{
  const {idleLook}=renderer().api;
  for(const t of [0,2999,3000,7400,11999,12000]) assert.equal(Math.hypot(...Object.values(idleLook(t))),0);
  assert.equal(idleLook(4200).headY,-18);assert.equal(idleLook(5900).headY,-18);
  assert.equal(idleLook(16200).headY,15);
  for(let t=0;t<=60000;t+=10){const p=idleLook(t);assert.ok(Math.abs(p.headX)<=8&&Math.abs(p.headY)<=19&&Math.abs(p.headZ)<=3);}
  for(const t of [3000,4200,6000,7400,12000]) assert.ok(Math.abs(idleLook(t+.1).headY-idleLook(t-.1).headY)<.01);
});
test('live idle Gork turns without mutating source poses; explicit states take over smoothly',()=>{
  const r=renderer();assert.equal(r.draw(2000).headY,0);assert.equal(r.draw(4500).headY,-18);
  assert.equal(r.pose.headY,0);
  r.face.set('happy');assert.equal(r.draw(4500).headY,-18);assert.equal(r.draw(5000).headY,0);
  assert.equal(r.draw(9000).headY,0);
  r.face.set('idle');assert.equal(r.draw(9500).headY,0);assert.equal(r.draw(13500).headY,-18);
  const frames=r.frames;r.face.dispose();r.draw(14000);assert.equal(r.frames,frames);assert.equal(r.cancelled,1);
});
test('still thumbnails, Watch previews, other characters and reduced-motion skip idle turns',()=>{
  for(const [options,reduced] of [[{idleMotion:false},false],[{appearance:{id:'kirby'}},false],[{},true]]){
    const r=renderer(options,reduced);assert.equal(r.draw(4500).headY,0);
  }
  const still=renderer({still:true});assert.equal(still.frames,0);assert.equal(still.last.headY,0);
});
test('late listeners share the same idle look from their scene start timestamp',()=>{
  const first=renderer({},false,10000),late=renderer({},false,13500);
  first.face.set('idle',{force:true,startedAt:10000});late.face.set('idle',{force:true,startedAt:10000});
  assert.deepEqual(first.draw(4500),late.draw(1000));
});
test('one-shot expression returns to idle and resumes occasional turns after the resting pause',()=>{
  const r=renderer();r.face.set('happy',{mode:'once'});
  assert.equal(r.draw(500).headY,0);assert.equal(r.draw(1000).headY,0);assert.equal(r.draw(3000).headY,0);assert.equal(r.draw(5500).headY,-18);
});
