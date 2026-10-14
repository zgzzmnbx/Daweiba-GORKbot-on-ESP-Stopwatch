const assert=require('node:assert/strict'),fs=require('fs'),vm=require('vm'),path=require('path'),Config=require('../../static/motion/gork-config'),Pens=require('../../static/motion/gork-pens'),{SceneController}=require('../../static/motion/scene-controller');
const legacy=JSON.parse(fs.readFileSync(__dirname+'/fixtures/config-v1.json','utf8'));legacy.scenes.writing.writing.handScale=1.15;legacy.scenes.writing.writing.penScale=.8;
const migrated=Config.validate(legacy);assert.equal(migrated.version,2);assert.equal(migrated.scenes.writing.writing.penStyle,'quill');assert.equal(migrated.scenes.writing.writing.penScale,.8);assert(!('handScale'in migrated.scenes.writing.writing));
assert.equal(legacy.version,1);assert('handScale'in legacy.scenes.writing.writing);
const invalid=structuredClone(legacy);invalid.scenes.writing.writing.evil='script';assert.throws(()=>Config.validate(invalid));invalid.scenes.writing.writing.handScale=999;delete invalid.scenes.writing.writing.evil;assert.throws(()=>Config.validate(invalid));
const {createCanvas,Path2D}=require(process.env.GORK_CANVAS_MODULE||'@napi-rs/canvas');const env={Path2D};env.window=env;vm.createContext(env);
for(const f of ['../avatar-engine.js','../avatar-presets.js','gork-pens.js','gork-renderer.js'])vm.runInContext(fs.readFileSync(path.join(__dirname,'../../static/motion',f),'utf8'),env);
const canvas=createCanvas(900,680),ctx=canvas.getContext('2d');if(process.env.GORK_NO_CLIP==='1')ctx.clip=()=>{};const renderer=env.GorkRenderer.create(canvas);let checked=0;
function inspect(p){renderer.draw(p);const d=ctx.getImageData(0,0,900,680).data;for(let y=0;y<680;y++)for(let x=0;x<900;x++){const i=(y*900+x)*4;if(d[i+3]<5)continue;assert(d[i]===d[i+1]&&d[i+1]===d[i+2]);const r=Math.hypot(x+.5-450,y+.5-300-p.bob);assert(r<233,`outside circle ${r}`);}checked++;}
function save(name){const proof=createCanvas(900,680),c=proof.getContext('2d');c.fillStyle='#fff';c.fillRect(0,0,900,680);c.drawImage(canvas,0,0);fs.writeFileSync(path.join(process.env.GORK_PROOF_DIR||__dirname,name+'.png'),proof.toBuffer('image/png'));}
const originalWriting={x:[-65,65],y:[35,140],scale:[.65,1.25],penScale:[.6,1.25],strokeWidth:[1.5,5]};
for(const style of Pens.styles){const config=Config.defaults();config.scenes.writing.writing.penStyle=style;assert.equal(Config.parse(Config.stringify(config)).scenes.writing.writing.penStyle,style);
 for(const bound of ['default','min','max']){const c=Config.clone(config),w=c.scenes.writing.writing;if(bound!=='default')for(const [key,bounds]of Object.entries(originalWriting))w[key]=bounds[bound==='min'?0:1];const scene=new SceneController({config:c});scene.set('writing',0);
 for(const t of [0,200,700,1250,1600,2800,3900,6200,7900,8440]){const p=scene.sample(t);if(t>=1250){const nib=Pens.trace(p.ink);assert(Math.abs(p.penX-nib.tip.x)<1e-8);assert(Math.abs(p.penY-nib.tip.y)<1e-8);}inspect(p);}if(bound==='default'){inspect(scene.sample(3000));save('pen-'+style);}scene.complete(8700);for(const t of [8710,8900,9200,9700])inspect(scene.sample(t));
 }
}
const bad=Config.defaults();bad.scenes.writing.writing.penStyle='unknown';assert.throws(()=>Config.validate(bad));
const rapid=new SceneController();for(let i=0;i<200;i++){rapid.set(['writing','question','loading','idle'][i%4],i*12);for(const v of Object.values(rapid.sample(i*12+1)))assert(Number.isFinite(v));}rapid.cancel(3000);const p=rapid.sample(6000);assert.equal(p.pen,0);assert.equal(p.paper,0);
console.log(JSON.stringify({result:'PASS v1 migration/roundtrip, 4 pen styles original default/min/max, exact nib/path alignment, unclipped circle bounds, enter/exit and rapid switches',frames:checked,clipDisabled:process.env.GORK_NO_CLIP==='1'}));
