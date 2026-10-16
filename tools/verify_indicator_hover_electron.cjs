// Native window coordinates and production renderers; isolated data, no live service.
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict'),{EventEmitter}=require('node:events');
const root=path.resolve(__dirname,'..'),desktop=path.join(root,'03-Src/gork-desktop');
const {app,BrowserWindow,ipcMain}=require('node:module').createRequire(path.join(desktop,'package.json'))('electron');
const {createIndicatorWindow}=require(path.join(desktop,'indicator-window')),{createTokenWindow}=require(path.join(desktop,'token-window'));
const out=path.join(root,'04-output/v0.21.3/tests');fs.mkdirSync(out,{recursive:true});
app.setPath('userData',path.join(root,'Codex-Temp/indicator-hover-'+Date.now()));
const delay=ms=>new Promise(r=>setTimeout(r,ms)),windows=[],errors=[];let card,strip;
function TestWindow(options){
 const win=new BrowserWindow({...options,show:false,webPreferences:{...options.webPreferences,offscreen:true,backgroundThrottling:false}});
 let visible=false;win.isVisible=()=>visible;win.showInactive=()=>{visible=true;};win.hide=()=>{visible=false;};
 win.webContents.on('console-message',d=>{if(d.level==='error')errors.push(d.message);});windows.push(win);return win;
}
ipcMain.handle('gork:token-height',(_e,height)=>{card.setHeight(height);return true;});
ipcMain.handle('gork:token-hover',(_e,value)=>{card.setHover(value,'card');return true;});
ipcMain.handle('gork:hide-token-card',()=>{card.hide();return true;});
ipcMain.handle('gork:open-console',()=>true);
async function run(){
 await app.whenReady();
 const avatar=new EventEmitter();avatar.webContents=new EventEmitter();avatar.webContents.send=()=>{};
 avatar.isDestroyed=()=>false;avatar.isVisible=()=>true;avatar.isMinimized=()=>false;avatar.isAlwaysOnTop=()=>true;
 avatar.getBounds=()=>({x:1700,y:15,width:144,height:168});
 const shared={BrowserWindow:TestWindow,screen:{getDisplayMatching:()=>({workArea:{x:0,y:0,width:1920,height:1080}})},avatar,
 preferences:{preload:path.join(desktop,'preload.js'),contextIsolation:true,sandbox:true},
 readUsage:async()=>({status:'available',total_tokens:76500000,date:'2026-10-15'}),
 readQuota:async()=>({status:'available',buckets:{x:{windows:[{name:'7天',remaining_percent:79}]}}})};
 strip=createIndicatorWindow({...shared,getSettings:()=>({mode:'bubbles',items:['quota','tokens','proxy']}),onLayout:()=>card?.sync()});
 card=createTokenWindow({...shared,getIndicatorBounds:()=>strip.visibleBounds()});
 avatar.emit('show');await delay(350);const before=windows[0].getBounds();assert(strip.visibleBounds());
 const checks=[];
 for(let i=0;i<3;i++){
  card.setHover(true);await delay(350);
  await windows[1].webContents.executeJavaScript(`document.getElementById('token-details').open=${i===1}`);await delay(200);
  strip.traffic({enabled:false});await delay(50);
  const after=windows[0].getBounds(),detail=windows[1].getBounds();assert.deepEqual(after,before);
  assert(detail.x+detail.width<=after.x||detail.x>=after.x+after.width||detail.y+detail.height<=after.y||detail.y>=after.y+after.height);
  checks.push({hover:i,after,detail});card.setHover(false);assert.deepEqual(windows[0].getBounds(),before);
 }
 assert.equal(errors.length,0,errors.join('\n'));
 fs.writeFileSync(path.join(out,'result.json'),JSON.stringify({result:'PASS',before,checks,errors,acceptance:'native Electron coordinates, hover/expand/collapse/traffic updates/leave keep numeric strip unchanged; detail card clears it'},null,2));
 card.destroy();strip.destroy();app.quit();
}
run().catch(e=>{fs.writeFileSync(path.join(out,'failure.log'),e.stack+'\n'+JSON.stringify(errors));app.exit(1);});
