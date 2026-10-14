/* Real Windows editor -> independent library -> desktop playback -> Watch export,
 * using an isolated port/profile and no physical device connection. */
const path=require('node:path'),fs=require('node:fs'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..'),desktop=path.join(root,'03-Src/gork-desktop');
const req=require('node:module').createRequire(path.join(desktop,'package.json')),{app,BrowserWindow}=req('electron');
const out=path.join(root,'Codex-Temp/motion-range-electron');fs.mkdirSync(out,{recursive:true});
const port=Number(process.env.GORK_BACKEND_PORT||8884),url=`http://127.0.0.1:${port}/`;
process.env.GORK_TEST_USER_DATA=path.join(out,'profile');process.env.GORK_BACKEND_PORT=String(port);
const errors=[];app.on('browser-window-created',(_e,win)=>win.webContents.on('console-message',(_e,level,message)=>{if(level>=3)errors.push(String(message).slice(0,180));}));
require(path.join(desktop,'main.js'));
const delay=ms=>new Promise(resolve=>setTimeout(resolve,ms)),js=(w,code)=>w.webContents.executeJavaScript(code,true);
async function until(check){for(let n=0;n<100;n++){const value=await check();if(value)return value;await delay(100);}throw Error('Range acceptance timeout');}
const frame='document.getElementById("motion-editor-frame").contentWindow',values={x:120,y:-60,scale:1.8,penScale:2.5,strokeWidth:9};
async function run(){
 await app.whenReady();
 const consoleWindow=await until(()=>BrowserWindow.getAllWindows().find(w=>w.webContents.getURL()===url));
 const avatar=await until(()=>BrowserWindow.getAllWindows().find(w=>w.webContents.getURL().endsWith('/avatar.html')));
 await until(()=>js(consoleWindow,"Boolean(document.querySelector('[data-page-link=motion]'))"));
 consoleWindow.show();await js(consoleWindow,"document.querySelector('[data-page-link=motion]').click()");
 await until(()=>js(consoleWindow,`Boolean(${frame}.gorkEditor)`));
 const original=await fetch(url+'api/motion/config').then(r=>r.text());
 await js(consoleWindow,`(()=>{const w=${frame};w.gorkEditor.selectScene('writing');for(const [key,value]of Object.entries(${JSON.stringify(values)})){const el=w.document.getElementById('writing-'+key);assertRange(el,value);el.value=String(value);el.dispatchEvent(new w.Event('change',{bubbles:true}));}function assertRange(el,value){if(!el||value<Number(el.min)||value>Number(el.max))throw Error('Expanded UI range missing');}w.document.getElementById('expression-name').value='范围验收';w.document.getElementById('save').click();})()`);
 await until(()=>js(consoleWindow,`${frame}.gorkEditor.getEditingId()`));
 const id=await js(consoleWindow,`${frame}.gorkEditor.getEditingId()`);
 const record=await fetch(url+'api/motion/expressions/'+id).then(r=>r.json());
 for(const [key,value]of Object.entries(values))assert.equal(record.config.scenes.writing.writing[key],value);
 assert.equal(await fetch(url+'api/motion/config').then(r=>r.text()),original);
 await js(consoleWindow,"document.getElementById('expression-menu').open=true;document.getElementById('expression-mode').value='loop'");
 await until(()=>js(consoleWindow,`Boolean(document.querySelector('[data-expression="${id}"]'))`));
 await js(consoleWindow,`document.querySelector('[data-expression="${id}"]').click()`);
 await until(()=>js(avatar,`face.getState().name==='${id}'`));
 assert.deepEqual((await js(avatar,'face.getConfig()')).scenes.writing.writing,record.config.scenes.writing.writing);
 await delay(1700);const first=(await avatar.webContents.capturePage()).toPNG();await delay(600);const second=(await avatar.webContents.capturePage()).toPNG();assert(!first.equals(second),'expanded animation must move');
 consoleWindow.reload();await until(()=>js(consoleWindow,"Boolean(document.querySelector('[data-page-link=motion]'))"));
 await js(consoleWindow,"document.querySelector('[data-page-link=motion]').click()");await until(()=>js(consoleWindow,`Boolean(${frame}.gorkEditor)`));
 await js(consoleWindow,`(()=>{const w=${frame},el=w.document.getElementById('custom-expression');el.value='${id}';el.dispatchEvent(new w.Event('change'));})()`);
 const restored=await js(consoleWindow,`${frame}.gorkEditor.getConfig().scenes.writing.writing`);assert.deepEqual(restored,record.config.scenes.writing.writing);
 const watch=await fetch(url+'api/motion/watch/json?expression_id='+id).then(r=>r.json());assert.deepEqual(watch.scenes[2].props.slice(0,5),Object.values(values));
 fs.writeFileSync(path.join(out,'editor-expanded.png'),(await consoleWindow.webContents.capturePage()).toPNG());fs.writeFileSync(path.join(out,'desktop-expanded.png'),second);
 assert.deepEqual(errors,[]);fs.writeFileSync(path.join(out,'result.json'),JSON.stringify({result:'PASS',version:req('./package.json').version,values,restored,desktopPixelsChanged:true,defaultConfigUnchanged:true,watchValues:watch.scenes[2].props.slice(0,5),consoleErrors:errors},null,2));
}
run().catch(error=>{fs.writeFileSync(path.join(out,'failure.log'),String(error.stack||error));process.exitCode=1;}).finally(()=>app.quit());
