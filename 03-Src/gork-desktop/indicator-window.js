const path=require('node:path');
const model=require('./indicator-model');
function placement(bounds,area,count){
  const columns=Math.min(3,count),width=Math.min(area.width,columns*72+Math.max(0,columns-1)*4+4),height=Math.ceil(count/3)*26+4;
  const face=Math.min(bounds.width*.88,bounds.height*.9);
  const bottom=bounds.y+bounds.height/2+face/2+4;
  const cx=bounds.x+bounds.width/2,cy=bounds.y+bounds.height/2;
  const head={x:cx-face/2,y:cy-face/2,width:face,height:face};
  const choices=[{x:cx-width/2,y:bottom},{x:cx-width/2,y:head.y-height-4},{x:bounds.x+bounds.width+4,y:cy-height/2},{x:bounds.x-width-4,y:cy-height/2}];
  const candidates=choices.map(p=>({x:Math.round(Math.max(area.x,Math.min(p.x,area.x+area.width-width))),y:Math.round(Math.max(area.y,Math.min(p.y,area.y+area.height-height))),width,height}));
  const overlap=p=>Math.max(0,Math.min(p.x+width,head.x+head.width+3)-Math.max(p.x,head.x-3))*Math.max(0,Math.min(p.y+height,head.y+head.height+3)-Math.max(p.y,head.y-3));
  return candidates.find(p=>overlap(p)===0)||candidates.sort((a,b)=>overlap(a)-overlap(b))[0];
}
function createIndicatorWindow({BrowserWindow,screen,avatar,preferences,getSettings,readUsage,readQuota,onDragEnd=()=>{},onLayout=()=>{},timers={setInterval,clearInterval}}){
  let win,ready=false,disposed=false,timer=null,epoch=0,active=false;
  let data={},pending={},drag=null,sizeKey='';
  const visible=()=>!disposed&&!avatar.isDestroyed()&&avatar.isVisible()&&!avatar.isMinimized?.();
  const wanted=()=>visible()&&getSettings().mode==='bubbles'&&getSettings().items.length>0;
  function paint(){
    if(!win||win.isDestroyed()||!ready)return;
    if(!wanted()){drag=null;win.hide();onLayout();return;}
    const rows=model.rows(getSettings(),data);
    if(!rows.length){drag=null;win.hide();onLayout();return;}
    {
      const a=avatar.getBounds();
      let bounds=placement(a,screen.getDisplayMatching(a).workArea,rows.length);
      const key=`${bounds.width}:${bounds.height}`;
      if(key!==sizeKey){win.setBounds(bounds);sizeKey=key;}
      const actual=win.getBounds();bounds.width=actual.width;bounds.height=actual.height;
      move(bounds);
    }
    win.setAlwaysOnTop(avatar.isAlwaysOnTop());win.webContents.send('gork:indicators',rows);
    if(!win.isVisible())win.showInactive();
    onLayout();
  }
  function move(bounds){
    const current=win.getBounds();if(current.x===bounds.x&&current.y===bounds.y)return;
    // Reuse requested DIP size, not native rounded size (which can grow on repeated Windows moves).
    const [width,height]=sizeKey.split(':').map(Number);
    win.setBounds({...bounds,width,height});
  }
  function clamp(bounds){const area=screen.getDisplayMatching(bounds).workArea;return {...bounds,x:Math.round(Math.max(area.x,Math.min(bounds.x,area.x+area.width-bounds.width))),y:Math.round(Math.max(area.y,Math.min(bounds.y,area.y+area.height-bounds.height)))};}
  function moveAvatar(bounds){
    // Transparent Windows bounds can round outwards under display scaling.
    // Correct the request, never feed rounded native dimensions back into the next move.
    for(let attempt=0;attempt<3;attempt++){
      avatar.setBounds({...bounds,...drag.size});
      const actual=avatar.getBounds(),dw=actual.width-drag.bounds.width,dh=actual.height-drag.bounds.height;
      if(Math.abs(dw)<=1&&Math.abs(dh)<=1)break;
      if(Math.abs(dw)>1)drag.size.width-=dw;
      if(Math.abs(dh)>1)drag.size.height-=dh;
    }
  }
  function dragRequest({phase,id}={}){
    if(!Number.isSafeInteger(id)||!['start','move','end','cancel'].includes(phase))throw Error('Invalid drag request');
    if(!wanted()||!win||!ready)throw Error('Indicators unavailable');
    if(phase==='start'){
      const cursor=screen.getCursorScreenPoint(),bounds=win.getBounds();
      if(drag||cursor.x<bounds.x||cursor.y<bounds.y||cursor.x>bounds.x+bounds.width||cursor.y>bounds.y+bounds.height)throw Error('Invalid drag origin');
      if(!win.isVisible())throw Error('Indicators unavailable');
      const original=avatar.getBounds();
      drag={id,cursor:{...cursor},bounds:{...original},size:{width:original.width,height:original.height},moved:false};return {dragged:false};
    }
    if(!drag||drag.id!==id)return {dragged:false,cancelled:true};
    if(phase==='cancel'){moveAvatar(drag.bounds);drag=null;paint();return {dragged:false,cancelled:true};}
    const cursor=screen.getCursorScreenPoint(),dx=cursor.x-drag.cursor.x,dy=cursor.y-drag.cursor.y;
    if(Math.hypot(dx,dy)>=4)drag.moved=true;
    if(drag.moved){
      // Move the avatar with a fixed request size; its normal layout keeps every bubble nearby.
      const target=clamp({...drag.bounds,x:drag.bounds.x+dx,y:drag.bounds.y+dy});
      const current=avatar.getBounds();
      if(current.x!==target.x||current.y!==target.y)moveAvatar(target);
      paint();
    }
    const moved=drag.moved;
    if(phase==='end'){
      const original=drag.bounds;
      if(moved){try{onDragEnd();}catch(error){moveAvatar(original);drag=null;paint();throw error;}}
      drag=null;
      paint();
    }
    return {dragged:moved};
  }
  async function read(key,fn){
    if(!wanted()||!getSettings().items.includes(key))return;
    const generation=epoch;
    if(!pending[key])pending[key]=Promise.resolve().then(fn).catch(()=>({status:'unavailable'}));
    const request=pending[key],value=await request;
    if(pending[key]===request)delete pending[key];
    if(disposed||generation!==epoch||!wanted()||!getSettings().items.includes(key))return;
    data[key]=value;paint();
  }
  function refresh(){void read('tokens',readUsage);void read('quota',readQuota);}
  function sync(){
    const next=wanted();
    if(next!==active){active=next;epoch++;if(timer!==null)timers.clearInterval(timer);timer=null;
      if(next){data={};refresh();timer=timers.setInterval(refresh,20000);}}
    if(next&&!win){
      win=new BrowserWindow({width:228,height:56,frame:false,transparent:true,resizable:false,show:false,skipTaskbar:true,focusable:false,alwaysOnTop:avatar.isAlwaysOnTop(),webPreferences:preferences});
      win.webContents.setWindowOpenHandler(()=>({action:'deny'}));win.webContents.on('will-navigate',e=>e.preventDefault());
      win.once('ready-to-show',()=>{ready=true;paint();});win.on('closed',()=>{win=null;ready=false;sizeKey='';});
      win.loadFile(path.join(__dirname,'indicators.html'));
    }
    paint();
  }
  const events=['show','restore','hide','minimize','move','resize'];for(const event of events)avatar.on(event,sync);
  avatar.webContents.on('did-finish-load',sync);
  return {sync,dragRequest,isDragging:()=>Boolean(drag),traffic(value){data.traffic=value;paint();},changed(){drag=null;epoch++;data.tokens={};data.quota={};sync();refresh();},
    owns(sender){return Boolean(win&&!win.isDestroyed()&&win.webContents===sender);},
    visibleBounds:()=>win&&!win.isDestroyed()&&win.isVisible()?win.getBounds():null,
    destroy(){disposed=true;drag=null;epoch++;if(timer!==null)timers.clearInterval(timer);for(const event of events)avatar.removeListener(event,sync);avatar.webContents.removeListener('did-finish-load',sync);if(win&&!win.isDestroyed())win.destroy();}};
}
module.exports={createIndicatorWindow,placement};
