const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const root=path.resolve(__dirname,'..');
const appearance=require('../gork-appearance');
test('appearance restricts ids and colors while keeping all ten source presets',()=>{
 assert.equal(appearance.presets.length,10);
 assert.deepEqual(appearance.normalize({id:'bad',bodyColor:'url(evil)',eyeColor:'#AABBCC'}),{id:'gork',bodyColor:'#000000',eyeColor:'#aabbcc'});
 assert.equal(appearance.normalize({id:'kirby'}).id,'kirby');
});
test('all ten source geometries render finite paths without starting static animation loops',()=>{
 const paths=[];let frames=0;
 const ctx={setTransform(){},clearRect(){},beginPath(){},arc(){},fill(){},save(){},translate(){},scale(){},clip(){},rotate(){},moveTo(){},lineTo(){},stroke(){},restore(){}};
 const scope={window:{},performance:{now:()=>0},Date,Path2D:class{constructor(p){assert.doesNotMatch(p,/NaN|Infinity|undefined/);paths.push(p);}},requestAnimationFrame(){frames++;},cancelAnimationFrame(){}};
 for(const name of ['avatar-engine.js','avatar-presets.js','gork-appearance.js','gork-catalog.js','gork-avatar.js']) {
  vm.runInNewContext(fs.readFileSync(path.join(root,name),'utf8'),scope);
  if(name==='avatar-engine.js')scope.window.AvatarProceduralEngine=scope.AvatarProceduralEngine;
 }
 for(const preset of appearance.presets)for(const seq of scope.window.GorkCatalog.sequences) {
  scope.window.GorkAvatar.mount({clientWidth:54,getContext:()=>ctx},scope.window.GorkCatalog,{still:true,appearance:{id:preset.id},expression:seq.id}).dispose();
 }
 assert.equal(frames,0);assert.ok(paths.length>400);
});
