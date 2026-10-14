const {createCanvas,Path2D}=require(process.env.GORK_CANVAS_MODULE||'@napi-rs/canvas');
const fs=require('fs'),vm=require('vm'),assert=require('node:assert/strict'),path=require('path'),Config=require('../../static/motion/gork-config.js'),{SceneController}=require('../../static/motion/scene-controller.js');
const context={Path2D};context.window=context;vm.createContext(context);
for(const file of ['../avatar-engine.js','../avatar-presets.js','gork-pens.js','gork-renderer.js'])vm.runInContext(fs.readFileSync(path.join(__dirname,'../../static/motion',file),'utf8'),context);
const canvas=createCanvas(900,680),ctx=canvas.getContext('2d');if(process.env.GORK_NO_CLIP==='1')ctx.clip=()=>{};
const renderer=context.GorkRenderer.create(canvas);let checked=0,maxRadius=0;
function inspect(p,label){renderer.draw(p);const data=ctx.getImageData(0,0,900,680).data;for(let y=0;y<680;y++)for(let x=0;x<900;x++){const i=(y*900+x)*4;if(data[i+3]<5)continue;assert(data[i]===data[i+1]&&data[i+1]===data[i+2],label+': colored pixel');const r=Math.hypot(x+.5-450,y+.5-(300+p.bob));assert(r<233,label+': pixel outside head '+r);if(data[i]>20)maxRadius=Math.max(maxRadius,r);}checked++;}
function save(name){const proof=createCanvas(900,680),c=proof.getContext('2d');c.fillStyle='#fff';c.fillRect(0,0,900,680);c.drawImage(canvas,0,0);fs.writeFileSync(path.join(process.env.GORK_PROOF_DIR||__dirname,name+'.png'),proof.toBuffer('image/png'));}
// Retain the original unclipped containment contract; extended sizes have a
// separate production-clipping acceptance in writing-range.test.cjs.
const originalWriting={x:[-65,65],y:[35,140],scale:[.65,1.25],penScale:[.6,1.25],strokeWidth:[1.5,5]};
for(const mode of ['default','min','max','mixed']){
 const config=Config.defaults();if(mode!=='default')for(const scene of Config.sceneNames)for(const [group,vals]of Object.entries(config.scenes[scene]))for(const key of Object.keys(vals)){const f=Config.fields[group][key];vals[key]=Array.isArray(f[1])?(mode==='max'?'brush':mode==='mixed'?'nib':'quill'):mode==='min'?f[1]:mode==='max'?f[2]:(key.length%2?f[1]:f[2]);}
 if(mode!=='default')for(const [key,[min,max]]of Object.entries(originalWriting))config.scenes.writing.writing[key]=mode==='min'?min:mode==='max'?max:(key.length%2?min:max);
 const control=new SceneController({config});let now=0;
 for(const scene of Config.sceneNames){control.set(scene,now);for(const dt of [0,80,180,450,900,1700,2700,6000]){inspect(control.sample(now+dt),mode+scene+dt);}save('editor-'+mode+'-'+scene);now+=6500;control.complete(now);for(const dt of [50,200,700,1300,2600])inspect(control.sample(now+dt),mode+scene+'exit');now+=3000;}
}
console.log(JSON.stringify({result:'PASS original renderer default/min/max/mixed ranges, enter/loop/exit, monochrome and unclipped circle containment',checkedFrames:checked,maxForegroundRadius:maxRadius,clipDisabled:process.env.GORK_NO_CLIP==='1'}));
