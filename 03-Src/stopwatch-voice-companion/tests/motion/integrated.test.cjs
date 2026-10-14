const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const {createCanvas,Path2D}=require(process.env.GORK_CANVAS_MODULE||'@napi-rs/canvas');
const base=path.resolve(__dirname,'../../static'),Config=require(base+'/motion/gork-config'),{SceneController}=require(base+'/motion/scene-controller');
const user=Config.parse(fs.readFileSync(base+'/motion/initial-config.gork.json','utf8'));
assert.deepEqual(user,JSON.parse(fs.readFileSync(base+'/motion/initial-config.gork.json','utf8')));
assert.deepEqual(Config.fields,JSON.parse(fs.readFileSync(base+'/motion/field-specs.json','utf8')));
let time=0,id=0;const frames=new Map(),listeners=new Map();
const media={matches:false,addEventListener(){},removeEventListener(){}};
const doc={hidden:false,addEventListener(k,f){(listeners.get(k)||listeners.set(k,new Set()).get(k)).add(f);},removeEventListener(k,f){listeners.get(k)?.delete(f);}};
const env={Path2D,TextEncoder,Date,performance:{now:()=>time},document:doc,matchMedia:()=>media,
 addEventListener(){},removeEventListener(){},devicePixelRatio:1,requestAnimationFrame:f=>{frames.set(++id,f);return id;},cancelAnimationFrame:i=>frames.delete(i)};env.window=env;vm.createContext(env);
for(const file of ['gork-catalog.js','avatar-engine.js','avatar-presets.js','gork-appearance.js','gork-avatar.js','motion/gork-config.js','motion/gork-pens.js','motion/scene-controller.js','motion/gork-renderer.js','motion/gork-player.js','motion/desktop-adapter.js'])vm.runInContext(fs.readFileSync(base+'/'+file,'utf8'),env);
const canvas=createCanvas(900,680);canvas.clientWidth=900;canvas.getBoundingClientRect=()=>({width:900,height:680});
const face=env.GorkDesktopSceneAdapter.mount(canvas,env.GorkCatalog,{config:user});
assert.equal(face.getState().kind,'legacy','built-in idle must remain its original renderer');
const custom=['idle','loading','writing','question'].map((scene,i)=>({id:'motion-'+String(i+1).padStart(12,'0'),name:'custom '+scene,scene,config:user}));face.setLibrary(custom);
assert.equal(face.getState().kind,'legacy','loading a library must not change current playback');
const tick=dt=>{time+=dt;const batch=[...frames];frames.clear();for(const[,f]of batch)f(time);assert.equal(frames.size,1,'exactly one RAF');};
media.matches=true;
for(const entry of custom){face.set(entry.id,{force:true,mode:'loop'});assert.equal(face.getState().reducedMotion,false,'explicit custom Play must animate with OS reduced-motion on');for(let i=0;i<25;i++)tick(100);const pixels=canvas.toBuffer('image/png');for(let i=0;i<8;i++)tick(100);assert(!pixels.equals(canvas.toBuffer('image/png')),'each explicitly selected custom scene must move');}
media.matches=false;face.set('idle',{force:true});
for(let i=0;i<1000;i++){face.set([custom[1].id,'happy',custom[2].id,'confused',custom[3].id,'idle'][i%6],{force:true,mode:i%2?'once':'loop'});tick(16);assert([...listeners.values()].reduce((n,s)=>n+s.size,0)<=1);}
face.set('happy',{force:true,mode:'once'});for(let i=0;i<200;i++)tick(100);assert.equal(face.getState().kind,'legacy','legacy one-shot must retain original idle');
face.set(custom[2].id,{force:true,mode:'loop'});const before=JSON.stringify(face.getConfig());const changed=JSON.parse(JSON.stringify(custom));changed[2].config.scenes.writing.writing.x=-50;face.setLibrary(changed);assert.equal(JSON.stringify(face.getConfig()),before,'saving a playing custom expression must not update its snapshot');face.set('idle',{force:true});
for(const entry of custom){face.set(entry.id,{force:true,mode:'once'});for(let i=0;i<240;i++)tick(100);assert.equal(face.getState().kind,'legacy','custom once must return to original idle');}
face.setAppearance({id:'freddy'});assert.equal(face.getState().kind,'legacy');face.setAppearance({id:'gork'});assert.equal(face.getState().kind,'legacy');
face.setAppearance({id:'gork',bodyColor:'#123456'});assert.equal(face.getState().kind,'legacy','keep existing custom Gork colors');face.setAppearance({id:'gork'});assert.equal(face.getState().kind,'legacy');
face.dispose();assert.equal(frames.size,0);assert.equal([...listeners.values()].reduce((n,s)=>n+s.size,0),0);
for(let i=0;i<100;i++){const f=env.GorkDesktopSceneAdapter.mount(canvas,env.GorkCatalog,{config:user});tick(16);f.dispose();assert.equal(frames.size,0);}
const ctx=canvas.getContext('2d');if(process.env.GORK_NO_CLIP==='1')ctx.clip=()=>{};
const renderer=env.GorkRenderer.create(canvas);let checked=0,maxForegroundRadius=0;
const output=process.env.GORK_PROOF_DIR; if(output)fs.mkdirSync(output,{recursive:true});
for(const pen of ['quill','nib','pencil','brush']){
 const c=Config.clone(user);c.scenes.writing.writing.penStyle=pen;const control=new SceneController({config:c});let now=0;
 for(const name of Config.sceneNames){control.set(name,now);for(const dt of [0,80,200,450,900,1250,1800,3000,5300,8200]){
  const p=control.sample(now+dt);renderer.draw(p);const pixels=ctx.getImageData(0,0,900,680).data;
  for(let y=0;y<680;y++)for(let x=0;x<900;x++){const i=(y*900+x)*4;if(pixels[i+3]<5)continue;assert(pixels[i]===pixels[i+1]&&pixels[i+1]===pixels[i+2]);const radius=Math.hypot(x+.5-450,y+.5-300-p.bob);assert(radius<233,'user pixel outside head');if(pixels[i]>20)maxForegroundRadius=Math.max(maxForegroundRadius,radius);}
  if(output&&dt===3000)fs.writeFileSync(path.join(output,'user-'+name+'-'+pen+'.png'),canvas.toBuffer('image/png'));
  checked++;
 }now+=8500;control.complete(now);for(const dt of [40,300,1000]){renderer.draw(control.sample(now+dt));checked++;}now+=2000;}
}
console.log(JSON.stringify({result:'PASS user config, original idle unchanged, custom library save isolation, 1000 new/legacy switches, once return, 100 remounts, single RAF/listener cleanup, real user Canvas pixels all four pens',frames:checked,maxForegroundRadius,clipDisabled:process.env.GORK_NO_CLIP==='1'}));
