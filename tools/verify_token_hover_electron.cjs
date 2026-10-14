/* Actual production main/preload/avatar/card; isolated HTTP and userData. */
const fs=require('node:fs'),path=require('node:path'),http=require('node:http'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..'),desktop=path.join(root,'03-Src/gork-desktop');
const req=require('node:module').createRequire(path.join(desktop,'package.json'));
const {app,BrowserWindow}=req('electron');
const out=path.join(root,'Codex-Temp/ccswitch-hover-20261014/electron');fs.mkdirSync(out,{recursive:true});
const profile=path.join(out,'profile-'+Date.now());fs.mkdirSync(profile,{recursive:true});
process.env.GORK_TEST_USER_DATA=profile;app.setPath('userData',profile);app.getVersion=()=>req('./package.json').version;
app.commandLine.appendSwitch('force-device-scale-factor','1.5');
const web=path.join(root,'03-Src/stopwatch-voice-companion/static');
let tokenValue=JSON.parse(fs.readFileSync(path.join(root,'Codex-Temp/ccswitch-hover-20261014/live-usage.json'),'utf8'));
const liveValue={...tokenValue},requests=[],errors=[];
const server=http.createServer((request,response)=>{
  const url=new URL(request.url,'http://localhost').pathname;
  if(url.startsWith('/api/')){
    requests.push([request.method,url]);
    const data=url==='/api/desktop/token-usage'?tokenValue:url==='/api/health'?{
      app:'stopwatch-voice-companion',instance:'token-card-test',pid:process.pid,version:app.getVersion(),
      auto_connect_voice:false,voice:{ready:false},voice_service:{},robot:{connected:false},answer:{ready:false}}:
      url==='/api/desktop/state'?{phase:'idle',character:{revision:0},codex:{enabled:false}}:
      url==='/api/motion/expressions'?{revision:1,entries:[]}:
      url==='/api/cost/sentinel'?{enabled:false,history:[]}:
      url==='/api/codex/sentinel'?{enabled:false,threads:[],history:[],buckets:[]}:
      url==='/api/character/voice-library'?{items:[],enabled:false}:{};
    response.writeHead(200,{'Content-Type':'application/json'});response.end(JSON.stringify(data));return;
  }
  const file=path.resolve(web,url==='/'?'index.html':decodeURIComponent(url.replace(/^\/static\//,'')));
  if(!file.startsWith(web+path.sep)||!fs.existsSync(file)){response.writeHead(404);response.end();return;}
  response.writeHead(200,{'Content-Type':({'.html':'text/html','.js':'text/javascript','.css':'text/css','.json':'application/json'})[path.extname(file)]||'application/octet-stream'});
  fs.createReadStream(file).pipe(response);
});
app.on('browser-window-created',(_e,win)=>win.webContents.on('console-message',details=>{if(details.level==='error')errors.push(details.message);}));
const delay=ms=>new Promise(resolve=>setTimeout(resolve,ms));
async function until(check){for(let i=0;i<100;i++){if(await check())return;await delay(100);}throw Error('Hover acceptance timeout');}
const js=(win,code)=>win.webContents.executeJavaScript(code,true);
let avatar,card;
async function enter(){
  avatar.webContents.sendInputEvent({type:'mouseEnter',x:Math.round(avatar.getBounds().width/2),y:Math.round(avatar.getBounds().height/2)});
  avatar.webContents.sendInputEvent({type:'mouseMove',x:Math.round(avatar.getBounds().width/2),y:Math.round(avatar.getBounds().height/2)});
  await until(()=>{card=BrowserWindow.getAllWindows().find(w=>w.webContents.getURL().endsWith('/token-card.html'));return card?.isVisible();});
  await until(()=>js(card,"document.getElementById('token-total').textContent!=='—'"));
}
async function leave(){avatar.webContents.sendInputEvent({type:'mouseLeave',x:-1,y:-1});await until(()=>!card.isVisible());}
async function capture(name){fs.writeFileSync(path.join(out,name+'.png'),(await card.webContents.capturePage()).toPNG());}
async function run(){
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));process.env.GORK_BACKEND_PORT=String(server.address().port);
  await app.whenReady();require(path.join(desktop,'main.js'));
  await until(()=>{avatar=BrowserWindow.getAllWindows().find(w=>w.webContents.getURL().endsWith('/avatar.html'));return Boolean(avatar);});
  await until(()=>js(avatar,"typeof face!=='undefined'"));
  avatar.setBounds({x:120,y:140,width:240,height:280});
  const consoleWin=BrowserWindow.getAllWindows().find(w=>w.webContents.getURL().startsWith('http://127.0.0.1:'));
  await enter();
  const total=await js(card,"document.getElementById('token-total').title");
  assert.equal(total,liveValue.total_tokens.toLocaleString('zh-CN')+' tokens');
  assert.equal(card.isFocusable(),false);await capture('hover-live');
  const layouts=[];
  for(const scale of [25,100,150]){
    await js(consoleWin,`gorkDesktop.setAvatarScale(${scale})`);await delay(150);
    const layout=await js(card,"({width:innerWidth,height:innerHeight,scrollWidth:document.documentElement.scrollWidth,scrollHeight:document.documentElement.scrollHeight,bottom:document.querySelector('.token-card').getBoundingClientRect().bottom})");
    assert(layout.scrollWidth<=layout.width+1);assert(layout.bottom<=layout.height,JSON.stringify(layout));
    layouts.push({scale,...layout});await capture('hover-scale-'+scale);
  }
  await leave();const count=requests.filter(r=>r[1]==='/api/desktop/token-usage').length;
  await delay(300);assert.equal(requests.filter(r=>r[1]==='/api/desktop/token-usage').length,count);
  tokenValue={...liveValue,stale:true,status:'unavailable'};await enter();
  assert.equal(await js(card,'document.body.dataset.stale'),'true');await capture('hover-stale');await leave();
  tokenValue={status:'missing',total_tokens:null};
  avatar.webContents.sendInputEvent({type:'mouseEnter',x:40,y:40});avatar.webContents.sendInputEvent({type:'mouseMove',x:40,y:40});
  await until(()=>card.isVisible());await until(()=>js(card,"document.getElementById('token-status').textContent.includes('未找到')"));
  assert.equal(await js(card,"document.getElementById('token-total').textContent"),'—');await capture('hover-missing');await leave();
  tokenValue=liveValue;await enter();avatar.hide();await until(()=>!card.isVisible());
  avatar.showInactive();await delay(100);await enter();
  await js(avatar,"document.getElementById('avatar').dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true}))");
  await until(()=>!card.isVisible());
  await js(avatar,"document.getElementById('avatar').dispatchEvent(new FocusEvent('focusin',{bubbles:true}))");await until(()=>card.isVisible());
  assert.deepEqual(errors,[]);
  assert(!requests.some(([method,url])=>method!=='GET'&&/\/api\/(session|device|tts|answer)/.test(url)));
  fs.writeFileSync(path.join(out,'result.json'),JSON.stringify({result:'PASS',version:app.getVersion(),total,layouts,errors,
    checks:['Chromium mouse input enters/leaves actual avatar','live CC Switch snapshot displayed exactly','independent card at 25/100/150 percent',
      'no focus stealing','stale/missing do not fake zero','hide/show and Escape/focus','hover-only fetch','no voice/device requests']},null,2));
  app.quit();
}
run().catch(error=>{fs.writeFileSync(path.join(out,'failure.log'),String(error.stack));console.error(error);process.exitCode=1;app.quit();});
app.on('will-quit',()=>{server.closeAllConnections();server.close();});
