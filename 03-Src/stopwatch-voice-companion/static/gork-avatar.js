/* Shared web/desktop renderer using Watch's pinned poses and head projection.
 * Hardware IMU/touch offsets are not simulated. */
(function(root) {
  const rad=d=>d*Math.PI/180, clamp=v=>Math.max(-1,Math.min(1,v));
  const scale=1000*430/(466*240);
  function eye(p,side) {
    const s=side<0?'Left':'Right', yaw=clamp(p.headY/45/35), pitch=clamp(p.headX/45/28);
    const depth=Math.max(.74,1+side*yaw*.16-Math.abs(pitch)*.03);
    const x=(side*p.spacing/2+p['positionX'+s])*scale*(1-Math.abs(yaw)*.16)+yaw*82;
    const y=p['positionY'+s]*scale+pitch*62, roll=rad(p.headZ);
    return {x:500+x*Math.cos(roll)-y*Math.sin(roll),y:500+x*Math.sin(roll)+y*Math.cos(roll),
      w:p['width'+s]*scale*depth*(1-Math.abs(yaw)*.10),h:p['height'+s]*scale*depth*(1-Math.abs(pitch)*.05),
      angle:p[side<0?'leftAngle':'rightAngle']+p.headZ+yaw*7+side*yaw*3.5};
  }
  function mount(canvas,catalog=root.GorkCatalog) {
    const ctx=canvas.getContext('2d'), poses=Object.fromEntries(catalog.expressions.map(p=>[p.id,p]));
    const seqs=Object.fromEntries(catalog.sequences.map(s=>[s.id,s]));
    let name='idle',mode='loop',start=performance.now(),previous=poses[seqs.idle.steps[0].expressionId],current=previous,stopped=false,frame;
    function set(next,options={}) {
      next=({processing:'thinking',generating:'thinking',speaking:'happy',error:'confused',ready:'idle',sleepy:'drowsy',dizzy:'playful','happy-work':'happy'})[next]||next;
      if(!seqs[next]) next='idle';
      if(next===name&&!options.force) return;
      previous=current;name=next;mode=options.mode==='once'&&next!=='idle'?'once':'loop';
      start=Number.isFinite(options.startedAt)
        ? performance.now()-Math.max(0,Date.now()-options.startedAt)
        : performance.now();
    }
    function draw(now) {
      if(stopped) return;
      let seq=seqs[name],total=seq.steps.reduce((n,s)=>n+s.transitionMs+s.holdMs,0);
      if(mode==='once'&&now-start>=total){previous=current;name='idle';mode='loop';start=now;seq=seqs.idle;total=seq.steps.reduce((n,s)=>n+s.transitionMs+s.holdMs,0);}
      let t=(now-start)%total,from=now-start>=total?poses[seq.steps.at(-1).expressionId]:previous;
      for(const step of seq.steps) {
        const to=poses[step.expressionId],duration=step.transitionMs+step.holdMs;
        if(t<duration) {
          let a=step.transitionMs?Math.min(1,t/step.transitionMs):1;
          if(step.transition==='smooth') a=a*a*(3-2*a);
          current=Object.fromEntries(Object.keys(to).map(k=>[k,typeof to[k]==='number'?from[k]+(to[k]-from[k])*a:to[k]]));break;
        }
        t-=duration;from=to;
      }
      const size=Math.max(1,Math.round(canvas.clientWidth*(root.devicePixelRatio||1)));
      if(canvas.width!==size) canvas.width=canvas.height=size;
      ctx.setTransform(size/1000,0,0,size/1000,0,0);ctx.clearRect(0,0,1000,1000);
      ctx.fillStyle='#000';ctx.beginPath();ctx.arc(500,500,500*430/466,0,Math.PI*2);ctx.fill();
      let blink=1;
      if(seq.blink.enabled&&now-start>=seq.blink.initialDelayMs) {
        const b=(now-start-seq.blink.initialDelayMs)%seq.blink.minIntervalMs;
        if(b<seq.blink.durationMs) blink=Math.max(.05,Math.abs(2*b/seq.blink.durationMs-1));
      }
      for(const side of [-1,1]) {
        const e=eye(current,side),h=Math.max(3,e.h*blink),w=Math.max(3,e.w),vertical=h>=w,half=Math.abs(h-w)/2;
        ctx.save();ctx.translate(e.x,e.y);ctx.rotate(rad(e.angle));ctx.strokeStyle='#fff';ctx.lineWidth=Math.min(w,h);ctx.lineCap='round';ctx.beginPath();
        ctx.moveTo(vertical?0:-half,vertical?-half:0);ctx.lineTo(vertical?0:half,vertical?half:0);
        if(half<.01) {ctx.fillStyle='#fff';ctx.arc(0,0,Math.min(w,h)/2,0,Math.PI*2);ctx.fill();} else ctx.stroke();
        ctx.restore();
      }
      frame=requestAnimationFrame(draw);
    }
    frame=requestAnimationFrame(draw);
    return {set,dispose(){stopped=true;cancelAnimationFrame(frame);}};
  }
  root.GorkAvatar={mount,eye};
})(window);
