/* Standalone config consumer and desktop integration seam. AGPL-3.0-only. */
(function(root){'use strict';
function mount(canvas,config=root.GorkConfig.defaults(),options={}){
 const controller=new root.GorkScenes.SceneController({now:0,config,reducedMotion:!!options.reducedMotion}),renderer=root.GorkRenderer.create(canvas,options),doc=root.document;
 let elapsed=0,last=performance.now(),paused=!!options.paused,stopped=false,raf=0,onceAt=null,returning=false,hidden=!!doc?.hidden,pageSuspended=false;
 const state=()=>({...controller.snapshot(elapsed),paused,reducedMotion:controller.reducedMotion,hidden:hidden||pageSuspended,elapsed});
 function resize(){const rect=canvas.getBoundingClientRect(),dpr=Math.min(2,root.devicePixelRatio||1);if(rect.width){const w=Math.round(rect.width*dpr),h=Math.round(rect.height*dpr);if(canvas.width!==w||canvas.height!==h){canvas.width=w;canvas.height=h;}}}
 function render(){resize();const p=controller.sample(elapsed);p.reduced=controller.reducedMotion;renderer.draw(p);options.onFrame?.(state());}
 function schedule(){if(!stopped&&!hidden&&!pageSuspended&&!raf)raf=requestAnimationFrame(tick);}
 function tick(now){raf=0;if(stopped||hidden||pageSuspended)return;if(!paused)elapsed+=Math.min(100,Math.max(0,now-last));last=now;if(onceAt!==null&&elapsed>=onceAt){onceAt=null;if(controller.scene==='idle'&&options.onIdle){options.onIdle();return;}controller.complete(elapsed);returning=true;}render();if(returning&&controller.scene==='idle'&&controller.phase==='loop'&&options.onIdle){returning=false;options.onIdle();return;}schedule();}
 function syncVisibility(){hidden=!!doc?.hidden;last=performance.now();if(hidden||pageSuspended){cancelAnimationFrame(raf);raf=0;}else{render();schedule();}}
 function pageHide(event){if(event.persisted){pageSuspended=true;syncVisibility();}else dispose();}
 function pageShow(){pageSuspended=false;syncVisibility();}
 function set(scene,opts={}){if(scene===controller.scene&&!opts.force)return;returning=false;controller.set(scene,elapsed);onceAt=opts.mode==='once'&&(scene!=='idle'||options.onIdle)?elapsed+controller.config.scenes[scene].motion.enterMs+({idle:5600,loading:2000,writing:7199,question:3200}[scene]/controller.config.scenes[scene].motion.speed):null;if(Number.isFinite(opts.startedAt))controller.started=elapsed-Math.max(0,Date.now()-opts.startedAt);render();}
 function dispose(){if(stopped)return;stopped=true;cancelAnimationFrame(raf);raf=0;doc?.removeEventListener?.('visibilitychange',syncVisibility);root.removeEventListener?.('pagehide',pageHide);root.removeEventListener?.('pageshow',pageShow);}
 doc?.addEventListener?.('visibilitychange',syncVisibility);root.addEventListener?.('pagehide',pageHide);root.addEventListener?.('pageshow',pageShow);schedule();
 return {set,setConfig(value){controller.setConfig(value);render();},getConfig:()=>root.GorkConfig.clone(controller.config),pause(value=true){paused=!!value;last=performance.now();render();},isPaused:()=>paused,replay(){set(controller.scene,{force:true});},complete(){onceAt=null;if(controller.scene==='idle'&&options.onIdle)return options.onIdle();returning=true;controller.complete(elapsed);render();},cancel(){onceAt=null;if(controller.scene==='idle'&&options.onIdle)return options.onIdle();returning=true;controller.cancel(elapsed);render();},getState:state,setReducedMotion(value){controller.reducedMotion=!!value;render();},dispose};
}
root.GorkScenePlayer={mount};
})(typeof window!=='undefined'?window:globalThis);
