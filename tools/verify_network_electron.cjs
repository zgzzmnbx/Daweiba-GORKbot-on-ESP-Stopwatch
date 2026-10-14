/* Isolated real Electron window; no device connection or cloud requests. */
const path=require('node:path'),fs=require('node:fs'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..'),req=require('node:module').createRequire(path.join(root,'03-Src/gork-desktop/package.json'));
const {app,BrowserWindow}=req('electron');
const out=path.join(root,'04-output/v0.20.0/tests');fs.mkdirSync(out,{recursive:true});
app.setPath('userData',path.join(root,'Codex-Temp/wifi-ble-v020/electron-profile'));
const url='http://127.0.0.1:8885/';
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
app.whenReady().then(async()=>{
  const win=new BrowserWindow({width:1150,height:900,show:true,webPreferences:{contextIsolation:true,nodeIntegration:false,sandbox:true}});
  const errors=[];win.webContents.on('console-message',(_e,level,text)=>{if(level>=3)errors.push(text)});
  try{
    await win.loadURL(url);
    const js=s=>win.webContents.executeJavaScript(s,true);
    for(let i=0;i<100;i++){if(await js("document.getElementById('header-version').textContent.includes('0.20.0')"))break;await sleep(100);}
    await js("document.querySelector('[data-page-link=watch]').click()");
    const state=await js(`({passwordType:document.getElementById('network-password').type,policy:document.getElementById('network-policy').value,source:document.getElementById('network-detail').textContent,voiceDefault:document.getElementById('watch-dialogue-enable').checked,networkState:document.getElementById('network-state').textContent,version:document.getElementById('header-version').textContent})`);
    assert.equal(state.passwordType,'password');assert.equal(state.voiceDefault,false);assert.match(state.version,/0.20.0/);
    await js("document.getElementById('network-password').value='dummy-private-input'");
    assert.equal(await js("Array.from(document.querySelectorAll('pre,p,small')).some(e=>e.textContent.includes('dummy-private-input'))"),false);
    await js("document.getElementById('network-configure').click()");await sleep(300);
    assert.equal(await js("document.getElementById('network-password').value"),'');
    const response=await fetch(url+'api/device/network/provision',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({ssid:'test',password:'dummy-validation-secret',revision:'bad'})});
    assert.equal(response.status,422);assert(!(await response.text()).includes('dummy-validation-secret'));
    fs.writeFileSync(path.join(out,'network-mantine.png'),(await win.webContents.capturePage()).toPNG());
    await js("document.querySelector('[data-page-link=dialogue]').click()");
    assert.equal(await js("document.getElementById('watch-dialogue-enable').closest('[data-page]').dataset.page"),'dialogue');
    fs.writeFileSync(path.join(out,'watch-dialogue.png'),(await win.webContents.capturePage()).toPNG());
    await js("document.querySelector('[data-page-link=watch]').click()");
    await js("document.getElementById('theme-toggle').click()");
    assert.equal(await js("document.documentElement.dataset.consoleTheme"),'classic');
    fs.writeFileSync(path.join(out,'network-classic.png'),(await win.webContents.capturePage()).toPNG());
    win.setSize(600,800);await sleep(500);
    fs.writeFileSync(path.join(out,'network-narrow.png'),(await win.webContents.capturePage()).toPNG());
    await js("document.getElementById('theme-toggle').click()");
    assert.equal(await js("document.documentElement.dataset.consoleTheme"),'mantine');
    assert.deepEqual(errors,[]);
    fs.writeFileSync(path.join(out,'electron-network.json'),JSON.stringify({result:'PASS',state,errors,realWindow:true,classicAndMantine:true,narrowWindow:true,deviceConnected:false,cloudRequests:false},null,2));
  }catch(e){fs.writeFileSync(path.join(out,'electron-network-failure.log'),String(e.stack));process.exitCode=1;}
  finally{win.destroy();app.quit();}
});
