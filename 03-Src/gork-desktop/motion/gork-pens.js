/* Original flat pen geometry and shared stroke path, AGPL-3.0-only.
 * Visual studies: Lucide feather/pen-tool/pencil and Phosphor paint-brush.
 * No upstream icon paths are copied. Each pen's nib is anchored at (0,0).
 */
(function(root){'use strict';
const styles=['quill','nib','pencil','brush'];
const labels={quill:'羽毛笔',nib:'钢笔尖',pencil:'极简铅笔',brush:'毛笔'};
const clamp=v=>Math.max(0,Math.min(1,v));
function inkPoint(line,x){return{x,y:34+line*30+Math.sin((x+90)*.12)*3.5+Math.sin((x+90)*.34)*1.8};}
function trace(progress){const p=clamp(progress),cursor=Math.min(2.999999,p*3),line=Math.floor(cursor),phase=cursor-line,drawn=Math.min(1,phase/.83),point=inkPoint(line,-90+170*drawn);let tip={...point},lift=0;
 if(phase>.83){const a=(phase-.83)/.17,next=inkPoint((line+1)%3,-90);tip={x:point.x+(next.x-point.x)*a,y:point.y+(next.y-point.y)*a};lift=Math.sin(a*Math.PI)*23;tip.y-=lift;}
 return{line,drawn,tip,lift,point};}
function drawPen(ctx,style,x,y,rotation,size,alpha){
 ctx.save();ctx.translate(x,y);ctx.rotate(rotation);ctx.scale(size,size);ctx.globalAlpha=alpha;ctx.fillStyle='#fff';ctx.strokeStyle='#fff';ctx.lineWidth=3;ctx.lineCap='round';ctx.lineJoin='round';
 const kind=typeof style==='number'?styles[style]:style;
 if(kind==='quill'){
  // A broad, tapered vane and separated barbs, ending in a fine quill tip.
  ctx.beginPath();ctx.moveTo(0,0);ctx.quadraticCurveTo(-1,-24,4,-44);ctx.quadraticCurveTo(11,-77,35,-102);ctx.bezierCurveTo(43,-76,33,-40,6,-24);ctx.quadraticCurveTo(2,-10,0,0);ctx.fill();
  ctx.strokeStyle='#000';ctx.lineWidth=2.6;ctx.beginPath();ctx.moveTo(5,-26);ctx.quadraticCurveTo(17,-61,32,-91);ctx.moveTo(13,-46);ctx.lineTo(30,-53);ctx.moveTo(19,-61);ctx.lineTo(34,-69);ctx.moveTo(8,-31);ctx.lineTo(21,-35);ctx.stroke();
 }else if(kind==='nib'){
  ctx.beginPath();ctx.moveTo(0,0);ctx.lineTo(-20,-43);ctx.lineTo(-12,-79);ctx.lineTo(12,-79);ctx.lineTo(20,-43);ctx.closePath();ctx.fill();
  ctx.strokeStyle='#000';ctx.lineWidth=3;ctx.beginPath();ctx.moveTo(0,-2);ctx.lineTo(0,-38);ctx.stroke();ctx.fillStyle='#000';ctx.beginPath();ctx.arc(0,-43,5,0,Math.PI*2);ctx.fill();ctx.fillRect(-16,-66,32,3);
 }else if(kind==='pencil'){
  ctx.beginPath();ctx.moveTo(0,0);ctx.lineTo(-7,-17);ctx.lineTo(-7,-88);ctx.quadraticCurveTo(-7,-93,0,-93);ctx.quadraticCurveTo(7,-93,7,-88);ctx.lineTo(7,-17);ctx.closePath();ctx.fill();ctx.strokeStyle='#000';ctx.lineWidth=2;ctx.beginPath();ctx.moveTo(-7,-19);ctx.lineTo(7,-19);ctx.moveTo(-7,-78);ctx.lineTo(7,-78);ctx.stroke();
 }else if(kind==='brush'){
  ctx.beginPath();ctx.moveTo(0,0);ctx.bezierCurveTo(-20,-14,-17,-32,-8,-44);ctx.lineTo(8,-44);ctx.bezierCurveTo(17,-30,14,-10,0,0);ctx.fill();ctx.beginPath();ctx.moveTo(-5,-48);ctx.lineTo(-3,-94);ctx.quadraticCurveTo(0,-103,3,-94);ctx.lineTo(5,-48);ctx.closePath();ctx.fill();ctx.strokeStyle='#000';ctx.lineWidth=2;ctx.beginPath();ctx.moveTo(0,-3);ctx.quadraticCurveTo(8,-17,5,-34);ctx.stroke();
 }
 ctx.restore();
}
function drawInk(ctx,progress,width,alpha){const state=trace(progress);ctx.save();ctx.globalAlpha=alpha;ctx.strokeStyle='#fff';ctx.lineWidth=width;ctx.lineCap='round';ctx.lineJoin='round';
 for(let line=0;line<=state.line;line++){const fraction=line<state.line?1:state.drawn;if(fraction<=0)continue;const end=-90+170*fraction;ctx.beginPath();const start=inkPoint(line,-90);ctx.moveTo(start.x,start.y);for(let x=-88;x<end;x+=2){const p=inkPoint(line,x);ctx.lineTo(p.x,p.y);}const p=inkPoint(line,end);ctx.lineTo(p.x,p.y);ctx.stroke();}ctx.restore();return state;}
const api={styles,labels,trace,inkPoint,drawPen,drawInk};if(typeof module!=='undefined')module.exports=api;else root.GorkPens=api;
})(typeof window!=='undefined'?window:globalThis);
