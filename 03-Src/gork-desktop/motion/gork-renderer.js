/* Reusable Gork scene drawing. AGPL-3.0-only. No editor/DOM dependencies beyond canvas. */
(function(root){'use strict';
function safeCenter(x,y,r){const distance=Math.hypot(x,y),limit=Math.max(0,216-r),factor=distance>limit?limit/distance:1;return{x:x*factor,y:y*factor};}
function create(canvas,options={}){const ctx=canvas.getContext('2d');
const fillPath=(path)=>{if(path)ctx.fill(new Path2D(path));};
function roundRect(x,y,w,h,r){ctx.beginPath();ctx.roundRect(x,y,w,h,r);}
function avatar(p){
 const preset=GorkPresets.find(x=>x.id==='gork');
 const geometry=AvatarProceduralEngine.renderAvatar(AvatarProceduralEngine.poseFromExpression(p),preset.body.primary,1,{bodyNodes:preset.body.nodes,includeWire:false});
 ctx.save();ctx.translate(450,300+p.bob);ctx.scale(490/260,490/260);
 ctx.fillStyle='#000';geometry.backPaths.forEach(fillPath);fillPath(geometry.headPath);
 ctx.save();ctx.clip(new Path2D(geometry.headPath));ctx.fillStyle='#fff';ctx.globalAlpha=p.eyeAlpha;
 if(geometry.leftVisible)fillPath(geometry.leftPath);if(geometry.rightVisible)fillPath(geometry.rightPath);
 ctx.restore();ctx.fillStyle='#000';geometry.frontPaths.forEach(fillPath);ctx.restore();
 return geometry;
}
function spinner(p,t){
 if(p.spinner<.002)return;
 const center=safeCenter(p.spinX,p.spinY,38*p.spinScale);ctx.save();ctx.translate(450+center.x,300+p.bob+center.y);ctx.scale((.4+.6*p.spinner)*p.spinScale,(.4+.6*p.spinner)*p.spinScale);ctx.globalAlpha=p.spinner;
 const rotation=p.reduced?-.5:p.spinAngle;
 ctx.rotate(rotation);ctx.lineWidth=9;ctx.lineCap='round';
 ctx.strokeStyle='#fff';ctx.beginPath();ctx.arc(0,0,32,-Math.PI*.6,Math.PI*.82);ctx.stroke();
 ctx.strokeStyle='#fff';ctx.beginPath();ctx.arc(0,0,32,Math.PI*.98,Math.PI*1.12);ctx.stroke();ctx.restore();
}
function writing(p){
 if(p.paper<.001&&p.pen<.001)return;
 // No paper slab and no hand. One flat pen above growing white strokes.
 const scale=.78*p.writeScale,center=safeCenter(p.writeX,p.writeY,190*scale);
 ctx.save();ctx.translate(450+center.x,300+p.bob+center.y);ctx.scale(scale,scale);ctx.translate(0,-35);
 GorkPens.drawInk(ctx,p.ink,p.strokeWidth,p.paper);
 GorkPens.drawPen(ctx,p.penStyle,p.penX,p.penY,p.penRotation,p.penSize,p.pen);
 ctx.restore();
}
function question(p){
 if(p.question<.002)return;
 const size=p.questionScale*p.question*p.qSize,center=safeCenter(p.qX,p.qY+p.questionY,63*Math.max(1,p.questionScale)*p.qSize);
 ctx.save();ctx.translate(450+center.x,300+p.bob+center.y);ctx.rotate(-.10);ctx.scale(size,size);ctx.globalAlpha=p.question;
 // Rounded white geometry matches the original eye capsules without font dependence.
 ctx.strokeStyle='#fff';ctx.lineWidth=13;ctx.lineCap='round';ctx.lineJoin='round';
 ctx.beginPath();ctx.moveTo(-23,-21);ctx.bezierCurveTo(-21,-47,23,-48,23,-21);ctx.bezierCurveTo(23,-5,0,-4,0,14);ctx.stroke();
 ctx.fillStyle='#fff';ctx.beginPath();ctx.arc(0,37,7,0,Math.PI*2);ctx.fill();ctx.restore();
}

function draw(p){
 const width=canvas.width,height=canvas.height,scale=options.fit==='avatar'?Math.min(width,height)*.92/452:Math.min(width/900,height/680);
 ctx.setTransform(1,0,0,1,0,0);ctx.clearRect(0,0,width,height);
 ctx.setTransform(scale,0,0,scale,(width-900*scale)/2,options.fit==='avatar'?height/2-300*scale:(height-680*scale)/2);
 const geometry=avatar(p);ctx.save();ctx.translate(450,300+p.bob);ctx.scale(490/260,490/260);ctx.clip(new Path2D(geometry.headPath));
 ctx.scale(260/490,260/490);ctx.translate(-450,-300-p.bob);
 spinner(p);writing(p);question(p);ctx.restore();
}
return {draw};}
root.GorkRenderer={create,safeCenter};
})(typeof window!=='undefined'?window:globalThis);
