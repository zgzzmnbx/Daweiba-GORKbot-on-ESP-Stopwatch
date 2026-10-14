/* Production main/preload/console/avatar with an isolated profile and HTTP fixture. */
const fs=require('node:fs'),path=require('node:path'),http=require('node:http'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..'),desktop=path.join(root,'03-Src/gork-desktop');
const req=require('node:module').createRequire(path.join(desktop,'package.json'));
const custom={id:'motion-000000000001',revision:1,scene:'writing',config:req('./motion/gork-config').defaults()};
const {app,BrowserWindow,screen}=req('electron');
const out=path.join(root,'Codex-Temp/pointer-follow-20261012/electron');fs.mkdirSync(out,{recursive:true});
const restore=process.argv.includes('--restore-off');
const profile=restore?fs.readFileSync(path.join(out,'last-profile.txt'),'utf8'):path.join(out,'profile-'+Date.now());
fs.mkdirSync(profile,{recursive:true});
if(!restore)fs.writeFileSync(path.join(out,'last-profile.txt'),profile);
process.env.GORK_TEST_USER_DATA=profile;app.setPath('userData',profile);
app.getVersion=()=>req('./package.json').version;
app.commandLine.appendSwitch('force-device-scale-factor','1.5');
const web=path.join(root,'03-Src/stopwatch-voice-companion/static'),requests=[],errors=[];
const server=http.createServer((request,response)=>{
  const pathname=new URL(request.url,'http://localhost').pathname;
  if(pathname.startsWith('/api/')) {
    requests.push([request.method,pathname]);
    const data=pathname==='/api/health'?{app:'stopwatch-voice-companion',instance:'isolated-pointer-test',pid:process.pid,
      version:app.getVersion(),auto_connect_voice:false,voice:{ready:false},voice_service:{},robot:{connected:false},answer:{ready:false}}:
      pathname==='/api/desktop/state'?{phase:'idle',character:{revision:0},codex:{enabled:false}}:
      pathname==='/api/motion/expressions'?{revision:1,entries:[]}:
      pathname.startsWith('/api/motion/expressions/')?custom:
      pathname==='/api/cost/sentinel'?{enabled:false,history:[]}:
      pathname==='/api/codex/sentinel'?{enabled:false,threads:[],history:[],buckets:[]}:
      pathname==='/api/character/voice-library'?{items:[],enabled:false}:{};
    response.writeHead(200,{'Content-Type':'application/json'});response.end(JSON.stringify(data));return;
  }
  const filename=pathname==='/'?'index.html':pathname.replace(/^\/static\//,'');
  const resolved=path.resolve(web,decodeURIComponent(filename));
  if(!resolved.startsWith(web+path.sep)||!fs.existsSync(resolved)){response.writeHead(404);response.end();return;}
  const types={'.html':'text/html','.js':'text/javascript','.css':'text/css','.json':'application/json'};
  response.writeHead(200,{'Content-Type':types[path.extname(resolved)]||'application/octet-stream'});
  fs.createReadStream(resolved).pipe(response);
});
app.on('browser-window-created',(_event,win)=>win.webContents.on('console-message',details=>{
  if(details.level==='error')errors.push(details.message);
}));
const delay=ms=>new Promise(resolve=>setTimeout(resolve,ms));
async function until(check){for(let i=0;i<100;i++){const value=await check();if(value)return value;await delay(100);}throw Error('Electron pointer acceptance timeout');}
const js=(win,code)=>win.webContents.executeJavaScript(code,true);
// Read the native global cursor first; then drive deterministic DIP samples
// through the production tracker/IPC to avoid competing with the user's mouse.
let drivenCursor=null,nativeCursor;
function move(point){drivenCursor=point;}
async function capture(win,name){fs.writeFileSync(path.join(out,name+'.png'),(await win.webContents.capturePage()).toPNG());}
async function run(){
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  process.env.GORK_BACKEND_PORT=String(server.address().port);
  await app.whenReady();nativeCursor=screen.getCursorScreenPoint.bind(screen);
  screen.getCursorScreenPoint=()=>drivenCursor||nativeCursor();
  require(path.join(desktop,'main.js'));
  const originalCursor=nativeCursor();
  const avatar=await until(()=>BrowserWindow.getAllWindows().find(w=>w.webContents.getURL().endsWith('/avatar.html')));
  const consoleWin=await until(()=>BrowserWindow.getAllWindows().find(w=>w.webContents.getURL().startsWith('http://127.0.0.1:')));
  await until(()=>js(consoleWin,"Boolean(document.getElementById('desktop-pointer-follow')&&!document.getElementById('desktop-pointer-follow').disabled)"));
  await until(()=>js(avatar,"typeof face!=='undefined'"));
  consoleWin.show();await js(consoleWin,"document.querySelector('[data-page-link=settings]').click()");
  assert.equal(await js(consoleWin,"document.getElementById('desktop-pointer-follow').checked"),!restore);
  if(restore){
    assert.equal(await js(avatar,'pointerFollow'),false);
    fs.writeFileSync(path.join(out,'restart.json'),JSON.stringify({result:'PASS',savedOffRestored:true,version:app.getVersion()},null,2));
    app.quit();return;
  }
  const display=screen.getPrimaryDisplay().workArea;
  avatar.setBounds({x:Math.round(display.x+display.width/2-120),y:Math.round(display.y+display.height/2-140),width:240,height:280});
  await js(avatar,`window.__lastPose=null;const originalPose=AvatarProceduralEngine.poseFromExpression;AvatarProceduralEngine.poseFromExpression=p=>{window.__lastPose={headX:p.headX,headY:p.headY};return originalPose(p);};const originalDraw=GorkAppearance.draw;GorkAppearance.draw=(ctx,p,b,a)=>{window.__basePose={headX:p.headX,headY:p.headY};return originalDraw(ctx,p,b,a);};window.__pointerSamples=[];gorkDesktop.onPointer(p=>window.__pointerSamples.push(p));void 0;`);
  await delay(200);
  avatar.hide();avatar.showInactive();await delay(100);
  const nativeSamples=await js(avatar,'window.__pointerSamples.filter(Boolean)');
  assert(nativeSamples.length>0,'native global cursor crosses the real preload bridge');
  const rect=await js(avatar,"JSON.parse(JSON.stringify(document.getElementById('gork-face').getBoundingClientRect()))");
  const bounds=avatar.getContentBounds();
  const center={x:Math.round(bounds.x+rect.left+rect.width/2),y:Math.round(bounds.y+rect.top+rect.height/2)};
  const right={x:Math.round(display.x+display.width*.88),y:Math.round(display.y+display.height*.18)};
  const left={x:Math.round(display.x+display.width*.12),y:Math.round(display.y+display.height*.82)};
  move(right);await delay(1150);const rightPose=await js(avatar,'window.__lastPose');
  fs.writeFileSync(path.join(out,'coordinates.json'),JSON.stringify({display,bounds,rect,center,right,actual:screen.getCursorScreenPoint(),samples:await js(avatar,'window.__pointerSamples.slice(-3)'),rightPose},null,2));
  assert(rightPose.headY>10&&rightPose.headX>10,JSON.stringify(rightPose));await capture(avatar,'look-up-right');
  move(left);await delay(1300);const leftPose=await js(avatar,'window.__lastPose');
  assert(leftPose.headY< -10&&leftPose.headX< -10,JSON.stringify(leftPose));await capture(avatar,'look-down-left');
  move(center);await delay(1350);const centerPose=await js(avatar,'window.__lastPose');
  assert(Math.abs(centerPose.headX)<2&&Math.abs(centerPose.headY)<2,JSON.stringify(centerPose));
  await js(consoleWin,"const toggle=document.getElementById('desktop-pointer-follow');toggle.checked=false;toggle.dispatchEvent(new Event('change'));");
  await until(()=>js(avatar,'pointerFollow===false'));
  const sampleCount=await js(avatar,'window.__pointerSamples.length');move(right);await delay(250);
  assert.equal(await js(avatar,'window.__pointerSamples.length'),sampleCount,'off stops the sampler');
  assert.equal(JSON.parse(fs.readFileSync(path.join(profile,'window-state.json'),'utf8')).pointerFollow,false);
  consoleWin.webContents.reload();await until(()=>js(consoleWin,"document.getElementById('desktop-pointer-follow')?.disabled===false"));
  assert.equal(await js(consoleWin,"document.getElementById('desktop-pointer-follow').checked"),false);
  await js(consoleWin,"document.querySelector('[data-page-link=settings]').click();const t=document.getElementById('desktop-pointer-follow');t.checked=true;t.dispatchEvent(new Event('change'));");
  await until(()=>js(avatar,'pointerFollow===true'));move(left);await delay(1200);
  assert((await js(avatar,'window.__lastPose')).headY< -10);
  // Manual states and custom animation keep ownership even while the cursor moves.
  await js(consoleWin,"gorkDesktop.setAvatarScene({expression:'thinking',mode:'loop',startedAt:Date.now()})");move(right);await delay(1100);
  const thinking=await js(avatar,'window.__lastPose');assert.deepEqual(thinking,await js(avatar,'window.__basePose'));
  await js(consoleWin,"gorkDesktop.playCustomExpression('motion-000000000001','loop')");
  move(left);await delay(350);assert.equal(await js(avatar,'face.getState().kind'),'scenes');
  await js(consoleWin,"gorkDesktop.setAvatarScene({expression:'idle',mode:'loop',startedAt:Date.now()})");
  avatar.hide();await delay(100);const hiddenCount=await js(avatar,'window.__pointerSamples.length');move(right);await delay(200);
  assert.equal(await js(avatar,'window.__pointerSamples.length'),hiddenCount);avatar.showInactive();await delay(1100);
  assert((await js(avatar,'window.__lastPose')).headY>10);
  const sizes=[];
  for(const scale of [25,100,150]){
    await js(consoleWin,`gorkDesktop.setAvatarScale(${scale})`);await delay(100);
    const layout=await js(avatar,"({width:innerWidth,scroll:document.documentElement.scrollWidth,dpr:devicePixelRatio})");
    assert(layout.scroll<=layout.width+1);sizes.push({scale,...layout});await capture(avatar,'avatar-'+scale);
  }
  for(const theme of ['mantine','classic']){
    await js(consoleWin,`document.documentElement.dataset.consoleTheme==='${theme}'||document.getElementById('theme-toggle').click()`);
    await delay(100);await capture(consoleWin,'settings-'+theme);
    const box=await js(consoleWin,"(()=>{const r=document.getElementById('desktop-pointer-follow').getBoundingClientRect();return {x:r.x,y:r.y,width:r.width,height:r.height};})()");
    assert(box.width>0&&box.height>0);
  }
  assert(!requests.some(([method,url])=>/\/api\/(session|device|tts|answer)/.test(url)&&method!=='GET'));
  assert.deepEqual(errors,[]);
  // Keep the isolated preference off to validate a fresh main-process restart.
  await js(consoleWin,'gorkDesktop.setPointerFollow(false)');
  fs.writeFileSync(path.join(out,'result.json'),JSON.stringify({result:'PASS',version:app.getVersion(),rightPose,leftPose,centerPose,thinking,sizes,
    nativeCursor:originalCursor,nativeSamples,coordinateDriver:'deterministic DIP samples through production screen/IPC',
    checks:['global cursor outside avatar','both axes and neutral center at 150% DPI','immediate switch and stopped sampling','saved off after console reload',
      'manual/custom animation priority','hide/show cleanup','25/100/150 sizes','classic/Mantine switch layouts'],errors,requests},null,2));
  drivenCursor=null;app.quit();
}
run().catch(error=>{fs.writeFileSync(path.join(out,'failure.log'),String(error.stack));console.error(error);process.exitCode=1;app.quit();});
app.on('will-quit',()=>{server.closeAllConnections();server.close();});
