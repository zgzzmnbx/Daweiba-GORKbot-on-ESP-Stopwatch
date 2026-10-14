(() => {
  let mounted=false,api,revision=0,forgetConfirm=false,watchPending=false,watchError='',latestWatch=null,answerState,setupSeen='',setupAvailable=false,setupPending=false,setupDirty=false,savedSetup=null;
  const el=id=>document.getElementById(id);
  let watchWanted=true,autoWatchKey='';
  const stages={disabled:'未启用',ready:'等待按键',armed:'已就绪',recording:'正在录音',recognizing:'正在识别',thinking:'正在生成回答',synthesizing:'正在合成',transferring:'正在传输和播放',completed:'本轮完成',cancelled:'本轮已取消',interrupted:'本轮中断，请重试',speech_not_played:'回答较长，未播放'};
  const feedback=text=>{el('network-feedback').textContent=text;el('network-feedback').hidden=!text;};
  const setupRestart='当前后台尚未加载提示词配置功能。请右击系统托盘 Gork，选“退出”后重新打开；已有 Key 会保留。';
  const setupFailures={ANSWER_SETUP_BUSY:'请先关闭按键对话、停止设备音频，再保存。',WORKSPACE_INVALID:'请先取得工作台控制权，再保存。',CLIENT_REQUIRED:'工作台会话尚未建立，请重新打开控制台后保存。',ANSWER_SETUP_INVALID:'请核对提示词、目标字数和 API Key；首次配置 Key 不能留空。',INVALID_INPUT:'请核对模型、提示词、目标字数和 API Key。',ANSWER_SETUP_FAILED:'本机加密配置未保存，请检查 Windows 用户凭据保护及文件权限。',LOCAL_ONLY:'请从本机 Gork 控制台保存配置。'};
  function renderPrompt(){
    el('answer-setup-preview').value=(el('answer-preview-mode').value==='watch'?savedSetup?.watch_prompt:savedSetup?.effective_prompt)||'新版后台加载并保存后显示实际提示词。';
  }
  const run=async fn=>{try{await fn();}catch{feedback('操作未完成，请检查所选连接、控制权和设备状态。秘密输入不会显示在错误中。');}};
  const watchFailures={ANSWER_UNAVAILABLE:'AI 回答服务未配置或未就绪，暂不能启用按键对话。',ANSWER_UPLOAD_DENIED:'请在设置中允许向回答服务发送文字，并应用设置。',AUDIO_UPLOAD_DENIED:'云端识别需要允许上传录音，并应用设置。',TEXT_UPLOAD_DENIED:'云端朗读需要允许上传回读文字，并应用设置。',VOICE_SESSION_INVALID:'请先连接电脑语音会话，再启用按键对话。',WORKSPACE_INVALID:'请先取得工作台控制权，再启用按键对话。',WORKSPACE_BUSY:'另一窗口正在控制，请先接管工作台。'};
  async function setWatchEnabled(enabled){
    if(watchPending)return;
    watchPending=true;watchError='';renderWatch();
    try{
      const value=await api('/watch/dialogue','POST',{enabled});
      latestWatch=value;
    }catch(error){watchError=watchFailures[error.code]||'Watch 对话操作未完成，请检查连接后重试。';}
    finally{watchPending=false;renderWatch();}
  }
  function renderWatch(){
    if(!latestWatch)return;
    const watch=latestWatch,unavailable=answerState&&!answerState.enabled;
    const detail=watchError||watch.error||(!watch.enabled&&unavailable?'暂不能启用：'+(answerState.reason||'AI 回答服务未就绪'):'')||(watch.enabled&&!Array.isArray(watch.turns)?'同步按键对话记录需要新版后台，请从托盘退出后重开 Gork。':'');
    const hint=el('watch-dialogue-feedback');hint.textContent=detail;hint.hidden=!detail;
    el('watch-dialogue-enable').disabled=watchPending||(!watch.enabled&&Boolean(unavailable));
    el('watch-dialogue-enable').setAttribute('aria-describedby','watch-dialogue-feedback');
    if(!watchPending)el('watch-dialogue-enable').checked=watch.enabled;
    el('watch-dialogue-status').textContent=watchPending?'正在更新…':!watch.enabled&&detail?'暂不可用':stages[watch.stage]||watch.stage;
    el('watch-dialogue-status').dataset.state=watch.enabled?'ready':'idle';
    el('watch-dialogue-shorten').hidden=watch.stage!=='speech_not_played';
    el('watch-dialogue-timings').textContent=Object.entries(watch.timings||{}).map(([k,v])=>`${{prepare:'录音准备',download:'录音上传到电脑',asr:'识别',answer:'回答',tts:'合成',playback:'传输与播放合计',encode:'编码',send:'音频发送',device_play:'设备播放',stop_to_play:'停录到播放回执'}[k]||k} ${v.toFixed(2)}秒`).join(' · ');
  }
  function mount(fn){
    if(mounted||!el('network-configure'))return;
    mounted=true;api=fn;
    const setupStatus=el('answer-setup-status');
    el('answer-setup-save').disabled=true;
    for(const id of ['answer-setup-model','answer-setup-prompt','answer-setup-max-chars'])el(id).addEventListener('input',()=>{setupDirty=true;});
    el('answer-preview-mode').onchange=renderPrompt;
    el('answer-setup-reset').onclick=()=>{
      if(!setupAvailable||setupPending)return;
      el('answer-setup-prompt').value=savedSetup.default_prompt;
      el('answer-setup-max-chars').value=String(savedSetup.default_max_chars);
      setupDirty=true;setupStatus.textContent='已恢复简短默认草稿，点击保存后生效。';
    };
    el('answer-setup-save').onclick=async()=>{
      if(!setupAvailable||setupPending)return;
      const prompt=el('answer-setup-prompt').value.trim(),limit=Number(el('answer-setup-max-chars').value);
      if(!prompt||prompt.length>2000||!Number.isInteger(limit)||limit<5||limit>300){setupStatus.textContent='提示词须为1～2000字，目标字数须为5～300的整数。';return;}
      setupPending=true;
      const input=el('answer-setup-key'),key=input.value;input.value='';
      const button=el('answer-setup-save');button.disabled=true;setupStatus.textContent='正在保存本机配置…';
      try{
        const value=await api('/answer/config','POST',{model:el('answer-setup-model').value,api_key:key,system_prompt:prompt,max_chars:limit});
        savedSetup=value;setupDirty=false;renderPrompt();
        answerState=value.capability;watchError='';renderWatch();
        setupStatus.textContent='已保存；现在可选择 AI 回答。按键对话还需应用文字上传许可。';
      }catch(error){
        if(error.status===404){setupAvailable=false;setupStatus.textContent=setupRestart;}
        else setupStatus.textContent=setupFailures[error.code]||'保存请求未完成，请检查本机连接后重试。';
      }finally{setupPending=false;button.disabled=!setupAvailable;}
    };
    el('network-configure').onclick=()=>run(async()=>{
      const password=el('network-password').value;
      el('network-password').value='';
      const via=el('network-provision-via').value;
      feedback(via==='usb'?'正在通过本机USB配置，请保持Watch连接并等待保存确认…':'正在通过可信蓝牙配置，请等待设备保存确认…');
      await api('/device/network/provision','POST',{ssid:el('network-ssid').value,password,revision,via});
      feedback('设备已确认配置。等待热点连接和 PC 身份认证。');
    });
    el('network-save').onclick=()=>run(async()=>{const v=await api('/device/network','PATCH',{policy:el('network-policy').value,power:el('network-power').value,revision});revision=v.revision;feedback('设备确认设置已保存');});
    el('network-connect').onclick=()=>run(async()=>{await api('/device/network/connect','POST',{address:el('network-address').value.trim()});feedback('正在连接；身份认证通过后才显示就绪');});
    el('network-forget').onclick=()=>run(async()=>{
      if(!forgetConfirm){forgetConfirm=true;el('network-forget').textContent='再次点击确认忘记热点';return;}
      await api('/device/network','DELETE');forgetConfirm=false;el('network-forget').textContent='忘记热点';feedback('设备确认已忘记热点，BLE 绑定保留');
    });
    el('watch-dialogue-enable').onchange=()=>{
      watchWanted=el('watch-dialogue-enable').checked;
      return setWatchEnabled(watchWanted);
    };
    el('watch-dialogue-shorten').onclick=()=>run(async()=>{await api('/watch/dialogue/shorten','POST',{});feedback('已明确请求生成更短回答，此次沿用当前文字上传许可');});
  }
  function update(network,watch,fn,answer,setup,startup={}){
    mount(fn);if(!mounted)return;
    if(answer!==undefined)answerState=answer;
    setupAvailable=setup?.prompt_configurable===true;
    el('answer-setup-save').disabled=setupPending||!setupAvailable;
    el('answer-setup-reset').disabled=setupPending||!setupAvailable;
    if(!setupAvailable&&!setupPending)el('answer-setup-status').textContent=setupRestart;
    const setupFresh=!Number.isInteger(savedSetup?.revision)||!Number.isInteger(setup?.revision)||setup.revision>=savedSetup.revision;
    if(setupAvailable&&setupFresh&&!setupPending&&JSON.stringify(setup)!==setupSeen){
      if(!setupDirty){
        el('answer-setup-model').value=setup.model;
        el('answer-setup-prompt').value=setup.system_prompt;
        el('answer-setup-max-chars').value=String(setup.max_chars);
      }
      savedSetup=setup;renderPrompt();
      setupSeen=JSON.stringify(setup);
      el('answer-setup-status').textContent=setup.error||(setup.key_saved?'已保存本机配置；接口可用性以首次问答结果为准。':'尚未配置，请在本机输入 API Key 并保存。');
    }
    if(network){
      revision=network.revision;
      const route={wifi:'Wi-Fi',ble:'蓝牙',offline:'离线'}[network.route]||'离线';
      const ready=network.route==='wifi'||network.route==='ble';
      el('network-state').textContent=ready?`${route} 已连接`:network.wifi_connected?'Wi-Fi 正在确认连接':'设备离线';
      el('network-state').dataset.state=ready?'ready':'idle';
      const states={'authenticated PC':'电脑身份认证通过','hotspot connected; waiting PC':'热点已连接，等待电脑认证','connecting / retry backoff':'正在连接热点','unconfigured':'尚未配置热点'};
      el('network-detail').textContent=network.error||(ready?`当前使用${route==='蓝牙'?'蓝牙':' Wi-Fi '}通信。电脑与 Watch 请保持在同一热点。`:states[network.device?.state]||'电脑与 Watch 使用同一个 2.4 GHz 热点。');
      el('network-current-address').textContent=network.address||'尚未获取';
      el('network-ble-state').textContent=network.ble_connected?'已连接':'未连接';
      const source={usb:'USB',external:'外接电源',battery:'电池',unknown:'未知'}[network.device?.source]||'未知';
      const power={1:'性能',2:'省电'}[network.device?.effective_power]||'待确认';
      el('network-power-state').textContent=`${source} / ${power}`;
      if(document.activeElement!==el('network-policy'))el('network-policy').value=network.policy;
      if(document.activeElement!==el('network-power'))el('network-power').value=network.power;
      if(network.address&&document.activeElement!==el('network-address'))el('network-address').placeholder=network.address;
    }
    if(watch)latestWatch=watch;
    renderWatch();
    // Default enabled is an intent, never an implicit upload permission or mic start.
    if(!startup.ready)autoWatchKey='';
    if(watchWanted&&startup.ready&&answerState?.enabled&&latestWatch&&!latestWatch.enabled&&!watchPending){
      const key=startup.key||'ready';
      if(autoWatchKey!==key){autoWatchKey=key;void setWatchEnabled(true);}
    }
  }
  window.GorkNetworkUI={update};
})();
