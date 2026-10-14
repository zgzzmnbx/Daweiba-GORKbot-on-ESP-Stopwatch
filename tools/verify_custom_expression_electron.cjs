/* Actual Windows Electron acceptance, using an isolated backend and profile. */
const path=require('node:path'),fs=require('node:fs'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..'),desktop=path.join(root,'03-Src/gork-desktop');
const requireDesktop=require('node:module').createRequire(path.join(desktop,'package.json'));
const {app,BrowserWindow}=requireDesktop('electron');
const out=path.join(root,'Codex-Temp/custom-expression-electron');fs.mkdirSync(out,{recursive:true});
const port=Number(process.env.GORK_BACKEND_PORT||8880),url=`http://127.0.0.1:${port}/`;
process.env.GORK_TEST_USER_DATA=path.join(out,'profile');process.env.GORK_BACKEND_PORT=String(port);
app.commandLine.appendSwitch('force-device-scale-factor','1.5');
const errors=[];app.on('browser-window-created',(_e,win)=>win.webContents.on('console-message',(_e,level,message)=>{if(level>=3)errors.push(String(message).slice(0,200));}));
require(path.join(desktop,'main.js'));
const delay=ms=>new Promise(resolve=>setTimeout(resolve,ms));
async function until(check,timeout=10000){const start=Date.now();while(Date.now()-start<timeout){const value=await check();if(value)return value;await delay(100);}throw Error('Custom expression acceptance timeout');}
const js=(win,code)=>win.webContents.executeJavaScript(code,true);
const frame='document.getElementById("motion-editor-frame").contentWindow';
async function capture(win,name){fs.writeFileSync(path.join(out,name+'.png'),(await win.webContents.capturePage()).toPNG());}
async function run(){
 await app.whenReady();
 const consoleWindow=await until(()=>BrowserWindow.getAllWindows().find(w=>w.webContents.getURL()===url));
 const avatar=await until(()=>BrowserWindow.getAllWindows().find(w=>w.webContents.getURL().endsWith('/avatar.html')));
 await until(()=>js(consoleWindow,"Boolean(document.querySelector('[data-page-link=motion]'))"));
 await until(()=>js(avatar,"typeof face!=='undefined'&&face.getState().kind==='legacy'"));
 consoleWindow.show();await js(consoleWindow,"document.querySelector('[data-page-link=motion]').click()");
 await until(()=>js(consoleWindow,`Boolean(${frame}.gorkEditor)`));
 const initial=await js(consoleWindow,`${frame}.gorkEditor.getConfig()`);
 assert.deepEqual(initial,JSON.parse(fs.readFileSync(path.join(desktop,'motion/initial-config.gork.json'),'utf8')));
 const initialDefault=await fetch(url+'api/motion/config').then(r=>r.text());
 await js(consoleWindow,`(()=>{const w=${frame};w.gorkEditor.selectScene('writing');w.document.getElementById('expression-name').value='验收书写';w.document.getElementById('save').click();})()`);
 await until(async()=> (await js(consoleWindow,`${frame}.document.getElementById('save-status').textContent`)).includes('已加入表情菜单'));
 const itemId=await js(consoleWindow,`${frame}.gorkEditor.getEditingId()`);
 assert.match(itemId,/^motion-[0-9a-f]{12}$/);
 assert.equal(await js(avatar,'face.getState().kind'),'legacy');assert.equal(await js(avatar,'face.getConfig()'),null);
 await js(consoleWindow,"document.getElementById('expression-menu').open=true;document.getElementById('expression-mode').value='loop'");
 await until(()=>js(consoleWindow,`Boolean(document.querySelector('[data-expression="${itemId}"]'))`));
 assert.equal(await js(consoleWindow,"document.getElementById('expression-grid').children.length"),24);
 await js(consoleWindow,`document.querySelector('[data-expression="${itemId}"]').click()`);
 await until(()=>js(avatar,`face.getState().name==='${itemId}'`));
 const snapshot=await js(avatar,'face.getConfig()');assert.deepEqual(snapshot,initial);
 await delay(1200);await capture(avatar,'custom-before-edit');
 await js(consoleWindow,`(()=>{const w=${frame},c=w.gorkEditor.getConfig();c.scenes.writing.writing.x=-24;c.scenes.writing.writing.penStyle='brush';w.gorkEditor.importConfig(JSON.stringify(c));w.document.getElementById('save').click();})()`);
 await until(async()=> (await js(consoleWindow,`${frame}.document.getElementById('save-status').textContent`)).includes('已加入表情菜单'));
 await delay(1300);assert.deepEqual(await js(avatar,'face.getConfig()'),snapshot,'saving must retain the playing snapshot');
 assert.equal(await fetch(url+'api/motion/config').then(r=>r.text()),initialDefault,'built-in/default parameter file must stay unchanged');
 await js(consoleWindow,`document.querySelector('[data-expression="${itemId}"]').click()`);
 await until(async()=> (await js(avatar,'face.getConfig()'))?.scenes.writing.writing.penStyle==='brush');
 await delay(1000);await capture(avatar,'custom-after-explicit-replay');
 // Save as a new named expression, then select and load the previous expression.
 await js(consoleWindow,`(()=>{const w=${frame};w.document.getElementById('expression-name').value='验收疑惑';w.gorkEditor.selectScene('question');w.document.getElementById('save-as-new').click();})()`);
 await until(async()=> (await js(consoleWindow,`${frame}.document.getElementById('custom-expression').options.length`))===3);
 const secondId=await js(consoleWindow,`${frame}.gorkEditor.getEditingId()`);assert.notEqual(secondId,itemId);
 await js(consoleWindow,`(()=>{const w=${frame},s=w.document.getElementById('custom-expression');s.value='${itemId}';s.dispatchEvent(new w.Event('change',{bubbles:true}));})()`);
 assert.equal(await js(consoleWindow,`${frame}.document.getElementById('expression-name').value`),'验收书写');
 assert.equal((await js(consoleWindow,`${frame}.gorkEditor.getConfig()`)).scenes.writing.writing.penStyle,'brush');
 await until(()=>js(consoleWindow,"document.getElementById('expression-grid').children.length===25"));
 // Without changing its name, Save As creates a new copy and leaves the original intact.
 await js(consoleWindow,`${frame}.document.getElementById('save-as-new').click()`);
 await until(()=>js(consoleWindow,`${frame}.document.getElementById('custom-expression').options.length===4`));
 const thirdId=await js(consoleWindow,`${frame}.gorkEditor.getEditingId()`);assert.notEqual(thirdId,itemId);assert.notEqual(thirdId,secondId);
 assert.equal(await js(consoleWindow,`${frame}.document.getElementById('expression-name').value`),'验收书写 副本1');
 await until(()=>js(consoleWindow,"document.getElementById('expression-grid').children.length===26"));
 await js(consoleWindow,"document.querySelector('[data-expression=idle]').click()");
 await until(()=>js(avatar,"face.getState().kind==='legacy'&&face.getState().name==='idle'"));
 assert.equal(await js(avatar,'face.getConfig()'),null);
 // Renderer reload and editor reopen do not replace original idle or lose named entries.
 avatar.webContents.reload();await until(()=>js(avatar,"typeof face!=='undefined'&&face.getState().kind==='legacy'"));
 await js(consoleWindow,"location.hash='#dialogue'");await until(()=>js(consoleWindow,"!document.getElementById('motion-editor-frame').getAttribute('src')"));
 await js(consoleWindow,"location.hash='#motion'");await until(()=>js(consoleWindow,`Boolean(${frame}.gorkEditor)&&${frame}.document.getElementById('custom-expression').options.length===4`));
 await js(consoleWindow,`(()=>{const w=${frame},s=w.document.getElementById('custom-expression');s.value='${itemId}';s.dispatchEvent(new w.Event('change',{bubbles:true}));})()`);
 assert.equal(await js(consoleWindow,`${frame}.document.getElementById('expression-name').value`),'验收书写');
 await delay(300);await capture(consoleWindow,'console-custom-editor');
 const layout=await js(consoleWindow,`({width:innerWidth,scroll:document.documentElement.scrollWidth,dpr:devicePixelRatio,iframe:${frame}.innerWidth})`);
 assert(layout.scroll<=layout.width+1);
 consoleWindow.setSize(820,650);await delay(300);await capture(consoleWindow,'console-820x650');
 const narrow=await js(consoleWindow,`({width:innerWidth,scroll:document.documentElement.scrollWidth,iframeWidth:${frame}.innerWidth,iframeScroll:${frame}.document.documentElement.scrollWidth})`);
 assert(narrow.scroll<=narrow.width+1);assert(narrow.iframeScroll<=narrow.iframeWidth+1,'editor horizontal overflow');
 assert.deepEqual(errors,[]);
 fs.writeFileSync(path.join(out,'result.json'),JSON.stringify({result:'PASS',version:requireDesktop('./package.json').version,checks:['original defaults preserved','create named expression in menu','explicit click playback ACK','edit existing expression saves without active snapshot change','explicit replay uses saved edit','save-as-new retains both entries','save-as-new without renaming creates a third automatic copy','select existing entry restores parameters','built-in idle returns to original renderer','renderer reload and editor reopen','150 percent DPI and 820x650 layout'],layout,narrow,itemIds:[itemId,secondId,thirdId],consoleErrors:errors},null,2));
 console.log('PASS actual Windows Electron: named create/select/edit/save-as-new/menu/playback ACK; default and active snapshot isolation; renderer reload; editor reopen; layouts.');app.quit();
}
run().catch(error=>{fs.writeFileSync(path.join(out,'failure.log'),String(error.stack));console.error(error);app.exit(1);});
