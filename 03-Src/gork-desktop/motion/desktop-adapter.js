/* Named custom expressions; built-in playback is independent. AGPL-3.0-only. */
(function(root){'use strict';
function mount(canvas,catalog=root.GorkCatalog,options={}){
 let active=null,kind=null,appearance=options.appearance,disposed=false,name='idle',selected=null;
 let entries=new Map();
 function legacy(scene='idle',opts={}){
  active?.dispose();kind='legacy';name=scene;selected=null;
  active=root.GorkAvatar.mount(canvas,catalog,{...options,appearance,onIdle(){if(!disposed)legacy('idle',{force:true});}});
  active.set(scene,opts);
 }
 function playCustom(entry,opts={}){
  if(disposed)return;
  if(!entry||!/^motion-[0-9a-f]{12}$/.test(entry.id)||!root.GorkConfig.sceneNames.includes(entry.scene))throw Error('自定义表情无效');
  const config=root.GorkConfig.validate(entry.config);
  active?.dispose();kind='scenes';name=entry.id;selected={...entry,config};
  // Selecting a custom expression is an explicit Play action, like the editor Play button.
  active=root.GorkScenePlayer.mount(canvas,config,{...options,fit:'avatar',reducedMotion:false,onIdle(){if(!disposed)legacy('idle',{force:true});}});
  active.set(entry.scene,{...opts,force:true});
 }
 function set(scene,opts={}){
  if(disposed||(!opts.force&&scene===name))return;
  if(entries.has(scene))return playCustom(entries.get(scene),opts);
  if(kind!=='legacy')legacy(scene,opts);else{name=scene;active.set(scene,opts);}
 }
 function dispose(){if(disposed)return;disposed=true;active?.dispose();active=null;kind=null;root.removeEventListener?.('pagehide',pagehide);}
 function pagehide(e){if(!e.persisted)dispose();}
 legacy();
 root.addEventListener?.('pagehide',pagehide);
 return {set,playCustom,setLibrary(values){const next=new Map();for(const entry of values||[]){if(!/^motion-[0-9a-f]{12}$/.test(entry.id))throw Error('自定义表情编号无效');next.set(entry.id,{...entry,config:root.GorkConfig.validate(entry.config)});}entries=next;},
  getConfig:()=>selected?root.GorkConfig.clone(selected.config):null,getState:()=>({kind,name,...active?.getState?.()}),
  setAppearance(value){appearance=root.GorkAppearance?.normalize(value)||value;if(kind==='legacy')active.setAppearance?.(value);},
  complete(){if(kind==='scenes')active.complete();},cancel(){if(kind==='scenes')active.cancel();},dispose};
}
root.GorkDesktopSceneAdapter={mount};
})(typeof window!=='undefined'?window:globalThis);
