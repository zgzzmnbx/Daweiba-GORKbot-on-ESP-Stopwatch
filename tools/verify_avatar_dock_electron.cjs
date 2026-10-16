// Isolated real desktop renderer: no backend, cloud, audio or device connections.
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..'),desktop=path.join(root,'03-Src/gork-desktop');
const {app,BrowserWindow,ipcMain}=require('node:module').createRequire(path.join(desktop,'package.json'))('electron');
const out=path.join(root,'04-output/v0.21.1/tests');fs.mkdirSync(out,{recursive:true});
app.setPath('userData',path.join(root,'Codex-Temp/avatar-dock-'+Date.now()));
const delay=ms=>new Promise(r=>setTimeout(r,ms));
const calls=[],errors=[],layouts=[];
const state={mode:'idle',label:'就绪',character:{},codex:{enabled:true,status:'available',bucket:{windows:[{name:'7 天',remaining_percent:84}]}}};
ipcMain.handle('gork:get-state',()=>state);
for(const name of ['token-hover','open-console','hide-avatar','hide-token-card'])ipcMain.handle('gork:'+name,(_e,value)=>{calls.push({name,value});return true;});
async function run(){
 await app.whenReady();
 const win=new BrowserWindow({width:240,height:280,show:false,frame:false,transparent:true,webPreferences:{preload:path.join(desktop,'preload.js'),contextIsolation:true,sandbox:true,offscreen:true,backgroundThrottling:false}});
 win.webContents.on('console-message',d=>{if(d.level==='error')errors.push(d.message);});
 await win.loadFile(path.join(desktop,'avatar.html'));
 const js=code=>win.webContents.executeJavaScript(code,true);
 for(const [width,height] of [[60,70],[144,168],[182,213],[240,280],[360,420]])for(const enabled of [false,true]){
  win.setSize(width,height);
  win.webContents.send('gork:traffic',{enabled,physical:{status:'available',down_speed:13312,up_speed:1126},clash:{status:'available',latest:{proxy_down_speed:10,proxy_up_speed:10},routes:{PROXY:{upload:1000,download:6395310}}}});
  win.webContents.send('gork:state',state);await delay(150);
  const layout=await js(`(()=>{const rect=s=>{const b=document.querySelector(s).getBoundingClientRect();return {x:b.x,y:b.y,right:b.right,bottom:b.bottom,width:b.width,height:b.height}};return {width:innerWidth,height:innerHeight,head:rect('.face-wrap'),dock:rect('.avatar-dock'),buttons:[rect('#console'),rect('#hide')],duplicate:!document.getElementById('quota-detail').hidden,overflow:document.documentElement.scrollWidth>innerWidth||document.documentElement.scrollHeight>innerHeight}})()`);
  assert(!layout.overflow&&!layout.duplicate,JSON.stringify(layout));
  for(const b of [layout.head,...(height>180?[layout.dock,...layout.buttons]:[])])assert(b.x>=0&&b.y>=0&&b.right<=width+1&&b.bottom<=height+1,JSON.stringify(layout));
  if(height>180)assert(layout.dock.y>=layout.head.bottom+7);else assert.equal(layout.dock.height,0);
  layouts.push({enabled,...layout});
  await win.webContents.capturePage();await delay(100);
  fs.writeFileSync(path.join(out,`avatar-${width}-${enabled?'traffic':'quiet'}.png`),(await win.webContents.capturePage()).toPNG());
 }
 win.setSize(182,213);win.webContents.send('gork:state',{...state,label:'语音服务暂时不可用，正在等待重新连接'});await delay(100);
 assert(await js("document.getElementById('status').scrollWidth>document.getElementById('status').clientWidth"));
 await js("document.getElementById('console').click();document.getElementById('hide').click();document.getElementById('traffic-badge').click();document.getElementById('avatar').dispatchEvent(new PointerEvent('pointerenter'))");await delay(50);
 assert.equal(calls.filter(c=>c.name==='open-console').length,2);assert.equal(calls.filter(c=>c.name==='hide-avatar').length,1);
 assert(calls.some(c=>c.name==='token-hover'&&c.value));
 assert.equal(await js("getComputedStyle(document.getElementById('status')).webkitAppRegion"),'drag');
 assert.equal(errors.length,0,errors.join('\n'));
 fs.writeFileSync(path.join(out,'result.json'),JSON.stringify({result:'PASS',layouts,errors,checks:['five desktop avatar scales, traffic on/off','no overlap or overflow; tiny scales retain silhouette','no duplicate quota bubble','console/hide/traffic actions and token hover IPC','long status truncates; status remains draggable']},null,2));
 if(fs.existsSync(path.join(out,'failure.log')))fs.unlinkSync(path.join(out,'failure.log'));
 app.quit();
}
run().catch(e=>{fs.writeFileSync(path.join(out,'failure.log'),e.stack+'\n'+JSON.stringify(errors));app.exit(1);});
