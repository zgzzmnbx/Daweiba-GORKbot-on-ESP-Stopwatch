const container=document.getElementById('indicators');
let gesture=null,sequence=0;
function dragError(){container.title='位置保存失败，已恢复上次位置，请重试。';}
container.addEventListener('pointerdown',event=>{
  if(event.button!==0||gesture||!event.target.closest('button')||!window.gorkDesktop?.indicatorDrag)return;
  event.preventDefault();container.setPointerCapture(event.pointerId);
  const current={id:++sequence,pointer:event.pointerId};gesture=current;
  current.start=window.gorkDesktop.indicatorDrag({phase:'start',id:current.id}).then(()=>true,()=>{dragError();return false;});
  document.body.dataset.dragging='true';
});
container.addEventListener('pointermove',event=>{
  const current=gesture;if(!current||current.pointer!==event.pointerId)return;
  current.start.then(ok=>{if(ok&&gesture===current)window.gorkDesktop.indicatorDrag({phase:'move',id:current.id}).catch(dragError);});
});
async function finish(event,cancel=false){
  const current=gesture;if(!current||current.pointer!==event.pointerId)return;
  gesture=null;document.body.dataset.dragging='false';
  if(container.hasPointerCapture(event.pointerId))container.releasePointerCapture(event.pointerId);
  try{if(!await current.start)return;const result=await window.gorkDesktop.indicatorDrag({phase:cancel?'cancel':'end',id:current.id});if(!cancel&&!result.dragged&&!result.cancelled)await window.gorkDesktop.openConsole();}
  catch{dragError();}
}
container.addEventListener('pointerup',event=>void finish(event));
container.addEventListener('pointercancel',event=>void finish(event,true));
container.addEventListener('lostpointercapture',event=>{if(gesture)void finish(event,true);});
window.gorkDesktop?.onIndicators(rows=>{
  const keys=rows.map(row=>row.key).join(',');
  if(container.dataset.keys!==keys){container.replaceChildren();let line;rows.forEach((row,index)=>{if(index%3===0){line=document.createElement('div');line.className='bubble-row';container.append(line);}const button=document.createElement('button');button.type='button';button.dataset.key=row.key;button.addEventListener('click',event=>{if(event.detail===0||!window.gorkDesktop?.indicatorDrag)window.gorkDesktop.openConsole();});line.append(button);});container.dataset.keys=keys;}
  const buttons=container.querySelectorAll('button');
  rows.forEach((row,index)=>{const button=buttons[index];button.textContent=row.text;button.title=`${row.title} · 按住拖动小人，单击打开控制台`;button.setAttribute('aria-label',`${row.title}：${row.text}`);});
});
