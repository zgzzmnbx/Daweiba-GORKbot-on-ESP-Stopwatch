/* Real generated console with its production modules; isolated HTTP and profile. */
const fs=require('node:fs'),path=require('node:path'),http=require('node:http'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..'),desktop=path.join(root,'03-Src/gork-desktop');
const {app,BrowserWindow,ipcMain}=require('node:module').createRequire(path.join(desktop,'package.json'))('electron');
const out=path.join(root,'04-output/v0.21.0/tests');fs.mkdirSync(out,{recursive:true});
app.setPath('userData',path.join(root,'Codex-Temp/v0210-electron-profile-'+Date.now()));
const web=path.join(root,'03-Src/stopwatch-voice-companion/static');
let traffic={enabled:false,day:'2026-10-15',physical:{status:'available',up_speed:51200,down_speed:2097152},clash:{status:'available',latest:{proxy_up_speed:12288,proxy_down_speed:1048576},routes:{PROXY:{upload:12345,download:1073741824},DIRECT:{upload:2345,download:987654}},difference:{upload:123,download:456}},processes:[{name:'codex.exe',upload:12345,download:1073741824,proxy:1073741824,direct:12345},{name:'chrome.exe',upload:34567,download:987654,proxy:0,direct:1022221}],domains:[],connections:[],history:{status:'available',updated_at:1792050404,rows:[{day:'2026-10-15',name:'ordinary.exe',upload:2048,download:4096}]}};
let outage=false,busy=false,session=false,generation=0,paused=false;
let volume=37,watchVolume=20,watchConnected=true,watchFail=false;
let receipts=[{source:'astra',event_id:'one',accepted_at:new Date().toISOString(),status:'queued',request:{text:'造价智算 Astra：表内含税金额 128,600 元。'}}];
let codex={enabled:false,mode:'auto',thread_id:'',target:'both',sound:false,sound_target:'pc',threshold:17,bucket_id:'',ring_mode:'hover',drop_step:3,drop_animation:false,history:[],threads:[],quota:{buckets:{}}};
const requests=[],errors=[];
const server=http.createServer(async(request,response)=>{
  const url=new URL(request.url,'http://localhost').pathname;
  if(url!=='/init')response.setHeader('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; media-src 'self' blob:; worker-src 'self'; frame-ancestors 'none'");
  if(url==='/init'){
    response.writeHead(200,{'Content-Type':'text/html'});
    response.end(`<script>localStorage.setItem('gork.cloud-defaults-v1','true');localStorage.setItem('gork.speech','{"cloud_voice":"Ethan","speaker_id":58,"speed":1}');localStorage.setItem('gork.audio-consent','false');localStorage.setItem('gork.asr','local');localStorage.setItem('gork.text-consent','true');localStorage.setItem('gork.answer-consent','false');location.href='/';</script>`);return;
  }
  if(url.startsWith('/api/')){
    let body='';for await(const chunk of request)body+=chunk;
    const value=body?JSON.parse(body):null;requests.push({url,method:request.method,body:value});
    const reply=(data,status=200)=>{response.writeHead(status,{'Content-Type':'application/json'});response.end(JSON.stringify(data));};
    const error=(status,code)=>reply({error:{code,message:'隔离断线测试'}},status);
    if(url==='/api/session'){
      if(request.method==='POST'){
        if(busy)return error(409,'SESSION_BUSY');
        if(outage)return error(503,'VOICE_OFFLINE');
        session=true;generation=0;return reply({generation});
      }
      if(outage||!session)return error(401,'VOICE_SESSION_INVALID');
      return reply({generation,phase:'idle',robot:{connected:watchConnected,network:{route:'wifi'}}});
    }
    if(url==='/api/voice/session'&&request.method==='DELETE'){session=false;return reply({released:true});}
    if(url==='/api/settings'){generation=value.generation;return reply({generation});}
    if(url==='/api/health')return reply({version:'0.21.0-dev',auto_connect_voice:true,external_protocol:{version:'1.0'},
      watch_dialogue:{enabled:false,stage:'disabled'},voice:{ready:!outage},
      ...(outage?{voice_error:{code:'VOICE_OFFLINE',message:'隔离断线测试'}}:{}),
      voice_service:{mode:'external',configured:false},voice_url:'fixture',robot:{connected:watchConnected,network:{route:'wifi'}},answer:{enabled:true,model:'deepseek-chat'},speech_output:{route:'cloud'},
      capabilities:{protocol_version:1,tts:{speakers:[{id:58,label:'Local 58'}]},cloud:{state:'configured',tts_model:'qwen3-tts-flash',request_voice:true,voices:[{id:'Ethan',label:'Ethan'},{id:'Cherry',label:'Cherry'}]}}});
    if(url==='/api/motion/expressions')return reply({revision:1,entries:[]});
    if(url==='/api/character/voice-library')return reply({items:[],enabled:false});
    if(url==='/api/device/sound/volume'){if(watchFail)return error(503,'DEVICE_ERROR');watchVolume=value.volume;return reply('OK:SOUND');}
    if(url==='/api/traffic'){if(request.method==='PUT')traffic={...traffic,enabled:value.enabled};return reply(traffic);}
    if(url==='/api/voice/volume'){if(request.method==='PUT')volume=value.volume;return reply({volume});}
    if(url==='/api/external/overview')return reply({paused,clients:[{source:'astra',label:'造价智算 Astra',enabled:true,display_targets:['desktop'],speech_targets:[]}],receipts,current:{},current_sound_target:'pc',pending:0});
    if(url==='/api/external/pause'||url==='/api/external/resume'){paused=url.endsWith('pause');return reply({paused});}
    if(url==='/api/codex/sentinel'){if(request.method==='PUT')codex={...codex,...value};return reply(codex);}
    if(url==='/api/cost/sentinel')return reply({enabled:false,history:[]});
    return reply({generation,robot:{connected:watchConnected,network:{route:'wifi'}}});
  }
  const file=path.resolve(web,url==='/'?'index.html':decodeURIComponent(url.replace(/^\/static\//,'')));
  if(!file.startsWith(web+path.sep)||!fs.existsSync(file)){response.writeHead(404);response.end();return;}
  response.writeHead(200,{'Content-Type':({'.html':'text/html','.js':'text/javascript','.css':'text/css','.json':'application/json','.svg':'image/svg+xml'})[path.extname(file)]||'application/octet-stream'});fs.createReadStream(file).pipe(response);
});
const delay=ms=>new Promise(resolve=>setTimeout(resolve,ms));
async function until(check){for(let i=0;i<100;i++){if(await check())return;await delay(100);}throw Error('UI condition timed out');}
async function run(){
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));await app.whenReady();
 const win=new BrowserWindow({width:1180,height:820,show:false,webPreferences:{contextIsolation:true,nodeIntegration:false,sandbox:true,backgroundThrottling:false,offscreen:true}});
 win.webContents.on('console-message',details=>{if(details.level==='error')errors.push(details.message);});
 const js=code=>win.webContents.executeJavaScript(code,true);
 await win.loadURL(`http://127.0.0.1:${server.address().port}/init`);
 await until(()=>js("!document.getElementById('header-traffic').disabled"));
 await js("document.querySelector('[data-page-link=traffic]').click();document.getElementById('header-traffic').click()");
 await until(()=>traffic.enabled);
 await until(()=>js("document.getElementById('header-traffic').getAttribute('aria-checked')==='true'"));
 assert.equal(await js("document.getElementById('page-traffic').hidden"),false);
 assert.equal(await js("document.getElementById('traffic-proxy-down').textContent"),'1.0 MiB/s');
 const layouts=[];
 for(const theme of ['mantine-dark','mantine-light','classic'])for(const width of [1180,800]){
  win.setSize(width,820);
  await js(`if(document.documentElement.dataset.consoleTheme!=='${theme==='classic'?'classic':'mantine'}')document.getElementById('theme-toggle').click();if('${theme}'!=='classic'&&document.documentElement.dataset.consoleScheme!=='${theme.endsWith('dark')?'dark':'light'}')document.getElementById('color-scheme-toggle').click()`);await delay(200);
  const layout=await js(`(()=>{const b=document.getElementById('header-traffic').getBoundingClientRect(),p=document.getElementById('page-traffic').getBoundingClientRect();return {width:innerWidth,overflow:document.documentElement.scrollWidth>innerWidth,button:{x:b.x,right:b.right,y:b.y,bottom:b.bottom},panel:{x:p.x,right:p.right},height:innerHeight}})()`);
  assert(!layout.overflow&&layout.button.x>=0&&layout.button.right<=layout.width&&layout.panel.right<=layout.width+1,JSON.stringify(layout));
  layouts.push({theme,...layout});fs.writeFileSync(path.join(out,`traffic-${theme}-${width}.png`),(await win.webContents.capturePage()).toPNG());
 }
 await js("document.getElementById('traffic-view').value='windows';document.getElementById('traffic-view').dispatchEvent(new Event('change'))");
 assert((await js("document.getElementById('traffic-rows').textContent")).includes('ordinary.exe'));
 await js("document.getElementById('header-traffic').click()");await until(()=>!traffic.enabled);
 assert.equal(requests.filter(r=>r.url==='/api/traffic'&&r.method==='PUT').length,2);
 const avatar=new BrowserWindow({width:240,height:280,show:false,frame:false,transparent:true,webPreferences:{preload:path.join(desktop,'preload.js'),contextIsolation:true,nodeIntegration:false,sandbox:true,offscreen:true}});
 ipcMain.handle('gork:get-state',()=>({mode:'idle',label:'就绪',character:{},codex:{enabled:false}}));
 ipcMain.handle('gork:token-hover',()=>true);
 avatar.webContents.on('console-message',details=>{if(details.level==='error')errors.push(details.message);});
 await avatar.loadFile(path.join(desktop,'avatar.html'));
 for(const [width,height] of [[240,280],[144,168],[60,70]]){
  avatar.setSize(width,height);avatar.webContents.send('gork:traffic',{...traffic,enabled:true});
  // Normal state refresh must retain the badge's reserved layout space.
  avatar.webContents.send('gork:state',{mode:'idle',label:'就绪',character:{},codex:{enabled:false}});await delay(200);
  const layout=await avatar.webContents.executeJavaScript(`(()=>{const b=document.getElementById('traffic-badge').getBoundingClientRect();return {width:innerWidth,height:innerHeight,x:b.x,y:b.y,right:b.right,bottom:b.bottom,hidden:document.getElementById('traffic-badge').hidden}})()`);
  assert(!layout.hidden&&layout.x>=0&&layout.y>=0&&layout.right<=width+1&&layout.bottom<=height+1,JSON.stringify(layout));layouts.push({avatar:true,...layout});
  fs.writeFileSync(path.join(out,`avatar-${width}.png`),(await avatar.webContents.capturePage()).toPNG());
 }
 avatar.webContents.send('gork:traffic',{enabled:false});await delay(100);
 assert.equal(await avatar.webContents.executeJavaScript("document.getElementById('traffic-badge').hidden"),true);
 assert.equal(errors.length,0,errors.join('\n'));
 assert(!requests.some(r=>/tts|synthesize|\/record/.test(r.url)));
 fs.writeFileSync(path.join(out,'electron-result.json'),JSON.stringify({result:'PASS',layouts,errors,checks:['production console DOM/modules and desktop preload IPC','three themes at two desktop widths','switch on/off and Windows history view','three avatar sizes; ordinary state updates preserve badge','no voice, device or cloud calls']},null,2));
 app.quit();
}
run().catch(error=>{fs.writeFileSync(path.join(out,'failure.log'),String(error.stack)+'\n'+JSON.stringify(errors));app.exit(1);});
app.on('will-quit',()=>{server.closeAllConnections();server.close();});
