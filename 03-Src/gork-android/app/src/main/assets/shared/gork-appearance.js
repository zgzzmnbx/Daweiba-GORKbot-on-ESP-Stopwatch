/* Appearance selection is independent of expression playback and Watch commands. */
(function(root){
  const presets = typeof module !== 'undefined' ? require('./avatar-presets') : root.GorkPresets;
  const fallback = presets.find(p=>p.id==='gork');
  function normalize(value) {
    const preset=presets.find(p=>p.id===value?.id) || fallback;
    const color=(key,defaultValue)=>/^#[0-9a-f]{6}$/i.test(value?.[key]) ? value[key].toLowerCase() : defaultValue;
    return {id:preset.id,bodyColor:color('bodyColor',preset.colors.body),eyeColor:color('eyeColor',preset.colors.eyes)};
  }
  function draw(ctx,expression,blink,value) {
    const style=normalize(value), preset=presets.find(p=>p.id===style.id);
    const pose={...expression};
    for(const key of Object.keys(fallback.eyes)) pose[key]+=preset.eyes[key]-fallback.eyes[key];
    for(const key of ['widthLeft','widthRight','heightLeft','heightRight']) pose[key]=Math.max(10,pose[key]);
    const engine=root.AvatarProceduralEngine;
    const geometry=engine.renderAvatar(engine.poseFromExpression(pose),preset.body.primary,blink,{bodyNodes:preset.body.nodes,includeWire:false});
    const viewSize=style.id==='gork'?260:300;
    ctx.save();ctx.translate(500,500);ctx.scale(1000/viewSize,1000/viewSize);
    const fill=p=>{if(p)ctx.fill(new Path2D(p));};
    ctx.fillStyle=style.bodyColor;geometry.backPaths.forEach(fill);fill(geometry.headPath);
    ctx.save();ctx.clip(new Path2D(geometry.headPath));ctx.fillStyle=style.eyeColor;
    if(geometry.leftVisible)fill(geometry.leftPath);if(geometry.rightVisible)fill(geometry.rightPath);
    ctx.restore();ctx.fillStyle=style.bodyColor;geometry.frontPaths.forEach(fill);ctx.restore();
  }
  const api={presets,normalize,draw};
  if(typeof module!=='undefined')module.exports=api;else root.GorkAppearance=api;
})(typeof window!=='undefined'?window:this);
