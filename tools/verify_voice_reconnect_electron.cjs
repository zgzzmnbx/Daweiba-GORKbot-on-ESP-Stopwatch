/* Real generated console with its production modules; isolated HTTP and profile. */
const fs=require('node:fs'),path=require('node:path'),http=require('node:http'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..'),desktop=path.join(root,'03-Src/gork-desktop');
const {app,BrowserWindow}=require('node:module').createRequire(path.join(desktop,'package.json'))('electron');
const out=path.join(root,'Codex-Temp/voice-reconnect-20261014/electron');fs.mkdirSync(out,{recursive:true});
app.setPath('userData',path.join(out,'profile-'+Date.now()));
const web=path.join(root,'03-Src/stopwatch-voice-companion/static');
let outage=false,busy=false,session=false,generation=0;
const requests=[],errors=[];
const server=http.createServer(async(request,response)=>{
  const url=new URL(request.url,'http://localhost').pathname;
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
    if(url==='/api/health')return reply({version:'0.20.35-dev',auto_connect_voice:true,
      watch_dialogue:{enabled:false,stage:'disabled'},voice:{ready:!outage},
      ...(outage?{voice_error:{code:'VOICE_OFFLINE',message:'隔离断线测试'}}:{}),
      voice_service:{mode:'external',configured:false},voice_url:'fixture',robot:{connected:false},answer:{enabled:false},
      capabilities:{protocol_version:1,tts:{speakers:[{id:58,label:'Local 58'}]},cloud:{request_voice:true,voices:[{id:'Ethan',label:'Ethan'},{id:'Cherry',label:'Cherry'}]}}});
    if(url==='/api/motion/expressions')return reply({revision:1,entries:[]});
    if(url==='/api/character/voice-library')return reply({items:[],enabled:false});
    if(url==='/api/cost/sentinel'||url==='/api/codex/sentinel')return reply({enabled:false,history:[],threads:[],quota:{buckets:{}}});
    return reply({generation,robot:{connected:false}});
  }
  const file=path.resolve(web,url==='/'?'index.html':decodeURIComponent(url.replace(/^\/static\//,'')));
  if(!file.startsWith(web+path.sep)||!fs.existsSync(file)){response.writeHead(404);response.end();return;}
  response.writeHead(200,{'Content-Type':({'.html':'text/html','.js':'text/javascript','.css':'text/css','.json':'application/json'})[path.extname(file)]||'application/octet-stream'});fs.createReadStream(file).pipe(response);
});
const delay=ms=>new Promise(resolve=>setTimeout(resolve,ms));
async function until(check){for(let i=0;i<120;i++){if(await check())return;await delay(100);}throw Error('Connection acceptance timeout');}
const posts=()=>requests.filter(r=>r.url==='/api/session'&&r.method==='POST');
async function run(){
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));await app.whenReady();
  const win=new BrowserWindow({width:1180,height:820,show:true,webPreferences:{contextIsolation:true,nodeIntegration:false,sandbox:true}});
  win.webContents.on('console-message',details=>{if(details.level==='error')errors.push(details.message);});
  const js=code=>win.webContents.executeJavaScript(code,true);
  const connected=()=>js("document.getElementById('quick-connect')?.textContent==='语音已连接'");
  await win.loadURL(`http://127.0.0.1:${server.address().port}/init`);
  await until(connected);assert.equal(posts().length,1);
  fs.writeFileSync(path.join(out,'startup-connected.png'),(await win.webContents.capturePage()).toPNG());
  outage=true;session=false;
  await until(()=>js("document.getElementById('global-voice').textContent.includes('等待重连')"));
  fs.writeFileSync(path.join(out,'waiting-reconnect.png'),(await win.webContents.capturePage()).toPNG());
  outage=false;await until(connected);assert.equal(posts().length,2);
  fs.writeFileSync(path.join(out,'reconnected.png'),(await win.webContents.capturePage()).toPNG());
  const setting=requests.filter(r=>r.url==='/api/settings').at(-1).body;
  assert.equal(setting.speech.cloud_voice,'Ethan');assert.equal(setting.routing.allow_audio_upload,false);assert.equal(setting.allow_answer_upload,false);
  assert(posts().every(r=>r.body.replace===false));
  await js("document.getElementById('release').click()");await until(()=>!session);
  const count=posts().length;await delay(5500);assert.equal(posts().length,count);
  busy=true;await js("document.getElementById('quick-connect').click()");
  await until(()=>js("!document.getElementById('takeover').hidden"));const busyCount=posts().length;
  await delay(1300);assert.equal(posts().length,busyCount);
  assert(!requests.some(r=>/\/api\/(asr|tts|answer)$|\/api\/device.*\/(record|play|speech)/.test(r.url)));
  assert.deepEqual(errors,[]);
  fs.writeFileSync(path.join(out,'result.json'),JSON.stringify({result:'PASS',version:'0.20.35-dev',
    checks:['real production modules auto-connect at startup','real periodic heartbeat detects loss','automatic non-takeover recovery',
      'tone and revoked consent retained','manual release stays disconnected','busy owner remains paused','no synthesis/recognition/device playback'],
    sessionPosts:posts().length,settings:setting,errors},null,2));
  app.quit();
}
run().catch(error=>{fs.writeFileSync(path.join(out,'failure.log'),String(error.stack));process.exitCode=1;app.quit();});
app.on('will-quit',()=>{server.closeAllConnections();server.close();});
