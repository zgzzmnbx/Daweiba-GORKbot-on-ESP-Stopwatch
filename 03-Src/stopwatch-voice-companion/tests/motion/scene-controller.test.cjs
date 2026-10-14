const assert=require('node:assert/strict');
const {SceneController}=require('../../static/motion/scene-controller.js');
const scenes=['idle','loading','writing','question'];
for(const scene of scenes){
 const c=new SceneController();c.set(scene,100);
 let a=c.sample(200),b=c.sample(2000);Object.values(a).forEach(v=>assert(Number.isFinite(v)));Object.values(b).forEach(v=>assert(Number.isFinite(v)));
 assert.equal(c.snapshot(2000).scene,scene);assert.equal(c.snapshot(2000).phase,'loop');
 c.complete(2100);assert.equal(c.snapshot(4000).scene,'idle');assert.equal(c.snapshot(4000).phase,'loop');
 const last=c.sample(4000);for(const k of ['spinner','paper','hand','question','pen'])assert.equal(last[k],0);
}
const c=new SceneController();let now=0;
for(let i=0;i<1000;i++){now+=7;c.set(scenes[i%4],now);const values=c.sample(now+1);for(const v of Object.values(values))assert(Number.isFinite(v));}
c.cancel(now+2);let last=c.sample(now+2000);for(const k of ['spinner','paper','hand','question','pen'])assert.equal(last[k],0);assert.equal(c.scene,'idle');
assert.throws(()=>c.set('invalid',9000));
for(const scene of scenes){const reduced=new SceneController({reducedMotion:true});reduced.set(scene,0);assert.equal(reduced.snapshot(200).phase,'loop');}
console.log('PASS: all scenes enter/loop/complete; 1,000 rapid switches; cancel cleanup; invalid input; reduced motion.');
