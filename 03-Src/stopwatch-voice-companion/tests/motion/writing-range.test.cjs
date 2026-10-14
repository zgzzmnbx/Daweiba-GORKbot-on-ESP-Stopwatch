/* Expanded writing values use the real face clip; original bounds remain
 * independently tested without clipping in editor-render/pen-styles. */
(async()=>{
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const Config=require('../../static/motion/gork-config'),{SceneController}=require('../../static/motion/scene-controller');
const {boot}=require('./helpers/editor-harness.cjs'),{createCanvas,Path2D}=require('@napi-rs/canvas');
const specs=JSON.parse(fs.readFileSync(path.join(__dirname,'../../static/motion/field-specs.json'),'utf8'));
assert.deepEqual(specs,Config.fields,'browser/backend bounds must agree');
const fields=['x','y','scale','penScale','strokeWidth'];
const app=await boot();app.c.gorkEditor.selectScene('writing');
for(const key of fields){const input=app.find('writing-'+key),meta=Config.fields.writing[key];assert.equal(Number(input.min),meta[1]);assert.equal(Number(input.max),meta[2]);input.value=String(meta[2]);input.fire('change');}
app.nodes['expression-name'].value='扩展书写';app.nodes.save.click();for(let i=0;i<30;i++)await Promise.resolve();
const record=app.c.librarySnapshot(),id=app.c.gorkEditor.getEditingId();
const reopened=await boot(new Map(),{libraryInput:record});reopened.nodes['custom-expression'].value=id;reopened.nodes['custom-expression'].fire('change');
for(const key of fields)assert.equal(reopened.c.gorkEditor.getConfig().scenes.writing.writing[key],Config.fields.writing[key][2]);
const env={Path2D};env.window=env;vm.createContext(env);
for(const file of ['../avatar-engine.js','../avatar-presets.js','gork-pens.js','gork-renderer.js'])vm.runInContext(fs.readFileSync(path.join(__dirname,'../../static/motion',file),'utf8'),env);
const canvas=createCanvas(900,680),ctx=canvas.getContext('2d'),renderer=env.GorkRenderer.create(canvas);let frames=0;
for(const style of ['quill','nib','pencil','brush'])for(const mode of ['min','max','mixed']){
 const config=Config.defaults(),w=config.scenes.writing.writing;w.penStyle=style;
 for(const key of fields)w[key]=Config.fields.writing[key][mode==='min'?1:mode==='max'?2:key.length%2?1:2];
 const control=new SceneController({config});control.set('writing',0);
 for(const time of [200,1250,3000,5000]){const pose=control.sample(time);for(const value of Object.values(pose))assert(Number.isFinite(value));renderer.draw(pose);const pixels=ctx.getImageData(0,0,900,680).data;
  for(let y=0;y<680;y++)for(let x=0;x<900;x++){const i=(y*900+x)*4;if(pixels[i+3]<5)continue;assert(Math.hypot(x+.5-450,y+.5-300-pose.bob)<233,'extended drawing escapes production face clip');}frames++;
 }
}
console.log(JSON.stringify({result:'PASS expanded writing bounds, actual editor save/reopen, browser/backend schema parity, four pens min/max/mixed production clipping',frames,clipDisabled:false}));
})().catch(error=>{console.error(error);process.exitCode=1;});
