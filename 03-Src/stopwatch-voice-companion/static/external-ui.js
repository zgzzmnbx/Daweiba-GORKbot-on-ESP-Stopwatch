const states={queued:'排队中',dispatching:'输出中',active:'显示中',completed:'已完成',partial:'部分完成',failed:'失败',cancelled:'已取消',superseded:'已替换',expired:'已过期',interrupted:'重启中断'};
const targets={desktop:'桌面',watch:'Watch',pc:'电脑'};
const deliveries={displayed:'已显示',accepted:'已接收',offline:'未连接',failed:'失败',suppressed:'已让出',not_requested:'未请求',completed_by_os:'播放已结束',device_playback_completed:'设备回报播放结束'};
export function createExternalUI({document,api,acquireWorkspace,hasWorkspace=()=>true,clipboard=()=>Promise.resolve(),onSnapshot=()=>{}}) {
  const $=id=>document.getElementById(id),feedback=$('external-feedback');
  if(!feedback)return {refresh:async()=>{}};
  let clients=[],editing=null,busy=false,refreshing=false,tokenTimer=null;
  const element=(tag,text,className)=>{const node=document.createElement(tag);if(text!==undefined)node.textContent=text;if(className)node.className=className;return node;};
  function note(text,error=false){feedback.textContent=text;feedback.dataset.error=String(error);}
  function clearToken(){clearTimeout(tokenTimer);$('external-token').value='';$('external-token-panel').hidden=true;}
  function paint(data){
    onSnapshot(data);
    clients=data.clients||[];$('external-resume').hidden=!data.paused;
    $('external-queue').textContent=data.paused?'已暂停':data.pending?`${data.pending} 条排队 / 输出中`:'等待通知';
    $('external-output-note').textContent=`当前声音：${targets[data.current_sound_target]||'电脑'} · 沿用已应用音色`;
    $('external-current').replaceChildren();
    for(const target of ['desktop','watch']){
      const value=data.current?.[target],box=element('div',undefined,'external-output');
      box.append(element('small',targets[target]+(value?.delivery ? ' · '+(value.delivery==='not_requested'?'等待输出':deliveries[value.delivery]||value.delivery):'')),element('strong',value?clients.find(c=>'external:'+c.source===value.source)?.label||value.source.replace('external:',''):'待机'));
      box.append(element('p',value?.bubble|| (value?'表情正在显示':'暂无程序消息')));$('external-current').append(box);
    }
    $('external-clients').replaceChildren();
    for(const client of clients){
      const row=element('article',undefined,'external-client');
      const title=element('div');title.append(element('strong',client.label),element('small',client.source));
      const info=element('div',undefined,'external-client-info');
      info.append(element('span',client.enabled?'已启用':'未启用',client.enabled?'external-status enabled':'external-status'),
        element('small',`显示：${(client.display_targets||[]).map(t=>targets[t]).join(' / ')||'无'} · 声音：${(client.speech_targets||[]).map(t=>targets[t]).join(' / ')||'无'}`));
      if(data.poll_source===client.source){
        info.append(element('small','旧轮询正在使用此来源。先关闭兼容轮询，再在配置中启用程序。'));
        const legacy=element('button','打开兼容轮询设置');legacy.type='button';
        legacy.onclick=()=>{const panel=$('sentinel-legacy');panel.open=true;panel.scrollIntoView?.({block:'start',behavior:'smooth'});};
        info.append(legacy);
      }else if(!client.enabled){
        info.append(element('small','点击配置，勾选“启用这个程序”并保存后，调试信号才能被接收。'));
      }
      const edit=element('button','配置');edit.type='button';edit.onclick=()=>open(client);
      row.append(title,info,edit);$('external-clients').append(row);
    }
    if(!clients.length)$('external-clients').append(element('p','登记一次，再由程序发送新阶段消息。','muted'));
    $('external-receipts').replaceChildren();
    for(const receipt of data.receipts||[]){
      const row=element('details',undefined,'external-receipt'),summary=element('summary');
      summary.append(element('span',states[receipt.status]||receipt.status,'external-status '+receipt.status),
        element('strong',clients.find(c=>c.source===receipt.source)?.label||receipt.source),
        element('span',receipt.request?.text||receipt.stage),element('time',new Date(receipt.accepted_at).toLocaleTimeString('zh-CN',{hour12:false})));
      const detail=element('div',undefined,'external-receipt-detail');
      detail.append(element('small',`${receipt.stage} · ${receipt.task_id} · ${receipt.attempt}`));
      detail.append(element('p',Object.entries(receipt.delivery||{}).map(([target,result])=>`${target==='speech'?'语音':targets[target]}：${deliveries[result]||result}`).join('　')));
      if(receipt.error)detail.append(element('p',receipt.error));
      if(['queued','dispatching','active','partial'].includes(receipt.status)){
        const cancel=element('button','取消这条');cancel.type='button';        cancel.onclick=async()=>{try{await api('/external/owner-cancel','POST',{source:receipt.source,event_id:receipt.event_id});await refresh();}catch(error){note(error.message,true);}};
        detail.append(cancel);
      }
      row.append(summary,detail);$('external-receipts').append(row);
    }
    if(!(data.receipts||[]).length)$('external-receipts').append(element('p','尚无通知。','muted'));
  }
  async function refresh(){
    if(refreshing||busy||!hasWorkspace())return;
    refreshing=true;
    try{paint(await api('/external/overview'));}
    catch(error){note(error.status===404?'当前后台尚未加载通用接口；请从托盘退出后正常重开 Gork。':error.message,true);}
    finally{refreshing=false;}
  }
  function open(client=null){
    editing=client?.source||null;clearToken();$('external-editor').hidden=false;
    $('external-source').value=client?.source||'';$('external-source').readOnly=!!client;
    $('external-label').value=client?.label||'';$('external-priority').value=String(client?.max_priority??2);
    $('external-enabled').checked=client?.enabled===true;
    for(const target of ['desktop','watch'])$('external-display-'+target).checked=(client?.display_targets||['desktop','watch']).includes(target);
    for(const target of ['pc','watch'])$('external-speech-'+target).checked=(client?.speech_targets||[]).includes(target);
    $('external-save').textContent=client?'保存权限':'保存登记';$('external-source').focus();
  }
  $('external-add').onclick=()=>open();$('external-editor-cancel').onclick=()=>{$('external-editor').hidden=true;editing=null;};
  $('external-editor').onsubmit=async event=>{
    event.preventDefault();if(busy)return;
    if(!hasWorkspace()&&!await acquireWorkspace())return;
    const source=$('external-source').value.trim();
    if(!/^[a-z][a-z0-9_-]{0,39}$/.test(source)){note('程序标识使用小写英文字母、数字、短横线或下划线。',true);return;}
    const policy={label:$('external-label').value.trim(),enabled:$('external-enabled').checked,
      display_targets:['desktop','watch'].filter(t=>$('external-display-'+t).checked),
      speech_targets:['pc','watch'].filter(t=>$('external-speech-'+t).checked),max_priority:Number($('external-priority').value)};
    if(!policy.label){note('请填写显示名称。',true);return;}
    busy=true;$('external-save').disabled=true;
    try{
      const result=await api(editing?'/external/clients/'+encodeURIComponent(editing):'/external/clients',editing?'PUT':'POST',editing?policy:{source,...policy});
      $('external-editor').hidden=true;editing=null;note(policy.enabled?'程序已启用；仅接收新通知。':'登记已保存，当前未启用。');
      if(result.token){$('external-token').value=result.token;$('external-token-panel').hidden=false;tokenTimer=setTimeout(clearToken,60000);}
    }catch(error){note(error.message,true);if(error.code==='SOURCE_MODE_CONFLICT')$('sentinel-legacy').open=true;}
    finally{busy=false;$('external-save').disabled=false;await refresh();}
  };
  $('external-token-copy').onclick=async()=>{try{await clipboard($('external-token').value);note('令牌已复制；请保存到该程序的本机私有配置。');}catch{note('复制失败，请检查剪贴板权限。',true);}};
  $('external-token-close').onclick=clearToken;
  $('external-acquire').onclick=async()=>{if(await acquireWorkspace()){note('已取得控制权。');await refresh();}};
  $('external-refresh').onclick=async()=>{if(hasWorkspace()||await acquireWorkspace())await refresh();};
  $('external-resume').onclick=async()=>{try{await api('/external/resume','POST');note('已恢复；旧通知不会补播。');await refresh();}catch(error){note(error.message,true);}};
  return {refresh,paint,destroy(){clearToken();}};
}
