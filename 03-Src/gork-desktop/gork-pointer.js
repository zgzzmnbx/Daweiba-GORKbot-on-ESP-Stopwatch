/* Adapted from Astra 03-Src/studio/gork-pointer.ts. Uses the player's existing RAF. */
(function(root) {
  const clamp = v => Math.max(-1, Math.min(1, v));
  function createPointerLook(env) {
    let x=0,y=0,followX=0,followY=0,weight=0,lastMove=-Infinity,previous=env.now();
    function reset() {x=y=followX=followY=weight=0;lastMove=-Infinity;previous=env.now();}
    function update(e) {
      if (!e) {reset();return;}
      if (!env.enabled() || e.pointerType==='touch' || !Number.isFinite(e.clientX) || !Number.isFinite(e.clientY)) return;
      const r=env.rect(),v=e.viewport||env.viewport();
      x=clamp((e.clientX-r.left-r.width/2)/Math.max(140,v.width*.35))*35;
      y=-clamp((e.clientY-r.top-r.height/2)/Math.max(140,v.height*.35))*28;
      lastMove=env.now();
    }
    function apply(pose) {
      if (!env.enabled()) {reset();return pose;}
      const now=env.now(),dt=Math.min(100,Math.max(0,now-previous));previous=now;
      const alpha=1-Math.exp(-dt/260);
      let dx=(x-followX)*alpha,dy=(y-followY)*alpha;
      const distance=Math.hypot(dx,dy),limit=90*dt/1000;
      if (distance>limit && distance>0) {dx*=limit/distance;dy*=limit/distance;}
      followX+=dx;followY+=dy;
      weight+=(Number(now-lastMove<2200)-weight)*(1-Math.exp(-dt/180));
      if (weight<.001) {weight=0;return pose;}
      return {...pose,headX:pose.headX+(followY-pose.headX)*weight,headY:pose.headY+(followX-pose.headY)*weight};
    }
    return {update,apply,reset};
  }
  const looks=new WeakMap();let wrapped=false;
  function attach(canvas, enabled) {
    if (!wrapped) {
      const original=root.GorkAppearance.draw;
      root.GorkAppearance.draw=(ctx,pose,blink,appearance)=>original(ctx,looks.get(ctx.canvas)?.apply(pose)||pose,blink,appearance);
      wrapped=true;
    }
    const reduced=root.matchMedia('(prefers-reduced-motion: reduce)');
    const look=createPointerLook({now:()=>performance.now(),rect:()=>canvas.getBoundingClientRect(),
      viewport:()=>({width:root.innerWidth,height:root.innerHeight}),enabled:()=>!root.document.hidden&&!reduced.matches&&enabled()});
    looks.set(canvas,look);
    const local=e=>look.update(e),reset=()=>look.reset();
    const unsubscribe=root.gorkDesktop?.onPointer?.(look.update);
    if (!unsubscribe) root.addEventListener('pointermove',local,{passive:true});
    root.document.addEventListener('visibilitychange',reset);
    reduced.addEventListener('change',reset);
    function dispose() {
      unsubscribe?.();root.removeEventListener('pointermove',local);
      root.document.removeEventListener('visibilitychange',reset);reduced.removeEventListener('change',reset);
      root.removeEventListener('pagehide',dispose);look.reset();looks.delete(canvas);
    }
    root.addEventListener('pagehide',dispose,{once:true});
    return {reset,dispose};
  }
  const api={createPointerLook,attach};
  if (typeof module!=='undefined') module.exports=api;
  else root.GorkDesktopPointer=api;
})(typeof window!=='undefined'?window:globalThis);
