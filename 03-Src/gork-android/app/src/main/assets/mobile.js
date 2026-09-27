/* Local mobile UI. Device operations are enabled only when native capability says READY. */
(() => {
  const get = id => document.getElementById(id);
  const pending = new Map();
  let nextId = 1;
  let generation = 0;
  if (window.gorkNative) {
    window.gorkNative.onmessage = event => {
      let reply;
      try { reply = JSON.parse(event.data); } catch { return; }
      const task = pending.get(reply.requestId);
      if (!task) return;
      pending.delete(reply.requestId);
      clearTimeout(task.timer);
      if (reply.ok) task.resolve(reply.result);
      else task.reject(new Error(reply.error || 'UNKNOWN'));
    };
  }
  function callRaw(method, params={}) {
    if (!window.gorkNative) return Promise.reject(new Error('WEBVIEW_BRIDGE_UNAVAILABLE'));
    const requestId = `m${nextId++}`;
    return new Promise((resolve,reject) => {
      const limit = ['audio.pickAndPlayPcm','speech.local.toWatch'].includes(method) ? 0 : method==='speech.local.synthesizeProbe' ? 65000 : method==='device.connect' ? 80000 : method==='device.scan' ? 15000 : method.startsWith('speech.local.') ? 20000 : 6000;
      const timer = limit ? setTimeout(() => { pending.delete(requestId); reject(new Error('TIMEOUT')); }, limit) : null;
      pending.set(requestId,{resolve,reject,timer});
      window.gorkNative.postMessage(JSON.stringify({requestId,generation,method,params}));
    });
  }
  const bootstrap = callRaw('capabilities.get').then(info => { generation = info.generation; });
  function call(method, params={}) { return bootstrap.then(() => callRaw(method,params)); }
  let avatar = GorkAvatar.mount(get('avatar'),GorkCatalog,{expression:'idle'});
  let currentAppearance='gork';
  let ready=false;
  let audioBusy=false;
  const watchControls=['send-expression','set-volume','stop-sound','volume','play-wav','speak-watch'];
  let savedTarget='phone';
  function setReady(value) {
    ready=Boolean(value);
    watchControls.forEach(id=>{get(id).disabled=!ready;});
    get('play-wav').disabled=!ready||audioBusy;
    get('speak-watch').disabled=!ready||audioBusy;
    document.querySelectorAll('#sounds button').forEach(button=>{button.disabled=!ready;});
    document.querySelectorAll('input[name=target]').forEach(input=>{
      if(input.value!=='phone')input.disabled=!ready;
    });
    document.querySelector(`input[name=target][value=${ready?savedTarget:'phone'}]`).checked=true;
    get('top-status').textContent=ready?'手机页面可用 · Watch 控制就绪':'手机页面可用 · Watch 未连接';
    get('watch-state').textContent=ready?'已完成配对、服务发现和通知订阅，可发送控制命令。':'未连接。请先扫描附近的 GorkBot-SW。';
  }
  const save = value => call('preferences.set',value).catch(() => {
    get('top-status').textContent = '偏好保存失败';
  });
  document.querySelectorAll('nav button').forEach(button => button.addEventListener('click',() => {
    const tab = button.dataset.tab;
    document.querySelectorAll('[data-panel]').forEach(panel => { panel.hidden = panel.dataset.panel !== tab; });
    document.querySelectorAll('nav button').forEach(item => item.removeAttribute('aria-current'));
    button.setAttribute('aria-current','page');
  }));
  const appearanceSelect=get('appearance');
  for (const preset of GorkPresets) {
    const option=document.createElement('option'); option.value=preset.id; option.textContent=preset.name;
    appearanceSelect.append(option);
  }
  appearanceSelect.onchange=() => {
    currentAppearance=appearanceSelect.value;
    avatar.setAppearance({id:currentAppearance});
    save({appearance:appearanceSelect.value});
  };
  for (const sequence of GorkCatalog.sequences) {
    const button=document.createElement('button');
    button.textContent=sequence.name || sequence.id;
    button.type='button';
    button.title='在手机上预览 '+sequence.id;
    button.onclick=() => { avatar.set(sequence.id,{force:true}); };
    get('expressions').append(button);
    const option=document.createElement('option');
    option.value=sequence.id==='drowsy'?'sleepy':sequence.id==='playful'?'dizzy':sequence.id;
    option.textContent=sequence.name || sequence.id;
    get('watch-expression').append(option);
  }
  const work=document.createElement('option');work.value='happy-work';work.textContent='happy-work（Watch 专属）';get('watch-expression').append(work);
  get('draft').addEventListener('input',() => save({draft:get('draft').value}));
  document.querySelectorAll('input[name=target]').forEach(input=>input.onchange=()=>{
    savedTarget=input.value;save({target:savedTarget});
  });
  get('theme').onchange=() => {
    document.documentElement.dataset.theme=get('theme').value;
    save({theme:get('theme').value});
  };
  get('send').onclick=async () => {
    const value=get('draft').value.trim();
    if (!value) { get('chat-result').textContent='请输入文字。'; return; }
    const target=document.querySelector('input[name=target]:checked').value;
    if(target==='phone'||target==='both'){
      get('bubble').textContent=value;
      get('bubble').hidden=false;
    }
    if(target==='watch'||target==='both'){
      if(!ready){get('chat-result').textContent='Watch 未就绪。';return;}
      try { await call('character.showText',{text:value});
        get('chat-result').textContent=target==='both'?'手机已显示；Watch 文字回执已确认。':'Watch 文字回执已确认。';
      } catch(error){get('chat-result').textContent=`Watch 文字未确认：${error.message}`;call('state.get').then(state=>setReady(state.ready)).catch(()=>setReady(false));}
    } else get('chat-result').textContent='已在手机角色显示。';
  };
  get('stop').onclick=async () => {
    get('bubble').hidden=true;
    avatar.set('idle',{force:true});
    call('speech.local.stop').catch(()=>{});
    get('chat-result').textContent='手机显示已停止。';
    if(ready){
      try {await call('sound.stop');get('chat-result').textContent='手机已停止；Watch 短音停止回执已确认。';}
      catch {await call('task.cancel').catch(()=>{});setReady(false);get('chat-result').textContent='手机已停止；Watch 停止未确认，连接已断开。';}
    }
  };
  get('speak-local').onclick=async()=>{
    const value=get('draft').value.trim();
    if(!value){get('chat-result').textContent='请输入要朗读的文字。';return;}
    try{await call('speech.local.speak',{text:value});get('chat-result').textContent='已提交本机中文语音引擎；实际听感待确认。';}
    catch(error){get('chat-result').textContent=`本机朗读不可用：${error.message}`;}
  };
  get('speak-watch').onclick=async()=>{
    const value=get('draft').value.trim();
    if(!value){get('chat-result').textContent='请输入完整语句。';return;}
    if(!ready){get('chat-result').textContent='Watch 未连接。';return;}
    audioBusy=true;
    setReady(true);
    get('chat-result').textContent='正在本机合成完整音频，然后传给 Watch…';
    try {
      await call('speech.local.toWatch',{text:value});
      get('chat-result').textContent='设备报告 PLAYED；文字在 COMMIT 后发送。请听验完整语句。';
    } catch(error) {
      get('chat-result').textContent=`Watch 朗读未完成：${error.message}`;
      call('state.get').then(state=>setReady(state.ready)).catch(()=>setReady(false));
    } finally {audioBusy=false;setReady(ready);}
  };
  get('check-tts').onclick=async()=>{
    get('tts-state').textContent='正在检测系统中文音色…';
    try{const result=await call('speech.local.status');get('tts-state').textContent=`可用的本机中文音色：${result.voice}。`;
    }catch(error){get('tts-state').textContent=`本机中文音色不可用：${error.message}`;}
  };
  get('probe-tts-file').onclick=async()=>{
    const value=get('draft').value.trim();
    if(!value){get('tts-file-state').textContent='先在对话页输入完整语句。';return;}
    const button=get('probe-tts-file');
    button.disabled=true;
    get('tts-file-state').textContent='正在等待本机语音引擎生成完整文件…';
    try {
      const result=await call('speech.local.synthesizeProbe',{text:value});
      get('tts-file-state').textContent=`完整文件已转为 ${result.rate} Hz PCM16、${result.seconds.toFixed(2)} 秒（${result.bytes} 字节）；尚未发送 Watch。`;
    } catch(error) {get('tts-file-state').textContent=`本机文件合成不可用：${error.message}`;}
    finally {button.disabled=false;}
  };
  const devices=get('devices');
  get('scan').onclick=async () => {
    get('watch-state').textContent='正在扫描，首次使用会请求附近设备权限。';
    try {
      const result=await call('device.scan');
      devices.replaceChildren();
      for(const item of result.devices){
        const option=document.createElement('option');option.value=item.address;option.textContent=`${item.name} · ${item.address}`;devices.append(option);
      }
      get('watch-state').textContent=result.devices.length?`发现 ${result.devices.length} 台候选设备。选择后在 Watch 本机打开 Pair。`:'未发现 GorkBot-SW。请检查设备蓝牙与 Pair 窗口。';
      get('connect').disabled=!result.devices.length||!get('migration-ack').checked;
    } catch(error){get('watch-state').textContent=`扫描失败：${error.message}`;}
  };
  get('migration-ack').onchange=()=>{get('connect').disabled=!devices.value||!get('migration-ack').checked;};
  devices.onchange=()=>{get('connect').disabled=!devices.value||!get('migration-ack').checked;};
  get('connect').onclick=async()=>{
    if(!devices.value||!get('migration-ack').checked)return;
    get('watch-state').textContent='正在请求系统配对并发现三个 GATT 服务…';
    try{await call('device.connect',{address:devices.value});setReady(true);}
    catch(error){setReady(false);get('watch-state').textContent=`连接未就绪：${error.message}。若设备仍绑定电脑，请按迁移清单在 Watch 本机清绑定并打开 Pair。`;}
  };
  get('disconnect').onclick=async()=>{await call('device.disconnect').catch(()=>{});setReady(false);};
  get('send-expression').onclick=async()=>{
    try{await call('character.play',{name:get('watch-expression').value,mode:get('watch-mode').value});get('watch-state').textContent='Watch 表情回执已确认。';}
    catch(error){get('watch-state').textContent=`表情未确认：${error.message}`;}
  };
  for(let id=1;id<=6;id++){
    const button=document.createElement('button');button.textContent=`短音 ${id}`;button.disabled=true;
    button.onclick=async()=>{
      try{await call('sound.play',{soundId:id});get('watch-state').textContent=`短音 ${id} 设备完成回执已确认；实际听感待人工确认。`;}
      catch(error){get('watch-state').textContent=`短音未确认：${error.message}`;}
    };
    get('sounds').append(button);
  }
  get('volume').oninput=()=>{get('volume-value').textContent=`${get('volume').value}%`;};
  get('set-volume').onclick=async()=>{
    try{await call('sound.volume',{volume:Number(get('volume').value)});get('watch-state').textContent='音量设置回执已确认。';}
    catch(error){get('watch-state').textContent=`音量未确认：${error.message}`;}
  };
  get('stop-sound').onclick=async()=>{
    try{await call('sound.stop');get('watch-state').textContent='短音停止回执已确认。';}
    catch(error){get('watch-state').textContent=`停止未确认：${error.message}`;}
  };
  get('play-wav').onclick=async()=>{
    const button=get('play-wav');
    audioBusy=true;
    button.disabled=true;
    get('cancel-audio').disabled=false;
    get('audio-state').textContent='请选择 WAV；发送期间保持应用在前台。';
    const ticker=setInterval(()=>call('state.get').then(state=>{
      if(!state.audio)return;
      const sent=state.audio.confirmedBytes;
      const total=state.audio.totalBytes;
      get('audio-state').textContent=`${state.audio.stage} · 设备已确认 ${sent}/${total} 字节`;
    }).catch(()=>{}),1000);
    try {
      const result=await call('audio.pickAndPlayPcm');
      get('audio-state').textContent=`设备报告 PLAYED（${result.bytes} 字节）；请实际听验完整语句。`;
    } catch(error) {
      get('audio-state').textContent=`Watch 音频未完成：${error.message}`;
      call('state.get').then(state=>setReady(state.ready)).catch(()=>setReady(false));
    } finally {clearInterval(ticker);audioBusy=false;button.disabled=!ready;get('cancel-audio').disabled=true;}
  };
  get('cancel-audio').onclick=async()=>{
    await call('task.cancel').catch(()=>{});
    setReady(false);
    get('audio-state').textContent='传输已中止，Watch 已断开；重新扫描后才能发送。';
  };
  document.addEventListener('visibilitychange',()=>{
    if(document.visibilityState==='hidden'){avatar?.dispose();avatar=null;return;}
    avatar=GorkAvatar.mount(get('avatar'),GorkCatalog,{expression:'idle',appearance:{id:currentAppearance}});
    call('state.get').then(value=>setReady(value.ready)).catch(()=>setReady(false));
  });
  setInterval(()=>{
    if(document.visibilityState!=='visible')return;
    call('state.get').then(value=>{if(Boolean(value.ready)!==ready)setReady(value.ready);}).catch(()=>{});
  },2000);
  call('preferences.get').then(value => {
    if (GorkPresets.some(item=>item.id===value.appearance)) {
      appearanceSelect.value=value.appearance;
      currentAppearance=value.appearance;
      avatar.setAppearance({id:value.appearance});
    }
    if (value.theme==='dark') { get('theme').value='dark'; document.documentElement.dataset.theme='dark'; }
    get('draft').value=value.draft || '';
    if(['phone','watch','both'].includes(value.target))savedTarget=value.target;
  }).catch(() => { get('top-status').textContent='手机角色可用 · 偏好桥不可用'; });
})();
