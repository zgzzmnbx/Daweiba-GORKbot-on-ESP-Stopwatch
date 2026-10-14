/* Gork motion preview · original scene choreography, AGPL-3.0-only. */
(function(root){
  'use strict';
  const Config=typeof module!=='undefined'?require('./gork-config.js'):root.GorkConfig;
  const Pens=typeof module!=='undefined'?require('./gork-pens.js'):root.GorkPens;
  const clamp=v=>Math.max(0,Math.min(1,v));
  const smooth=v=>{v=clamp(v);return v*v*(3-2*v);};
  const mix=(a,b,t)=>a+(b-a)*t;
  const defaults={headX:0,headY:0,headZ:0,widthLeft:20,widthRight:20,heightLeft:50,heightRight:50,spacing:35,positionXLeft:0,positionXRight:0,positionYLeft:-7,positionYRight:-7,leftAngle:0,rightAngle:0,perspective:1,eyeAlpha:1,spinner:0,paper:0,hand:0,question:0,pen:0,paperY:0,handX:0,handY:0,penX:0,penY:0,penRotation:0,ink:0,bob:0,questionScale:1,questionY:0};
  const durations={idle:650,loading:750,writing:1250,question:800};
  function target(scene,age,reduced=false,config=Config.defaults()){
    const c=config.scenes[scene],e=c.eyes;
    const p={...defaults,...e,positionXLeft:e.x,positionXRight:e.x,positionYLeft:e.y,positionYRight:e.y},t=age/1000,loop=reduced?0:t;
    delete p.x;delete p.y;
    const load=config.scenes.loading.loading,write=config.scenes.writing.writing,q=config.scenes.question.question;
    Object.assign(p,{spinX:load.x,spinY:load.y,spinScale:load.scale,writeX:write.x,writeY:write.y,writeScale:write.scale,penSize:write.penScale,strokeWidth:write.strokeWidth,penStyle:Pens.styles.indexOf(write.penStyle),qX:q.x,qY:q.y,qSize:q.scale,spinAngle:loop*3.3});
    if(scene==='idle'){
      const look=reduced?0:Math.sin(loop*.52)*3;
      p.headY=e.headY+look;p.headZ=e.headZ+look*.3;p.bob=reduced?0:Math.sin(loop*1.5)*2;
      const blink=age%5600; if(!reduced&&blink>4600&&blink<4850){let b=Math.abs((blink-4600)/125-1);p.heightLeft=5+(e.heightLeft-5)*b;p.heightRight=5+(e.heightRight-5)*b;}
    } else if(scene==='loading'){
      p.eyeAlpha=0;p.widthLeft=p.widthRight=5;p.heightLeft=p.heightRight=5;p.spacing=3;p.spinner=1;
    } else if(scene==='writing'){
      p.paper=1;p.pen=1;
      const active=Math.max(0,loop-c.motion.enterMs*c.motion.speed/1000);
      p.ink=(active%7.2)/7.2;const nib=Pens.trace(p.ink);
      p.penX=nib.tip.x;p.penY=nib.tip.y;p.penRotation=.35+Math.sin(active*2)*.025;
      p.bob=0;
    } else if(scene==='question'){
      p.leftAngle=-5;p.rightAngle=-12;p.question=1;
      p.questionY=reduced?0:Math.sin(loop*2.7)*q.bob;p.headZ+=reduced?0:Math.sin(loop*1.6)*1.8;
    }
    return p;
  }
  class SceneController{
    constructor({now=0,reducedMotion=false,config=Config.defaults()}={}){this.config=Config.validate(config);this.scene='idle';this.started=now;this.transitionStart=now;this.duration=0;this.from=target('idle',0,true,this.config);this.displayed={...this.from};this.reducedMotion=reducedMotion;this.phase='loop';this.reason='';this.revision=0;}
    set(scene,now,reason='switch'){
      if(!Object.hasOwn(durations,scene))throw new Error('Unknown scene');
      this.from=this.sample(now);const outgoing=this.config.scenes[this.scene].motion;this.scene=scene;this.started=now;this.transitionStart=now;this.reason=reason;
      this.duration=this.reducedMotion?150:scene==='idle'?(reason==='cancel'?Math.min(400,outgoing.exitMs):outgoing.exitMs):this.config.scenes[scene].motion.enterMs;
      this.revision++;return this.snapshot(now);
    }
    complete(now){return this.scene==='idle'?this.snapshot(now):this.set('idle',now,'complete');}
    cancel(now){return this.scene==='idle'?this.snapshot(now):this.set('idle',now,'cancel');}
    sample(now){
      const age=Math.max(0,now-this.started),p=target(this.scene,age*this.config.scenes[this.scene].motion.speed,this.reducedMotion,this.config),raw=this.duration?clamp((now-this.transitionStart)/this.duration):1,progress=smooth(raw);
      const out={};for(const k of Object.keys(p))out[k]=mix(this.from[k],p[k],progress);
      if(this.scene==='loading'&&raw<1){
        const eyes=this.config.scenes.loading.eyes,collapse=smooth((raw-.2)/.7),opening=smooth(raw/.2);
        for(const k of ['widthLeft','widthRight','heightLeft','heightRight'])out[k]=mix(mix(this.from[k],eyes[k],opening),5,collapse);
        out.spacing=mix(mix(this.from.spacing,eyes.spacing,opening),3,collapse);
        out.eyeAlpha=1-collapse;out.spinner=collapse;
      }
      // All writing uses one shared ink path. Enter with raised nib; exit lifts it.
      out.penStyle=p.penStyle;
      if(this.scene==='writing'&&raw<1){
        const enter=smooth(raw),nib=Pens.trace(0);
        out.paper=mix(this.from.paper,1,enter);out.pen=mix(this.from.pen,1,enter);
        out.penX=mix(this.from.pen>.01?this.from.penX:nib.tip.x+25,nib.tip.x,enter);
        out.penY=mix(this.from.pen>.01?this.from.penY:nib.tip.y-30,nib.tip.y,enter);
        out.penRotation=mix(this.from.pen>.01?this.from.penRotation:.55,p.penRotation,enter);out.ink=0;
      }
      if(this.scene!=='writing'&&this.from.pen>.001&&raw<1){
        out.ink=this.from.ink;out.penX=this.from.penX;out.penY=this.from.penY-smooth(raw)*30;
        out.penRotation=this.from.penRotation+smooth(raw)*.18;
      }
      if(this.scene==='question'&&raw<1&&!this.reducedMotion){out.questionScale=1+Math.sin(raw*Math.PI)*.2;}
      this.displayed=out;this.phase=raw<1?(this.scene==='idle'?'exit':'enter'):'loop';return out;
    }
    setConfig(config){this.config=Config.validate(config);}
    snapshot(now){this.sample(now);return {scene:this.scene,phase:this.phase,reason:this.reason,revision:this.revision};}
  }
  if(typeof module!=='undefined')module.exports={SceneController,target,defaults};else root.GorkScenes={SceneController,target,defaults};
})(typeof window!=='undefined'?window:globalThis);
