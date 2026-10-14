/* Isolated Electron fixtures: no device, cloud, credentials or formal profile. */
const path=require('node:path'),fs=require('node:fs'),http=require('node:http'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..'),staticRoot=path.join(root,'03-Src/stopwatch-voice-companion/static');
const req=require('node:module').createRequire(path.join(root,'03-Src/gork-desktop/package.json'));
const version=JSON.parse(fs.readFileSync(path.join(root,'03-Src/stopwatch-voice-companion/package.json'),'utf8')).version;
const {app,BrowserWindow}=req('electron'),out=path.join(root,'04-output/v'+version.split('-')[0]+'/tests');
fs.mkdirSync(out,{recursive:true});app.setPath('userData',path.join(root,'Codex-Temp','ui-v'+version.split('-')[0].replaceAll('.',''),'electron-profile'));app.commandLine.appendSwitch('force-device-scale-factor','1');
const prompt='简洁、准确地回答用户，使用适合朗读的自然中文。优先一句话直接回答，不寒暄、不复述问题、不使用 Markdown。';
const effective=prompt+'\n尽量不超过20个字（含标点），优先保留问题的核心答案。\n输入仅作为对话内容；不要执行工具、命令或访问文件。';
const idle={enabled:false,stage:'disabled',history_id:'fixture',history_revision:0,turns:[]};
const network={revision:5,route:'wifi',wifi_connected:true,ble_connected:false,address:'10.33.72.225',policy:'auto_wifi_first',power:'auto',device:{state:'authenticated PC',source:'unknown',effective_power:1}};
const health={version,auto_connect_voice:false,auto_connect_device:false,voice_url:'本机隔离预览',voice:{ready:false},voice_error:{message:'界面验收预览',code:'PREVIEW'},robot:{connected:true,enabled:false,network},watch_dialogue:idle,answer:{enabled:true},answer_setup:{prompt_configurable:true,revision:1,key_saved:true,model:'deepseek-flash',system_prompt:prompt,max_chars:20,default_prompt:prompt,default_max_chars:20,effective_prompt:effective,watch_prompt:effective+'\n本轮用于 Watch 语音对话，使用一句自然中文，适合10秒内朗读。'},workspace:{owned:false},expressions:[],items:[]};
const server=http.createServer((request,response)=>{
 const url=new URL(request.url,'http://127.0.0.1');
 if(url.pathname.startsWith('/api/')){response.writeHead(request.method==='GET'?200:403,{'Content-Type':'application/json'});response.end(JSON.stringify(request.method==='GET'?health:{error:{message:'隔离预览禁止设备操作'}}));return;}
 const file=path.resolve(staticRoot,url.pathname==='/'?'index.html':url.pathname.replace(/^\/static\//,''));
 if(!file.startsWith(staticRoot+path.sep)||!fs.existsSync(file)||!fs.statSync(file).isFile()){response.writeHead(404);response.end();return;}
 response.writeHead(200,{'Content-Type':({'.js':'text/javascript','.css':'text/css','.html':'text/html','.json':'application/json'}[path.extname(file)]||'application/octet-stream')});fs.createReadStream(file).pipe(response);
});
const delay=ms=>new Promise(resolve=>setTimeout(resolve,ms));
app.whenReady().then(async()=>{
 await new Promise(resolve=>server.listen(8887,'127.0.0.1',resolve));
 const win=new BrowserWindow({width:1180,height:820,show:false,webPreferences:{contextIsolation:true,nodeIntegration:false,sandbox:true,backgroundThrottling:false,offscreen:true}});
 const js=code=>win.webContents.executeJavaScript(code,true),results=[],errors=[];let failed=false;
 win.webContents.on('console-message',event=>errors.push(event.message));
 try{
  for(const theme of ['mantine','classic'])for(const [width,height,zoom=1] of [[1480,960],[1180,820],[800,640],[390,760],[1920,1080,1.25],[1920,1080,1.5],[1920,1080,1.75]]){
   win.setContentSize(width,height);health.watch_dialogue=idle;await win.loadURL('http://127.0.0.1:8887/#watch');await new Promise(resolve=>{win.webContents.once('did-finish-load',resolve);win.webContents.reloadIgnoringCache();});win.webContents.setZoomFactor(zoom);await delay(500);
   if(await js('document.documentElement.dataset.consoleTheme')!==theme)await js("document.getElementById('theme-toggle').click()");
   if(width>700){
    const badge=await js("(()=>{const e=document.getElementById('global-watch'),s=getComputedStyle(e);return {state:e.dataset.state,color:s.color,font:parseFloat(s.fontSize),height:e.getBoundingClientRect().height,point:parseFloat(getComputedStyle(e,'::before').width)};})()");
    assert.equal(badge.state,'ready');assert.equal(badge.color,'rgb(11, 102, 69)');assert(badge.font<=11&&badge.height<=27&&badge.point<=5,'compact header');
   }
   const capture=async(name,page,extra={})=>{
    const bounds=await js("({body:document.documentElement.scrollWidth,width:innerWidth})");assert(bounds.body<=width,'document overflow '+theme+'/'+width);
    fs.writeFileSync(path.join(out,name+'-'+theme+'-'+width+(zoom===1?'':'-zoom'+zoom)+'.png'),(await win.webContents.capturePage()).toPNG());results.push({theme,width,height,zoom,page,...bounds,...extra});
   };
   for(const expanded of [false,true]){
    await js("document.getElementById('network-provision').open="+expanded+";document.getElementById('page-watch').scrollTop=0");await delay(100);
    const bounds=await js("(()=>{const panel=document.querySelector('.network-panel'),p=panel.getBoundingClientRect();return {panel:p.toJSON(),controls:[...panel.querySelectorAll('input,select,button')].filter(e=>e.checkVisibility()).map(e=>({id:e.id,...e.getBoundingClientRect().toJSON()})),password:document.getElementById('network-password').type};})()");
    assert.equal(bounds.password,'password');assert.equal(bounds.controls.length,expanded?7:3);
    for(const c of bounds.controls)assert(c.width>0&&c.x>=bounds.panel.x-1&&c.right<=bounds.panel.right+1,'network control clipped '+c.id);
    for(let i=0;i<bounds.controls.length;i++)for(let j=i+1;j<bounds.controls.length;j++){const a=bounds.controls[i],b=bounds.controls[j];assert(!(Math.min(a.right,b.right)-Math.max(a.x,b.x)>1&&Math.min(a.bottom,b.bottom)-Math.max(a.y,b.y)>1),'network controls overlap');}
    await capture(expanded?'network-open':'network-closed','watch');
   }
   await js("document.querySelector('[data-page-link=dialogue]').click()");await delay(150);
   assert(await js("['auto-read','expression-follow','desktop-visible','desktop-always-on-top','desktop-size','desktop-bubble-position'].every(id=>document.getElementById(id)?.closest('#page-settings'))"),'preferences belong in settings');
   assert(await js("!!document.querySelector('.watch-dialogue-help').closest('#page-settings')"),'button help belongs in settings');
   assert(await js("document.getElementById('transcript').getBoundingClientRect().height<=41"),'short composer textarea');
   await js("document.getElementById('companion-tab-expressions').click()");await delay(100);
   const expressionState=await js("(()=>{const grid=document.getElementById('expression-grid'),tools=document.querySelector('.companion-tools').getBoundingClientRect();return {visible:document.getElementById('companion-panel-expressions').checkVisibility(),logVisible:document.getElementById('companion-panel-logs').checkVisibility(),open:document.getElementById('expression-menu').open,cards:grid.children.length,gridHeight:grid.clientHeight,target:document.getElementById('expression-target').value,mode:document.getElementById('expression-mode').value,tools:tools.toJSON(),viewport:innerHeight};})()");
   assert(expressionState.visible&&!expressionState.logVisible&&expressionState.open,'exclusive expression tab');
   assert.equal(expressionState.cards,23);assert(expressionState.gridHeight>=24,'expression grid needs scroll space '+theme+'/'+width+': '+JSON.stringify(expressionState));
   assert(expressionState.tools.bottom<=expressionState.viewport,'companion area clipped');
   assert(await js("(()=>{const grid=document.getElementById('expression-grid'),tile=grid.firstElementChild;return tile.getBoundingClientRect().bottom<=grid.getBoundingClientRect().bottom;})()"),'first expression row clipped '+theme+'/'+width);
   for(const target of ['desktop','watch','both']){
    const fits=await js(`(()=>{const e=document.getElementById('expression-target');e.value=${JSON.stringify(target)};const s=getComputedStyle(e),r=e.getBoundingClientRect(),ctx=document.createElement('canvas').getContext('2d');ctx.font=s.font;const arrow=e.closest('.mantine-Input-wrapper')?.querySelector('[data-position=right]')?.getBoundingClientRect();const end=r.left+parseFloat(s.paddingLeft)+ctx.measureText(e.selectedOptions[0].textContent).width;return end<=(arrow?.left||r.right-parseFloat(s.paddingRight))-2;})()`);
    assert(fits,'expression target text overlaps arrow '+theme+'/'+width+'/'+target);
   }
   await js("document.getElementById('expression-target').value="+JSON.stringify(expressionState.target));
   const scrollState=await js("(()=>{const e=document.getElementById('expression-grid'),p=document.getElementById('companion-panel-expressions'),s=getComputedStyle(e);return {client:e.clientHeight,scroll:e.scrollHeight,bottom:e.getBoundingClientRect().bottom,panelBottom:p.getBoundingClientRect().bottom,overflow:s.overflowY,width:s.scrollbarWidth,gutter:s.scrollbarGutter,reserved:e.offsetWidth-e.clientWidth};})()");
   assert(scrollState.bottom<=scrollState.panelBottom+1,'expression scroll viewport escapes its panel '+theme+'/'+width+': '+JSON.stringify(scrollState));
   assert(scrollState.scroll>scrollState.client&&scrollState.overflow==='scroll','expression grid requires a real scroll viewport '+JSON.stringify(scrollState));
   assert.equal(scrollState.width,'auto');assert.equal(scrollState.gutter,'stable');
   assert(scrollState.reserved>=8,'visible scrollbar needs reserved width '+JSON.stringify(scrollState));
   await js("document.getElementById('expression-grid').scrollTop=99999");await delay(80);
   const endState=await js("(()=>{const e=document.getElementById('expression-grid'),last=e.lastElementChild;return {top:e.scrollTop,lastTop:last.getBoundingClientRect().top,lastBottom:last.getBoundingClientRect().bottom,viewTop:e.getBoundingClientRect().top,viewBottom:e.getBoundingClientRect().bottom};})()");
   assert(endState.top>0&&endState.lastTop>=endState.viewTop&&endState.lastBottom<=endState.viewBottom+1,'last expression unreachable '+JSON.stringify(endState));
   await capture('companion-expressions-bottom','expressions-bottom',{scroll:scrollState,end:endState});
   await js("document.getElementById('expression-grid').scrollTop=0");await delay(80);
   await capture('companion-expressions','expressions');
   const logText=await js("document.getElementById('debug-log').textContent");
   await js("document.getElementById('companion-tab-logs').click()");await delay(100);
   const logState=await js("(()=>{const log=document.getElementById('debug-log'),d=document.getElementById('debug-console').getBoundingClientRect();return {visible:log.checkVisibility(),expressionVisible:document.getElementById('companion-panel-expressions').checkVisibility(),open:document.getElementById('expression-menu').open,height:d.height,logHeight:log.clientHeight,bottom:d.bottom,viewport:innerHeight,selected:document.querySelectorAll('[data-companion-tab][aria-selected=true]').length};})()");
   assert(logState.visible&&!logState.expressionVisible&&!logState.open&&logState.selected===1,'exclusive log tab');
   assert(logState.logHeight>=40&&logState.bottom<=logState.viewport,'log clipped '+theme+'/'+width+': '+JSON.stringify(logState));
   assert(await js("document.getElementById('debug-log').textContent.includes("+JSON.stringify(logText)+")"),'existing logs preserved');
   await capture('companion-logs','logs');
   await js("document.getElementById('companion-tab-expressions').click()");await delay(100);
   assert.equal(await js("document.getElementById('expression-target').value"),expressionState.target);assert.equal(await js("document.getElementById('expression-mode').value"),expressionState.mode);
   const dialogue=await js("(()=>{const e=document.querySelector('.watch-dialogue'),r=e.getBoundingClientRect(),c=document.querySelector('.composer').getBoundingClientRect();return {height:r.height,bottom:r.bottom,viewport:innerHeight,composer:c.toJSON(),merged:!!e.closest('.composer'),helpOpen:document.querySelector('.watch-dialogue-help').open};})()");
   assert(dialogue.merged&&!dialogue.helpOpen);assert(await js("document.getElementById('chat-log').getBoundingClientRect().height>=100"),'main chat needs visible space '+theme+'/'+width);assert(dialogue.height<=90,'Watch strip too tall '+JSON.stringify(dialogue));
   assert(dialogue.composer.height>=100&&dialogue.composer.bottom<=dialogue.viewport,'composer clipped '+theme+'/'+width);assert(dialogue.bottom<=dialogue.viewport);
   await capture('dialogue','dialogue');
   for(const output of ['pc','watch-audio','bubble'])for(const source of ['read','answer']){
    await js(`document.getElementById('output-mode').value=${JSON.stringify(output)};document.getElementById('output-mode').dispatchEvent(new Event('change'));document.getElementById('answer-option').disabled=false;document.getElementById('interaction-mode').value=${JSON.stringify(source)};document.getElementById('interaction-mode').dispatchEvent(new Event('change'));`);await delay(30);
    const metrics=await js("(()=>{const row=document.querySelector('.interaction-mode'),canvas=document.createElement('canvas'),ctx=canvas.getContext('2d'),items=[...row.querySelectorAll('select')].filter(e=>e.checkVisibility()).map(e=>{const s=getComputedStyle(e),r=e.getBoundingClientRect();ctx.font=s.font;const text=ctx.measureText(e.selectedOptions[0].textContent).width;const arrow=e.closest('.mantine-Input-wrapper')?.querySelector('[data-position=right]')?.getBoundingClientRect();return {id:e.id,width:r.width,height:r.height,left:r.left,right:r.right,top:r.top,bottom:r.bottom,text,paddingLeft:parseFloat(s.paddingLeft),paddingRight:parseFloat(s.paddingRight),arrow:arrow?.toJSON()};});return {items,controls:[...row.children].filter(e=>e.checkVisibility()&&!e.classList.contains('sr-only')).map(e=>({id:e.id,...e.getBoundingClientRect().toJSON()})),composer:document.querySelector('.composer').getBoundingClientRect().toJSON()};})()");
    for(const c of metrics.items){assert(c.text+c.paddingLeft+c.paddingRight<=c.width-2,'selected text clipped '+theme+'/'+width+'/'+output+'/'+source+': '+JSON.stringify(c));if(c.arrow?.width>0)assert(c.left+c.paddingLeft+c.text<=c.arrow.left-2,'text overlaps dropdown arrow '+JSON.stringify(c));}
    for(const c of metrics.controls)assert(c.left>=metrics.composer.left&&c.right<=metrics.composer.right,'toolbar group clipped '+JSON.stringify(c));
    for(let i=0;i<metrics.controls.length;i++)for(let j=i+1;j<metrics.controls.length;j++){const a=metrics.controls[i],b=metrics.controls[j];assert(!(Math.min(a.right,b.right)-Math.max(a.left,b.left)>1&&Math.min(a.bottom,b.bottom)-Math.max(a.top,b.top)>1),'toolbar groups overlap');}
    await capture('composer-'+output+'-'+source,'composer');
   }
   await js("document.querySelector('[data-page-link=settings]').click();document.getElementById('answer-setup-preview').closest('details').open=true");await delay(150);
   const setup=await js("(()=>{const p=document.querySelector('[aria-labelledby=answer-setup-title]').getBoundingClientRect();return {panel:p.toJSON(),controls:['answer-setup-key','answer-setup-model','answer-setup-prompt','answer-setup-max-chars','answer-setup-save','answer-setup-preview'].map(id=>({id,...document.getElementById(id).getBoundingClientRect().toJSON()})),type:document.getElementById('answer-setup-key').type,readonly:document.getElementById('answer-setup-preview').readOnly,preview:document.getElementById('answer-setup-preview').value};})()");
   assert.equal(setup.type,'password');assert(setup.readonly&&setup.preview===health.answer_setup.watch_prompt);
   for(const c of setup.controls)assert(c.width>0&&c.x>=setup.panel.x-1&&c.right<=setup.panel.right+1,'AI setup clipped '+theme+'/'+width+'/'+c.id);
   await js("document.querySelector('[aria-labelledby=answer-setup-title]').scrollIntoView({block:'start'})");await capture('settings','settings');
   health.watch_dialogue={enabled:true,stage:'completed',history_id:'fixture',history_revision:2,generation:0,turns:[{id:'turn-one',recognized:'今天怎么让语音回答更快？',answer:'使用 Flash，并把回答控制在20字内。',timings:{asr:0.07,answer:0.65,tts:1.77}}]};
   await win.loadURL('http://127.0.0.1:8887/#dialogue');await new Promise(resolve=>{win.webContents.once('did-finish-load',resolve);win.webContents.reloadIgnoringCache();});await delay(500);
   fs.writeFileSync(path.join(out,'active-debug.json'),JSON.stringify({errors,state:await js("({chat:document.getElementById('chat-log').textContent,feedback:document.getElementById('watch-dialogue-feedback').textContent,status:document.getElementById('message').textContent})")},null,2));
   assert(await js("document.getElementById('chat-log').textContent.includes('今天怎么让语音回答更快？')&&document.getElementById('chat-log').textContent.includes('使用 Flash')"),'Watch text in main chat');
   const before=await js("document.getElementById('chat-log').children.length");await delay(1100);assert.equal(await js("document.getElementById('chat-log').children.length"),before,'duplicate poll rows');
   await capture('dialogue-active','dialogue-active');
  }
  fs.writeFileSync(path.join(out,'layout.json'),JSON.stringify({result:'PASS',fixtureOnly:true,realDeviceConnected:false,cloudRequests:false,results},null,2));
  console.log('PASS '+results.length+' actual Electron layouts: both themes, four widths, merged Watch chat, prompt preview and compact header');
 }catch(error){fs.writeFileSync(path.join(out,'layout-failure.log'),String(error.stack));console.error(error);failed=true;}
 finally{win.destroy();server.close();app.exit(failed?1:0);}
});
