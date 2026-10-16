/* Real generated console with its production modules; isolated HTTP and profile. */
const fs=require('node:fs'),path=require('node:path'),http=require('node:http'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..'),desktop=path.join(root,'03-Src/gork-desktop');
const {app,BrowserWindow}=require('node:module').createRequire(path.join(desktop,'package.json'))('electron');
const out=path.join(root,'04-output/v0.20.42/tests');fs.mkdirSync(out,{recursive:true});
app.setPath('userData',path.join(root,'Codex-Temp/v42-electron-profile-'+Date.now()));
const web=path.join(root,'03-Src/stopwatch-voice-companion/static');
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
    if(url==='/api/health')return reply({version:'0.20.42-dev',auto_connect_voice:true,external_protocol:{version:'1.0'},
      watch_dialogue:{enabled:false,stage:'disabled'},voice:{ready:!outage},
      ...(outage?{voice_error:{code:'VOICE_OFFLINE',message:'隔离断线测试'}}:{}),
      voice_service:{mode:'external',configured:false},voice_url:'fixture',robot:{connected:watchConnected,network:{route:'wifi'}},answer:{enabled:true,model:'deepseek-chat'},speech_output:{route:'cloud'},
      capabilities:{protocol_version:1,tts:{speakers:[{id:58,label:'Local 58'}]},cloud:{state:'configured',tts_model:'qwen3-tts-flash',request_voice:true,voices:[{id:'Ethan',label:'Ethan'},{id:'Cherry',label:'Cherry'}]}}});
    if(url==='/api/motion/expressions')return reply({revision:1,entries:[]});
    if(url==='/api/character/voice-library')return reply({items:[],enabled:false});
    if(url==='/api/device/sound/volume'){if(watchFail)return error(503,'DEVICE_ERROR');watchVolume=value.volume;return reply('OK:SOUND');}
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
async function until(check){for(let i=0;i<120;i++){if(await check())return;await delay(100);}const w=BrowserWindow.getAllWindows()[0];fs.writeFileSync(path.join(out,'diagnostic.json'),JSON.stringify({requests,errors,dom:await w.webContents.executeJavaScript("({hidden:document.hidden,visibility:document.visibilityState,feedback:document.getElementById('external-feedback').textContent,message:document.getElementById('message').textContent})")},null,2));throw Error('Connection acceptance timeout');}
const posts=()=>requests.filter(r=>r.url==='/api/session'&&r.method==='POST');
async function run(){
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));await app.whenReady();
 const win=new BrowserWindow({width:1180,height:820,show:false,webPreferences:{contextIsolation:true,nodeIntegration:false,sandbox:true,backgroundThrottling:false,offscreen:true}});
 win.webContents.on('console-message',details=>{if(details.level==='error')errors.push(details.message);});
 const js=code=>win.webContents.executeJavaScript(code,true);
 await win.loadURL(`http://127.0.0.1:${server.address().port}/init`);
 await until(()=>js("!document.getElementById('header-watch-volume').disabled"));
 assert.equal(await js("document.getElementById('header-watch-volume-label').textContent"),'—');
 assert.equal(requests.filter(r=>r.url==='/api/device/sound/volume').length,0);
 await js("document.getElementById('header-volume-menu').querySelector('summary').click();var s=document.getElementById('header-watch-volume');s.value='65';s.dispatchEvent(new Event('input',{bubbles:true}));");
 assert.equal(requests.filter(r=>r.url==='/api/device/sound/volume').length,0);
 assert.equal(await js("document.getElementById('sound-volume').value"),'65');
 await js("document.getElementById('header-watch-volume').dispatchEvent(new Event('change',{bubbles:true}))");await until(()=>watchVolume===65);
 await until(()=>js("document.getElementById('header-watch-volume-hint').textContent.includes('已确认')"));assert.equal(volume,37);
 await js("var s=document.getElementById('sound-volume');s.value='45';s.dispatchEvent(new Event('input',{bubbles:true}));s.dispatchEvent(new Event('change',{bubbles:true}));");await until(()=>watchVolume===45);await until(()=>js("!document.getElementById('header-watch-volume').disabled"));
 assert.equal(await js("document.getElementById('header-watch-volume-label').textContent"),'45%');
 const layouts=[];
 for(const theme of ['mantine-dark','mantine-light','classic'])for(const width of [1180,800]){
  win.setSize(width,820);
  await js(`if(document.documentElement.dataset.consoleTheme!=='${theme==='classic'?'classic':'mantine'}')document.getElementById('theme-toggle').click();if('${theme}'!=='classic'&&document.documentElement.dataset.consoleScheme!=='${theme.endsWith('dark')?'dark':'light'}')document.getElementById('color-scheme-toggle').click();document.getElementById('header-volume-menu').open=true`);await delay(150);
  const layout=await js(`(()=>{const panel=document.querySelector('.volume-panel').getBoundingClientRect();return {width:innerWidth,overflow:document.documentElement.scrollWidth>innerWidth,panel:{x:panel.x,y:panel.y,right:panel.right,bottom:panel.bottom},height:innerHeight,inputs:['voice-volume','header-watch-volume'].map(id=>{const r=document.getElementById(id).getBoundingClientRect();return {id,x:r.x,right:r.right,y:r.y,bottom:r.bottom,width:r.width,height:r.height}})}})()`);
  assert(!layout.overflow&&layout.panel.x>=0&&layout.panel.right<=layout.width&&layout.panel.bottom<=layout.height,JSON.stringify(layout));
  for(const r of layout.inputs)assert(r.width>=80&&r.height>0&&r.x>=layout.panel.x&&r.right<=layout.panel.right,JSON.stringify(r));
  assert(layout.inputs[0].bottom<layout.inputs[1].y);layouts.push({theme,...layout});
  await win.webContents.capturePage();await delay(100);fs.writeFileSync(path.join(out,`volume-${theme}-${width}.png`),(await win.webContents.capturePage()).toPNG());
 }
 watchFail=true;
 await js("var s=document.getElementById('header-watch-volume');s.value='80';s.dispatchEvent(new Event('change',{bubbles:true}));");await until(()=>js("document.getElementById('header-watch-volume-hint').textContent.includes('提交未确认')"));assert.equal(watchVolume,45);
 assert.equal(await js("document.getElementById('sound-volume-label').textContent"),'—');
 watchConnected=false;await until(()=>js("document.getElementById('header-watch-volume').disabled"));
 assert.match(await js("document.getElementById('header-watch-volume-hint').textContent"),/未连接/);
 assert.equal(requests.filter(r=>r.url==='/api/device/sound/volume').length,3);
 assert(!requests.some(r=>/\/answer$|\/tts|\/synthesize|\/transcribe|\/record/.test(r.url)));
 // One expected HTTP 503 from the isolated failure case, no script errors.
 const unexpected=errors.filter(e=>!e.includes('503'));assert.equal(unexpected.length,0,unexpected.join('\n'));
 fs.writeFileSync(path.join(out,'result.json'),JSON.stringify({result:'PASS',checks:['6 Windows desktop layouts only, no phone validation','header and Watch page share submitted state','no write on drag alone, one write on release','computer volume unchanged by Watch slider','failure clears unconfirmed value; disconnect disables','production generated DOM and strict CSP; isolated device API, no real playback'],layouts},null,2));app.quit();
}
run().catch(error=>{fs.writeFileSync(path.join(out,'failure.log'),String(error.stack)+'\n'+JSON.stringify(errors));app.exit(1);});
app.on('will-quit',()=>{server.closeAllConnections();server.close();});
