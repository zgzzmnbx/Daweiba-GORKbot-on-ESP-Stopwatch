/* Real Electron pixel/time acceptance under OS reduced-motion; isolated only. */
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..'),desktop=path.join(root,'03-Src/gork-desktop');
const {app,BrowserWindow}=require('node:module').createRequire(path.join(desktop,'package.json'))('electron');
const out=path.join(root,'Codex-Temp/custom-motion-playback');fs.mkdirSync(out,{recursive:true});
const port=Number(process.env.GORK_BACKEND_PORT||8882),url=`http://127.0.0.1:${port}/`;
process.env.GORK_TEST_USER_DATA=path.join(out,'profile');process.env.GORK_BACKEND_PORT=String(port);
require(path.join(desktop,'main.js'));
const delay=ms=>new Promise(r=>setTimeout(r,ms)),js=(win,code)=>win.webContents.executeJavaScript(code,true);
async function until(check){const start=Date.now();while(Date.now()-start<10000){try{const v=await check();if(v)return v;}catch{}await delay(100);}throw Error('Playback acceptance timeout');}
async function run(){
 await app.whenReady();
 const consoleWindow=await until(()=>BrowserWindow.getAllWindows().find(w=>w.webContents.getURL()===url));
 const avatar=await until(()=>BrowserWindow.getAllWindows().find(w=>w.webContents.getURL().endsWith('/avatar.html')));
 await until(()=>js(consoleWindow,"document.getElementById('expression-menu')!==null"));
 consoleWindow.show();
 for(const win of [consoleWindow,avatar]){win.webContents.debugger.attach('1.3');await win.webContents.debugger.sendCommand('Emulation.setEmulatedMedia',{features:[{name:'prefers-reduced-motion',value:'reduce'}]});}
 const config=JSON.parse(fs.readFileSync(path.join(desktop,'motion/initial-config.gork.json'),'utf8'));
 const library=await fetch(url+'api/motion/expressions').then(r=>r.json());
 const saved=await fetch(url+'api/motion/expressions',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({expected_revision:library.revision,name:'动画实测'+library.revision,scene:'question',config})}).then(r=>r.json());
 const id=saved.entry.id;
 consoleWindow.webContents.reload();await until(()=>js(consoleWindow,"document.getElementById('expression-menu')!==null"));
 await js(avatar,"window.customMounts=0;window.originalCustomPlay=face.playCustom;face.playCustom=(...args)=>{window.customMounts++;return window.originalCustomPlay(...args);};true");
 await js(consoleWindow,`(()=>{document.getElementById('expression-menu').open=true;document.getElementById('expression-mode').value='loop';})()`);
 await until(()=>js(consoleWindow,`Boolean(document.querySelector('[data-expression="${id}"]'))`));
 await js(consoleWindow,`document.querySelector('[data-expression="${id}"]').click()`);
 await until(()=>js(avatar,`face.getState().name==='${id}'`));
 const reduced=await js(avatar,"matchMedia('(prefers-reduced-motion: reduce)').matches"),start=await js(avatar,'face.getState()');
 await delay(1100);
 const first=await js(avatar,'({state:face.getState(),pixels:document.getElementById("gork-face").toDataURL(),mounts:window.customMounts})');
 await delay(500);
 const second=await js(avatar,'({state:face.getState(),pixels:document.getElementById("gork-face").toDataURL(),mounts:window.customMounts})');
 const web=await js(consoleWindow,'({pixels:document.getElementById("gork-face").toDataURL()})');await delay(500);
 const webNext=await js(consoleWindow,'({pixels:document.getElementById("gork-face").toDataURL()})');
 const evidence={systemReduced:reduced,start,first:first.state,second:second.state,mounts:second.mounts,desktopPixelsChanged:first.pixels!==second.pixels,consolePixelsChanged:web.pixels!==webNext.pixels};
 fs.writeFileSync(path.join(out,'evidence.json'),JSON.stringify(evidence,null,2));
 assert.equal(reduced,true);assert.equal(first.state.reducedMotion,false,'explicit playback must move even when the OS requests reduced motion');
 assert.equal(second.mounts,1,'renderer ACK/shared-state echo must not replay the same command');
 assert(second.state.elapsed>first.state.elapsed);assert.notEqual(first.pixels,second.pixels,'desktop pixels must animate');assert.notEqual(web.pixels,webNext.pixels,'console pixels must animate');
 fs.writeFileSync(path.join(out,'avatar-moving.png'),(await avatar.webContents.capturePage()).toPNG());
 // Once must animate, then return to the original idle; replay must be one delivery.
 await js(consoleWindow,"document.getElementById('expression-mode').value='once'");
 await js(consoleWindow,`document.querySelector('[data-expression="${id}"]').click()`);
 await until(()=>js(avatar,`face.getState().name==='${id}'`));
 await until(()=>js(avatar,"face.getState().kind==='legacy'&&face.getState().name==='idle'"));
 evidence.onceReturned=true;assert.equal(await js(avatar,'window.customMounts'),2);
 fs.writeFileSync(path.join(out,'result.json'),JSON.stringify({result:'PASS',...evidence},null,2));app.quit();
}
run().catch(e=>{fs.writeFileSync(path.join(out,'failure.log'),String(e.stack));app.exit(1);});
