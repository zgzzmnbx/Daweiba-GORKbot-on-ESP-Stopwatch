// Native window coordinates and production renderers; isolated data, no live service.
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict'),{EventEmitter}=require('node:events');
const root=path.resolve(__dirname,'..'),desktop=path.join(root,'03-Src/gork-desktop');
const {app,BrowserWindow,ipcMain}=require('node:module').createRequire(path.join(desktop,'package.json'))('electron');
const {createBubbleWindow}=require(path.join(desktop,'bubble-window'));
const {createIndicatorWindow}=require(path.join(desktop,'indicator-window')),{createTokenWindow}=require(path.join(desktop,'token-window'));
const out=path.join(root,'04-output/v0.21.5/tests');fs.mkdirSync(out,{recursive:true});
app.setPath('userData',path.join(root,'Codex-Temp/indicator-hover-'+Date.now()));
const delay=ms=>new Promise(r=>setTimeout(r,ms)),windows=[],errors=[];let card,strip,speech,cursor,opens=0,saves=0;
function TestWindow(options){
 const win=new BrowserWindow({...options,show:false,webPreferences:{...options.webPreferences,offscreen:true,backgroundThrottling:false}});
 let visible=false;win.isVisible=()=>visible;win.showInactive=()=>{visible=true;};win.hide=()=>{visible=false;};
 win.webContents.on('console-message',d=>{if(d.level==='error')errors.push(d.message);});windows.push(win);return win;
}
ipcMain.handle('gork:token-height',(_e,height)=>{card.setHeight(height);return true;});
ipcMain.handle('gork:token-hover',(_e,value)=>{card.setHover(value,'card');return true;});
ipcMain.handle('gork:hide-token-card',()=>{card.hide();return true;});
ipcMain.handle('gork:open-console',()=>{opens++;return true;});
ipcMain.handle('gork:indicator-drag',(event,value)=>{assert(strip.owns(event.sender));return strip.dragRequest(value);});
async function until(check){for(let i=0;i<100;i++){if(await check())return;await delay(100);}throw Error('Window readiness timed out');}
async function run(){
 await app.whenReady();
 const avatar=new BrowserWindow({x:900,y:400,width:182,height:213,frame:false,transparent:true,show:false,webPreferences:{offscreen:true,backgroundThrottling:false}});
 avatar.isVisible=()=>true;const avatarBefore=avatar.getBounds();
 await avatar.loadFile(path.join(desktop,'avatar.html'));
 assert.equal(await avatar.webContents.executeJavaScript("document.querySelectorAll('.quota-ring').length"),0,'quota ring removed');
 const shared={BrowserWindow:TestWindow,screen:{getDisplayMatching:()=>({workArea:{x:0,y:0,width:1920,height:1080}}),getCursorScreenPoint:()=>({...cursor})},avatar,
 preferences:{preload:path.join(desktop,'preload.js'),contextIsolation:true,sandbox:true},
 readUsage:async()=>({status:'available',total_tokens:76500000,date:'2026-10-15'}),
 readQuota:async()=>({status:'available',buckets:{x:{windows:[{name:'7天',remaining_percent:79}]}}})};
 strip=createIndicatorWindow({...shared,getSettings:()=>({mode:'bubbles',items:['quota','tokens','proxy']}),onDragEnd:()=>{saves++;},onLayout:()=>{speech?.sync();card?.sync();}});
 speech=createBubbleWindow({...shared,getPosition:()=> 'below',getIndicatorBounds:()=>strip.visibleBounds()});
 card=createTokenWindow({...shared,getIndicatorBounds:()=>strip.visibleBounds()});
 avatar.emit('show');await until(()=>strip.visibleBounds());strip.traffic({enabled:true});await delay(100);const before=windows[0].getBounds();assert(strip.visibleBounds());
 const checks=[];
 for(let i=0;i<3;i++){
  card.setHover(true);await until(()=>card.visibleBounds());await delay(150);
  await windows[1].webContents.executeJavaScript(`document.getElementById('token-details').open=${i===1}`);await delay(200);
  strip.traffic({enabled:true});await delay(50);
  const after=windows[0].getBounds(),detail=windows[1].getBounds();assert.deepEqual(after,before);
  assert(detail.x+detail.width<=after.x||detail.x>=after.x+after.width||detail.y+detail.height<=after.y||detail.y>=after.y+after.height);
  checks.push({hover:i,after,detail});card.setHover(false);assert.deepEqual(windows[0].getBounds(),before);
 }
 // A below-positioned speech bubble must move around the numeric strip.
 speech.update({bubble:'Codex 额度下降2个百分点',revision:1});await until(()=>speech.visibleBounds());await delay(100);
 assert.deepEqual(windows[0].getBounds(),before);
 const spoken=speech.visibleBounds();assert(spoken.y>=before.y+before.height||spoken.x+spoken.width<=before.x||spoken.x>=before.x+before.width);
 const target=await windows[0].webContents.executeJavaScript("(()=>{const b=document.querySelector('button').getBoundingClientRect();return {x:Math.round(b.x+b.width/2),y:Math.round(b.y+b.height/2)}})()");
 cursor={x:before.x+target.x,y:before.y+target.y};
 windows[0].webContents.sendInputEvent({type:'mouseDown',button:'left',clickCount:1,...target});await delay(100);
 const origin={...cursor};
 for(let step=1;step<=10;step++){
  cursor={x:origin.x+step*10,y:origin.y-Math.round(step*6.5)};
  windows[0].webContents.sendInputEvent({type:'mouseMove',x:target.x+step*10,y:target.y-Math.round(step*6.5)});await delay(60);
  const size=windows[0].getBounds();assert(Math.abs(size.width-before.width)<=1,'native width rounding must remain bounded');assert(Math.abs(size.height-before.height)<=1,'native height rounding must remain bounded');
 }
 windows[0].webContents.sendInputEvent({type:'mouseUp',button:'left',clickCount:1,...target});await delay(150);
 assert.equal(saves,1,'drag persisted once');assert.equal(opens,0,'drag must not open console');
 const avatarAfter=avatar.getBounds();assert(Math.abs(avatarAfter.width-avatarBefore.width)<=1&&Math.abs(avatarAfter.height-avatarBefore.height)<=1,'avatar dimensions do not grow');assert(Math.abs(avatarAfter.x-avatarBefore.x-100)<=1&&Math.abs(avatarAfter.y-avatarBefore.y+65)<=1,'drag moves real avatar');
 const dragged=windows[0].getBounds();assert(Math.abs(dragged.x-before.x-100)<=1&&Math.abs(dragged.y-before.y+65)<=1,JSON.stringify({before,dragged,cursor}));
 strip.traffic({enabled:true});speech.update({bubble:'第二次播报',revision:2});await delay(100);assert.deepEqual(windows[0].getBounds(),dragged);
 cursor={x:dragged.x+target.x,y:dragged.y+target.y};
 windows[0].webContents.sendInputEvent({type:'mouseDown',button:'left',clickCount:1,...target});await delay(50);
 windows[0].webContents.sendInputEvent({type:'mouseUp',button:'left',clickCount:1,...target});await delay(150);assert.equal(opens,1,'click still opens console');
 strip.traffic({enabled:false});await delay(100);assert.deepEqual(await windows[0].webContents.executeJavaScript("[...document.querySelectorAll('button')].map(b=>b.dataset.key)"),['quota','tokens']);
 strip.traffic({enabled:true});await delay(100);assert.deepEqual(await windows[0].webContents.executeJavaScript("[...document.querySelectorAll('button')].map(b=>b.dataset.key)"),['quota','tokens','proxy']);
 assert.equal(errors.length,0,errors.join('\n'));
 fs.writeFileSync(path.join(out,'result.json'),JSON.stringify({result:'PASS',before,checks,spoken,dragged,avatarBefore,avatarAfter,saves,opens,errors,acceptance:'native Electron hover/speech keep strip fixed; ten pointer moves preserve native size; drag moves avatar and saves once without console click; normal click opens console; traffic toggle filters pills; no quota ring'},null,2));
 if(fs.existsSync(path.join(out,'failure.log')))fs.unlinkSync(path.join(out,'failure.log'));card.destroy();speech.destroy();strip.destroy();avatar.destroy();app.quit();
}
run().catch(e=>{fs.writeFileSync(path.join(out,'failure.log'),e.stack+'\n'+JSON.stringify(errors));app.exit(1);});
