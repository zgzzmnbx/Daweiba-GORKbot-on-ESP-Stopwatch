/* Real generated console with its production modules; isolated HTTP and profile. */
const fs=require('node:fs'),path=require('node:path'),http=require('node:http'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..'),desktop=path.join(root,'03-Src/gork-desktop');
const {app,BrowserWindow}=require('node:module').createRequire(path.join(desktop,'package.json'))('electron');
const out=path.join(root,'04-output/v0.21.5/header');fs.mkdirSync(out,{recursive:true});
app.setPath('userData',path.join(root,'Codex-Temp/v215-header-'+Date.now()));
const web=path.join(root,'03-Src/stopwatch-voice-companion/static');
let outage=false,busy=false,session=false,generation=0,paused=false;
let volume=37;
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
      return reply({generation,phase:'idle',robot:{connected:false}});
    }
    if(url==='/api/voice/session'&&request.method==='DELETE'){session=false;return reply({released:true});}
    if(url==='/api/settings'){generation=value.generation;return reply({generation});}
    if(url==='/api/health')return reply({version:'0.20.41-dev',auto_connect_voice:true,external_protocol:{version:'1.0'},
      watch_dialogue:{enabled:false,stage:'disabled'},voice:{ready:!outage},
      ...(outage?{voice_error:{code:'VOICE_OFFLINE',message:'隔离断线测试'}}:{}),
      voice_service:{mode:'external',configured:false},voice_url:'fixture',robot:{connected:false},answer:{enabled:true,model:'deepseek-chat'},speech_output:{route:'cloud'},
      capabilities:{protocol_version:1,tts:{speakers:[{id:58,label:'Local 58'}]},cloud:{state:'configured',tts_model:'qwen3-tts-flash',request_voice:true,voices:[{id:'Ethan',label:'Ethan'},{id:'Cherry',label:'Cherry'}]}}});
    if(url==='/api/motion/expressions')return reply({revision:1,entries:[]});
    if(url==='/api/character/voice-library')return reply({items:[],enabled:false});
    if(url==='/api/voice/volume'){if(request.method==='PUT')volume=value.volume;return reply({volume});}
    if(url==='/api/external/overview')return reply({paused,clients:[{source:'astra',label:'造价智算 Astra',enabled:true,display_targets:['desktop'],speech_targets:[]}],receipts,current:{},current_sound_target:'pc',pending:0});
    if(url==='/api/external/pause'||url==='/api/external/resume'){paused=url.endsWith('pause');return reply({paused});}
    if(url==='/api/codex/sentinel'){if(request.method==='PUT')codex={...codex,...value};return reply(codex);}
    if(url==='/api/cost/sentinel')return reply({enabled:false,history:[]});
    return reply({generation,robot:{connected:false}});
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
 await win.loadURL(`http://127.0.0.1:${server.address().port}/init`);await delay(900);
 await until(()=>js("document.getElementById('service-answer').dataset.state!=='unknown'"));
 const layouts=[];
 for(const theme of ['mantine-dark','mantine-light','classic'])for(const width of [1180,800]){
  win.setSize(width,820);
  await js(`if(document.documentElement.dataset.consoleTheme!=='${theme==='classic'?'classic':'mantine'}')document.getElementById('theme-toggle').click();if('${theme}'!=='classic'&&document.documentElement.dataset.consoleScheme!=='${theme.endsWith('dark')?'dark':'light'}')document.getElementById('color-scheme-toggle').click()`);await delay(100);
  for(const route of ['Wi-Fi','蓝牙']){
   const layout=await js(`(()=>{GorkShell.session({connected:true,voiceLabel:'已连接',robotConnected:true,watchLink:'${route}'});const rect=e=>{const r=e.getBoundingClientRect();return {x:r.x,y:r.y,right:r.right,bottom:r.bottom,w:r.width,h:r.height}};return {width:innerWidth,overflow:document.documentElement.scrollWidth>innerWidth,label:document.getElementById('watch-transport').textContent,badge:rect(document.getElementById('watch-transport')),header:[...document.querySelectorAll('.global-status>.service-chip>summary,.header-tools>.header-menu>summary,.header-tools>button')].map(rect)}})()`);
   assert.equal(layout.label,route);assert(!layout.overflow);assert(layout.badge.w>0&&layout.badge.right<=layout.width);
   for(const r of layout.header)assert(r.x>=0&&r.right<=layout.width);
   for(let i=0;i<layout.header.length;i++)for(let j=i+1;j<layout.header.length;j++){const a=layout.header[i],b=layout.header[j];assert(!(a.x<b.right&&a.right>b.x&&a.y<b.bottom&&a.bottom>b.y),'header overlap');}
   layouts.push({theme,width,route,...layout});
  }
  fs.writeFileSync(path.join(out,`${theme}-${width}.png`),(await win.webContents.capturePage()).toPNG());
 }
 assert.equal(await js("GorkShell.session({robotConnected:false});document.getElementById('watch-transport').textContent"),'未连接');
 assert.equal(await js("GorkShell.unavailable();document.getElementById('watch-transport').textContent"),'未知');
 fs.writeFileSync(path.join(out,'transport-result.json'),JSON.stringify({result:'PASS',layouts,errors},null,2));
 win.destroy();server.close();app.quit();
}
run().catch(e=>{fs.writeFileSync(path.join(out,'transport-failure.log'),e.stack);app.exit(1);});
