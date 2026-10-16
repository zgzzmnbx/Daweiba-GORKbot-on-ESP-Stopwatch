/* Display existing health evidence; never probe providers or acquire a session. */
(function(root){
  const doc=root.document,$=id=>doc.getElementById(id);
  const nav=$('module-tabs'),prev=$('tabs-prev'),next=$('tabs-next');
  function bounds(){
    const overflow=nav.scrollWidth>nav.clientWidth+2;
    prev.hidden=next.hidden=!overflow;
    prev.disabled=nav.scrollLeft<=2;
    next.disabled=nav.scrollLeft+nav.clientWidth>=nav.scrollWidth-2;
  }
  const behavior=()=>root.matchMedia?.('(prefers-reduced-motion: reduce)').matches?'instant':'smooth';
  function reveal(){
    const active=nav.querySelector(`[href="${root.location.hash || '#dialogue'}"]`);
    if(active){
      const a=active.getBoundingClientRect(),n=nav.getBoundingClientRect();
      const delta=a.left<n.left?a.left-n.left:a.right>n.right?a.right-n.right:0;
      if(delta)nav.scrollBy({left:delta,behavior:'instant'});
    }
    bounds();
  }
  prev.onclick=()=>nav.scrollBy({left:-Math.max(120,nav.clientWidth*.75),behavior:behavior()});
  next.onclick=()=>nav.scrollBy({left:Math.max(120,nav.clientWidth*.75),behavior:behavior()});
  nav.addEventListener('scroll',bounds,{passive:true});
  nav.addEventListener('focusin',event=>event.target.scrollIntoView?.({block:'nearest',inline:'nearest'}));
  root.addEventListener('hashchange',reveal);
  root.addEventListener('resize',reveal);
  if(root.ResizeObserver)new root.ResizeObserver(()=>{bounds();reveal();}).observe(nav);
  doc.fonts?.ready.then(reveal);
  bounds();reveal();

  const menus=[...doc.querySelectorAll('.service-chip,.header-menu')];
  for(const menu of menus){
    menu.addEventListener('toggle',()=>{if(menu.open)for(const other of menus)if(other!==menu)other.open=false;});
    menu.addEventListener('keydown',event=>{if(event.key==='Escape'){menu.open=false;menu.querySelector('summary').focus();}});
  }
  doc.addEventListener('click',event=>{
    for(const menu of menus)if(menu.open&&(!menu.contains(event.target)||event.target.closest('a')))menu.open=false;
  });
  // Give the existing controls text labels when they live in the More panel.
  for(const [id,label] of [['theme-color-menu','主题配色'],['architecture-open','架构图']]){
    const parent=id==='theme-color-menu'?$(id).querySelector('summary'):$(id).querySelector('.mantine-Button-label')||$(id);
    const text=doc.createElement('span');text.className='menu-text';text.textContent=label;parent.append(text);
  }
  let latest=null,offline=false;
  function paint(key,state,title,detail){
    if(key==='watch'&&state!=='ready')$('watch-transport').textContent=state==='offline'?'未连接':'未知';
    const chip=$('service-'+key);chip.dataset.state=state;
    chip.querySelector('summary').title=title;
    chip.querySelector('summary').setAttribute('aria-label',title);
    $('global-'+key).textContent=title;
    $('service-'+key+'-detail').textContent=detail;
  }
  function observation(value,base,detail){
    if(!value||!['success','error'].includes(value.state)||!Number.isFinite(value.at))return ['configured',base+' · 已配置',detail+'；尚无实际请求结果，不代表云端已连通。'];
    const age=Date.now()/1000-value.at;
    const time=new Date(value.at*1000).toLocaleTimeString('zh-CN',{hour12:false});
    const success=value.state==='success',fresh=age>=0&&age<=300;
    return [fresh?(success?'ready':'error'):'unknown',base+(fresh?(success?' · 最近成功':' · 最近失败'):' · 待验证'),
      `${detail}；上次请求${success?'成功':'失败'}（${time}）${fresh?'，不表示持续连接。':'，已超过 5 分钟，不作为当前可用性判断。'}`];
  }
  function modelStates(){
    if(offline){for(const key of ['answer','tts'])paint(key,'unknown',key==='answer'?'问答 · 状态未知':'合成 · 状态未知','控制台健康状态读取失败；旧结果不作为当前状态。');return;}
    if(!latest)return;
    const answer=latest.answer,model=answer?.model||'问答模型';
    if(!answer)paint('answer','unknown','问答 · 状态未知','当前后台没有返回模型能力。');
    else if(!answer.enabled)paint('answer','offline','问答 · 未配置','回答模型未配置完整或缺少凭据，请打开设备与问答设置。');
    else if(!$('answer-consent').checked)paint('answer','paused',model+' · 未授权','文字上传许可已关闭；不会为状态展示调用模型。');
    else paint('answer',...observation(answer.observation,model,'只观察正常问答请求'));
    const route=latest.speech_output?.route,cloud=latest.capabilities?.cloud||latest.voice?.cloud;
    const name=route==='local'?'本地 TTS':route==='cloud'?(cloud?.tts_model||'云端 TTS'):'语音合成';
    if(latest.voice_error)paint('tts','error',name+' · 服务不可用','语音服务健康检查失败；不据此推断云端模型故障。');
    else if(!route)paint('tts','unknown',name+' · 路由未知','当前后台未返回已应用的合成路由，请打开语音设置。');
    else if(route==='cloud'&&!$('text-consent').checked)paint('tts','paused',name+' · 未授权','回读文字上传许可已关闭。');
    else if(route==='local')paint('tts',latest.capabilities?.tts?.state==='ready'?'ready':'unknown',name+(latest.capabilities?.tts?.state==='ready'?' · 引擎就绪':' · 等待引擎'),'本地引擎状态来自语音服务，不使用云端。');
    else if(cloud?.state==='missing_key')paint('tts','offline',name+' · 未配置','云端合成配置不完整，请查看语音设置。');
    else if(cloud?.state!=='configured')paint('tts','unknown',name+' · 状态未知','当前后台未返回云端配置状态。');
    else {
      const seen=latest.speech_output?.observation;
      paint('tts',...observation(seen?.route===route?seen:null,name,'本机语音服务可达；云端按需请求'));
    }
  }
  root.GorkShell={
    health(data){latest=data;offline=false;modelStates();},
    unavailable(){offline=true;modelStates();for(const key of ['voice','watch'])paint(key,'unknown',key==='voice'?'语音 · 状态未知':'Watch · 状态未知','控制台健康状态读取失败。');},
    session({connected,voiceLabel,robotConnected,watchLink}){
      if(offline){for(const key of ['voice','watch'])paint(key,'unknown',key==='voice'?'语音 · 状态未知':'Watch · 状态未知','控制台健康状态读取失败。');return;}
      paint('voice',connected?'ready':'offline','语音 · '+voiceLabel,'表示当前窗口的语音会话。合成模型状态单独显示。');
      $('watch-transport').textContent=robotConnected?(['Wi-Fi','蓝牙'].includes(watchLink?.trim())?watchLink.trim():'未知'):'未连接';
      paint('watch',robotConnected?'ready':'offline','Watch · '+(robotConnected?watchLink+'已连接':'未连接'),'显示当前使用的设备连接通道；点击下方入口查看设备。');
      modelStates();
    }
  };
})(window);
