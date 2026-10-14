(async()=>{
const assert=require('node:assert/strict'),{boot}=require('./helpers/editor-harness.cjs');
for(const reduced of [false,true]){
 const app=await boot(new Map(),{reduced});app.tick();
 assert.equal(app.c.gorkEditor.getState().reducedMotion,reduced);
 assert.equal(app.nodes['phase-label'].textContent,reduced?'静态预览':'循环中');
 assert.equal(app.nodes.pause.textContent,reduced?'播放循环':'暂停循环');
 for(let scene=0;scene<4;scene++){
  app.buttons[scene].click();app.advance(2100);const a=app.pixels();app.advance(1300);const b=app.pixels();
  assert.equal(a.equals(b),reduced,`scene ${scene}: reduced motion ${reduced}`);
 }
 if(reduced){assert.equal(app.nodes['motion-note'].hidden,false);app.nodes.pause.click();assert.equal(app.c.gorkEditor.getState().reducedMotion,false);assert.equal(app.nodes['follow-system'].hidden,false);}
 for(let scene=0;scene<4;scene++){
  app.buttons[scene].click();app.advance(9100);const a=app.pixels();app.advance(1100);assert(!a.equals(app.pixels()),`scene ${scene} keeps animating after a complete cycle`);
 }
 app.nodes.pause.click();assert.equal(app.c.gorkEditor.getState().paused,true);assert.equal(app.nodes['phase-label'].textContent,'已暂停');const paused=app.pixels();app.advance(1400);assert(paused.equals(app.pixels()));
 app.visibility(true);assert.equal(app.frames.size,0);const elapsed=app.c.gorkEditor.getState().elapsed;app.tick(60000);assert.equal(app.c.gorkEditor.getState().elapsed,elapsed);app.visibility(false);assert.equal(app.frames.size,1);app.advance(500);assert.equal(app.c.gorkEditor.getState().paused,true);assert(paused.equals(app.pixels()));
 app.nodes.pause.click();assert.equal(app.c.gorkEditor.getState().paused,false);app.advance(700);assert(!paused.equals(app.pixels()));
 app.visibility(true);const before=app.c.gorkEditor.getState().elapsed;app.tick(60000);app.visibility(false);app.tick(16);assert.equal(app.c.gorkEditor.getState().elapsed-before,16);assert.equal(app.frames.size,1);
 app.windowEvent('pagehide',{persisted:true});assert.equal(app.frames.size,0);app.tick(60000);app.windowEvent('pageshow',{persisted:true});assert.equal(app.frames.size,1);app.tick();assert.equal(app.c.gorkEditor.getState().paused,false);
 // Explicit Play is local to this visit, never changes the OS or exported config.
 const config=app.c.gorkEditor.exportConfig();app.preference(true);assert.equal(app.c.gorkEditor.getState().reducedMotion,false);app.nodes['follow-system'].click();assert.equal(app.c.gorkEditor.getState().reducedMotion,true);assert.equal(app.nodes['phase-label'].textContent,'静态预览');app.preference(false);assert.equal(app.c.gorkEditor.getState().reducedMotion,false);assert.equal(app.c.gorkEditor.exportConfig(),config);
 app.preference(true);app.nodes.replay.click();assert.equal(app.c.gorkEditor.getState().reducedMotion,false);app.nodes.pause.click();app.buttons[1].click();assert.equal(app.c.gorkEditor.getState().paused,false);
 app.windowEvent('pagehide',{persisted:false});assert.equal(app.frames.size,0);app.visibility(false);assert.equal(app.frames.size,0);
}
const memory=new Map(),first=await boot(memory,{reduced:false});first.buttons[2].click();first.nodes.pause.click();const reloaded=await boot(memory,{reduced:false});assert.equal(reloaded.c.gorkEditor.getState().paused,false,'pause does not persist across loads');
const initiallyHidden=await boot(new Map(),{hidden:true});assert.equal(initiallyHidden.frames.size,0);initiallyHidden.visibility(false);initiallyHidden.tick();assert.equal(initiallyHidden.frames.size,1);
console.log('PASS rendered loops with system motion on/off, explicit play/replay, honest pause/static labels, OS changes, reload, paused/running hide/show and BFCache, single RAF/disposal. Native Canvas + DOM event harness; not browser/Windows QA.');

})().catch(e=>{console.error(e);process.exitCode=1;});
