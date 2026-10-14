const path = require('node:path');
function tokenPlacement(avatar, area, desiredHeight=480) {
  const width=Math.min(276,area.width),height=Math.min(desiredHeight,area.height),gap=8;
  const cx=avatar.x+avatar.width/2,cy=avatar.y+avatar.height/2;
  const choices=[{x:avatar.x+avatar.width+gap,y:cy-height/2},
    {x:avatar.x-width-gap,y:cy-height/2},{x:cx-width/2,y:avatar.y-height-gap},
    {x:cx-width/2,y:avatar.y+avatar.height+gap}];
  const place=choices.find(p=>p.x>=area.x&&p.y>=area.y&&p.x+width<=area.x+area.width&&p.y+height<=area.y+area.height)||choices[0];
  return {bounds:{x:Math.round(Math.max(area.x,Math.min(place.x,area.x+area.width-width))),
    y:Math.round(Math.max(area.y,Math.min(place.y,area.y+area.height-height))),width,height}};
}

function createTokenWindow({BrowserWindow, screen, avatar, preferences, readUsage, readQuota,
  timers = {setInterval, clearInterval}}) {
  let win, ready=false, hovering=false, disposed=false, interval=null, epoch=0;
  const hoverSources=new Set();let height=240;
  let current={status:'loading',total_tokens:null}, quota={status:'loading',buckets:{}}, pending=null, quotaPending=null;
  function sync() {
    if (!win || win.isDestroyed() || !ready) return;
    if (!hovering || avatar.isDestroyed() || !avatar.isVisible() || avatar.isMinimized?.()) {win.hide();return;}
    const place=tokenPlacement(avatar.getBounds(),screen.getDisplayMatching(avatar.getBounds()).workArea,height);
    win.setBounds(place.bounds);win.setAlwaysOnTop(avatar.isAlwaysOnTop());
    win.webContents.send('gork:token-usage',{...current,quota});
    if(!win.isVisible())win.showInactive();
  }
  async function refresh() {
    void refreshQuota();
    const generation=epoch;
    if(!hovering||disposed)return;
    if(!pending)pending=Promise.resolve().then(readUsage).catch(()=>({status:'unavailable',total_tokens:null,stale:true}));
    const request=pending,value=await request;
    if(pending===request)pending=null;
    if(disposed||!hovering||generation!==epoch)return;
    current=value;sync();
  }
  async function refreshQuota() {
    const generation=epoch;
    if(!readQuota||!hovering||disposed)return;
    if(!quotaPending)quotaPending=Promise.resolve().then(readQuota).catch(()=>null);
    const request=quotaPending,value=await request;
    if(quotaPending===request)quotaPending=null;
    if(disposed||!hovering||generation!==epoch)return;
    quota=value||{...quota,status:'unavailable',stale:true};sync();
  }
  function setHover(value,source='avatar') {
    if(disposed)return;
    if(value)hoverSources.add(source);else hoverSources.delete(source);
    const active=hoverSources.size>0;
    if(hovering===active)return;
    hovering=active;epoch++;
    if(!hovering){if(interval!==null)timers.clearInterval(interval);interval=null;win?.webContents.send('gork:token-reset');sync();return;}
    // Never display yesterday's cached total before the new response arrives.
    current={status:'loading',total_tokens:null};
    quota={status:'loading',buckets:{}};
    if(!win){
      win=new BrowserWindow({width:276,height:240,frame:false,transparent:true,resizable:false,
        show:false,skipTaskbar:true,focusable:false,alwaysOnTop:avatar.isAlwaysOnTop(),webPreferences:preferences});
      win.setIgnoreMouseEvents(false);
      win.webContents.setWindowOpenHandler(()=>({action:'deny'}));
      win.webContents.on('will-navigate',event=>event.preventDefault());
      win.once('ready-to-show',()=>{ready=true;sync();});
      win.on('closed',()=>{win=null;ready=false;});
      win.loadFile(path.join(__dirname,'token-card.html'));
    }
    sync();void refresh();interval=timers.setInterval(refresh,20000);
  }
  const hide=()=>{hoverSources.clear();setHover(false);if(!avatar.isDestroyed())avatar.webContents?.send?.('gork:token-reset');};
  for(const event of ['move','resize'])avatar.on(event,sync);
  for(const event of ['hide','minimize'])avatar.on(event,hide);
  return {setHover,sync,hide,owns(sender){return Boolean(win&&!win.isDestroyed()&&sender===win.webContents);},
    setHeight(value){if(Number.isInteger(value)&&value>=180&&value<=900){height=value;sync();}},
    destroy(){if(disposed)return;hide();disposed=true;
    for(const event of ['move','resize'])avatar.removeListener(event,sync);
    for(const event of ['hide','minimize'])avatar.removeListener(event,hide);
    if(win&&!win.isDestroyed())win.destroy();win=null;ready=false;}};
}
module.exports={createTokenWindow,tokenPlacement};
