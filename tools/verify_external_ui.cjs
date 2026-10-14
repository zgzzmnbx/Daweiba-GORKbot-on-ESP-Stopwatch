/* Isolated actual Electron render. No physical device, cloud or audio. */
const path=require('node:path'),fs=require('node:fs'),http=require('node:http'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..'),staticRoot=path.join(root,'03-Src/stopwatch-voice-companion/static');
const req=require('node:module').createRequire(path.join(root,'03-Src/gork-desktop/package.json'));
const {app,BrowserWindow}=req('electron'),out=path.join(root,'04-output',process.env.GORK_UI_OUTPUT_VERSION||'v0.20.28','tests');fs.mkdirSync(out,{recursive:true});
app.setPath('userData',path.join(root,'Codex-Temp/external-ui-profile'));
const client={source:'astra',label:'智算 Astra',enabled:true,display_targets:['desktop','watch'],speech_targets:['pc','watch'],max_priority:4};
const overview={clients:[client],paused:false,pending:1,current_sound_target:'watch',current:{desktop:{source:'external:astra',expression:'working',bubble:'正在核对工作量'},watch:{source:'external:astra',expression:'working',bubble:'正在核对工作量'}},receipts:[{source:'astra',event_id:'evt1',task_id:'任务001',attempt:'attempt1',stage:'match_result',accepted_at:new Date().toISOString(),status:'partial',request:{text:'匹配完成，请复核'},delivery:{desktop:'displayed',watch:'offline',speech:'voice_session_required'}}]};
const health={version:'0.20.28-dev',external_protocol:'1.0',auto_connect_voice:false,voice:{ready:false},voice_url:'隔离预览',robot:{connected:false,enabled:false},watch_dialogue:{enabled:false,stage:'disabled',turns:[]},answer:{enabled:false},expressions:[]};
const server=http.createServer((r,s)=>{const url=new URL(r.url,'http://127.0.0.1');if(url.pathname.startsWith('/api/')){s.writeHead(200,{'Content-Type':'application/json'});s.end(JSON.stringify(url.pathname==='/api/external/overview'?overview:url.pathname==='/api/workspace'?{generation:0,voice_connected:false,robot:health.robot}:health));return;}const file=path.resolve(staticRoot,url.pathname==='/'?'index.html':url.pathname.replace(/^\/static\//,''));if(!file.startsWith(staticRoot+path.sep)||!fs.existsSync(file)||!fs.statSync(file).isFile()){s.writeHead(404);s.end();return;}s.writeHead(200,{'Content-Type':{'.js':'text/javascript','.html':'text/html','.css':'text/css','.json':'application/json'}[path.extname(file)]||'application/octet-stream'});fs.createReadStream(file).pipe(s);});
const delay=ms=>new Promise(r=>setTimeout(r,ms));
app.whenReady().then(async()=>{await new Promise(r=>server.listen(8888,'127.0.0.1',r));const win=new BrowserWindow({width:1180,height:820,show:false,webPreferences:{contextIsolation:true,nodeIntegration:false,sandbox:true,offscreen:true,backgroundThrottling:false}}),js=code=>win.webContents.executeJavaScript(code,true);const results=[],errors=[];let failed=false;
 win.webContents.on('console-message',event=>{if(event.level==='error')errors.push(event.message)});
 try{for(const theme of ['mantine','dark','classic'])for(const width of [1480,1180,800,390]){
 win.setContentSize(width,820);await win.loadURL('http://127.0.0.1:8888/#external');await delay(400);
 await js(`(()=>{const r=document.documentElement;if(r.dataset.consoleTheme!==${JSON.stringify(theme==='classic'?'classic':'mantine')})document.getElementById('theme-toggle').click();if(${theme==='dark'}!==(r.dataset.mantineColorScheme==='dark')&&${theme!=='classic'})document.getElementById('color-scheme-toggle').click();document.getElementById('external-acquire').click()})()`);await delay(200);
 for(const state of ['overview','editor','legacy','conflict']){
 client.enabled=state!=='conflict';overview.poll_source=state==='conflict'?'astra':null;
 await js("document.getElementById('external-refresh').click()");await delay(100);
 await js(`document.getElementById('external-editor').hidden=${state!=='editor'};document.getElementById('sentinel-legacy').open=${state==='legacy'};`);
 if(state==='editor')await js("document.getElementById('external-add').click();document.getElementById('external-label').value='智算 Astra';document.getElementById('external-source').value='astra';document.getElementById('external-editor').scrollIntoView({block:'center'})");
 else if(state==='legacy')await js("document.getElementById('sentinel-legacy').scrollIntoView({block:'start'})");else await js("document.getElementById('page-external').scrollTop=0");await delay(80);
 const metrics=await js("(()=>{const page=document.getElementById('page-external');return {width:innerWidth,body:document.documentElement.scrollWidth,page:page.getBoundingClientRect().toJSON(),scroll:page.scrollHeight>page.clientHeight,controls:[...page.querySelectorAll('input,select,button')].filter(e=>e.checkVisibility()).map(e=>({id:e.id,...e.getBoundingClientRect().toJSON()})),receipt:document.getElementById('external-receipts').textContent}})()");
 assert(!(await js("document.getElementById('message').textContent")).includes('控制权已失效'),'workspace fixture valid');
 assert(metrics.body<=metrics.width,'document overflow '+theme+'/'+width+'/'+state);assert(metrics.receipt.includes('匹配完成'),'receipt rendered');
 if(state==='conflict')assert(await js("document.getElementById('external-clients').textContent.includes('先关闭兼容轮询')"),'conflict guidance visible');
 for(const c of metrics.controls)assert(c.width>0&&c.left>=metrics.page.left-1&&c.right<=metrics.page.right+1,'control clipped '+theme+'/'+width+'/'+state+'/'+c.id);
 for(let i=0;i<metrics.controls.length;i++)for(let j=i+1;j<metrics.controls.length;j++){const a=metrics.controls[i],b=metrics.controls[j];assert(!(Math.min(a.right,b.right)-Math.max(a.left,b.left)>1&&Math.min(a.bottom,b.bottom)-Math.max(a.top,b.top)>1),'controls overlap '+a.id+'/'+b.id+' '+theme+'/'+width+'/'+state);}
 fs.writeFileSync(path.join(out,`external-${theme}-${width}-${state}.png`),(await win.webContents.capturePage()).toPNG());results.push({theme,width,state,scroll:metrics.scroll});
 }
 }
 assert.equal(errors.length,0,errors.join('\n'));fs.writeFileSync(path.join(out,'external-layout.json'),JSON.stringify({result:'PASS',fixture:true,physicalOutput:false,results},null,2));console.log('PASS '+results.length+' real Electron layouts');
 }catch(e){fs.writeFileSync(path.join(out,'external-layout-failure.log'),String(e.stack));console.error(e);failed=true;}finally{win.destroy();server.close();app.exit(failed?1:0);}
});
