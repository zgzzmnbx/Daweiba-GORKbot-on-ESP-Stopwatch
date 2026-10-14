/* Isolated library thumbnails and hover previews; no desktop writes. AGPL-3.0-only. */
(function(root){'use strict';
root.GorkMotionPreview={mount(canvas,entry,options={}){
 const config=root.GorkConfig.validate(entry.config);
 if(options.still){const controller=new root.GorkScenes.SceneController({config});controller.set(entry.scene,0);root.GorkRenderer.create(canvas,{fit:'avatar'}).draw(controller.sample(config.scenes[entry.scene].motion.enterMs+2500));return {dispose(){}};}
 const reduced=root.matchMedia?.('(prefers-reduced-motion: reduce)')?.matches;
 const player=root.GorkScenePlayer.mount(canvas,config,{fit:'avatar',reducedMotion:reduced});player.set(entry.scene,{force:true,mode:'loop'});return player;
}};
})(typeof window!=='undefined'?window:globalThis);
