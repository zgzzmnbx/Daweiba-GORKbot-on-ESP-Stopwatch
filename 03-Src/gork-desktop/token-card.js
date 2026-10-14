const node=id=>document.getElementById(id);
function formatTokens(value){
  if(!Number.isFinite(value)||value<0)return '—';
  if(value>=1e9)return `${(value/1e9).toFixed(2)}B`;
  if(value>=1e6)return `${(value/1e6).toFixed(2)}M`;
  if(value>=1e3)return `${(value/1e3).toFixed(1)}K`;
  return Math.round(value).toLocaleString('zh-CN');
}
function renderTokens(value={}) {
  renderQuota(value.quota);
  const known=Number.isFinite(value.total_tokens)&&value.total_tokens>=0;
  document.body.dataset.stale=String(Boolean(value.stale));
  node('token-date').textContent=/^\d{4}-\d{2}-\d{2}$/.test(value.date||'')?`${value.date.slice(5)} · 北京时间`:'北京时间';
  for(const [id,key] of [['token-total','total_tokens'],['token-input','input_tokens'],['token-output','output_tokens']]){
    const amount=known?value[key]:null;node(id).textContent=formatTokens(amount);
    node(id).title=Number.isFinite(amount)?`${amount.toLocaleString('zh-CN')} tokens`:'';
  }
  const messages={loading:'正在读取 CC Switch…',missing:'未找到 CC Switch 用量库',unsupported:'CC Switch 数据格式暂不支持',unavailable:'暂时无法读取 CC Switch'};
  node('token-status').textContent=value.status==='available'?`${Number.isInteger(value.request_count)?value.request_count.toLocaleString('zh-CN'):'—'} 次请求 · 含缓存 token`:
    `${messages[value.status]||'暂无用量数据'}${known?' · 上次统计':''}`;
  node('token-cache').textContent=`其中缓存 ${formatTokens(known?value.cache_tokens:null)}`;
  node('token-notice').hidden=value.status==='available'&&!value.stale;
  node('token-notice').textContent=value.stale&&known?'上次统计 · 等待刷新':messages[value.status]||'暂无用量数据';
  const stamp=new Date(value.sampled_at||'');
  const options={timeZone:'Asia/Hong_Kong',hour12:false};
  const last=new Date(Number.isFinite(value.last_event_at)?value.last_event_at*1000:NaN);
  const updated=Number.isFinite(stamp.getTime())?`读取 ${stamp.toLocaleTimeString('zh-CN',options)}`:'仅统计已同步记录';
  const sameDay=Number.isFinite(last.getTime())&&last.toLocaleDateString('en-CA',{timeZone:'Asia/Hong_Kong'})===value.date;
  const counted=Number.isFinite(last.getTime())?(sameDay?last.toLocaleTimeString('zh-CN',options):last.toLocaleString('zh-CN',{...options,month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit'})):null;
  node('token-updated').textContent=counted?`最近计数 ${counted} · ${updated}`:updated;
}
function renderQuota(value={}) {
  const messages={loading:'正在读取额度…',unknown:'暂未取得额度',cli_missing:'未找到 Codex CLI',not_logged_in:'Codex CLI 尚未登录',
    api_key_account:'API Key 登录不提供订阅额度',unsupported:'当前账号暂不支持额度读取',no_windows:'当前账号未返回额度窗口',
    network_error:'额度网络连接失败，将自动重试',timeout:'额度读取超时，将自动重试',unavailable:'额度暂时无法读取'};
  const buckets=value.buckets||{},bucket=buckets[value.bucket_id]||Object.values(buckets)[0];
  node('quota-bucket').textContent=bucket?.name||'';
  const container=node('quota-windows');container.replaceChildren();
  const detailContainer=node('quota-detail-windows');detailContainer.replaceChildren();
  const windows=Array.isArray(bucket?.windows)?bucket.windows.slice(0,2):[];
  node('quota-empty').hidden=windows.length>0;
  for(const item of windows){
    const remaining=Number.isFinite(item.remaining_percent)&&item.remaining_percent>=0&&item.remaining_percent<=100?item.remaining_percent:null;
    const row=document.createElement('div');row.className='quota-window';
    const line=document.createElement('div');line.className='total quota-number';
    const name=document.createElement('span');name.textContent=item.duration_minutes?item.name.replace(/（.*）$/,''):item.name||'额度窗口';
    const percent=document.createElement('strong');percent.textContent=remaining===null?'—':`${remaining}%`;
    percent.title=remaining===null?'剩余额度未知':`剩余 ${remaining}%`;
    line.append(percent,name);row.append(line);
    if(remaining!==null){const meter=document.createElement('meter');meter.min=0;meter.max=100;meter.value=remaining;meter.setAttribute('aria-label',`${name.textContent}剩余 ${remaining}%`);row.append(meter);}
    const reset=document.createElement('p');reset.className='quota-reset';
    const date=new Date(Number.isFinite(item.resets_at)?item.resets_at*1000:NaN);
    reset.textContent=Number.isFinite(date.getTime())?`重置 ${date.toLocaleString('zh-CN',{timeZone:'Asia/Hong_Kong',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hour12:false})} · 北京时间`:'重置时间未知';
    reset.textContent=`${name.textContent} · ${reset.textContent}`;
    detailContainer.append(reset);container.append(row);
  }
  const stamp=new Date(value.sampled_at||'');
  const updated=Number.isFinite(stamp.getTime())?` · 读取 ${stamp.toLocaleTimeString('zh-CN',{timeZone:'Asia/Hong_Kong',hour12:false})}`:'';
  const stale=Boolean(value.stale)||value.status!=='available';container.parentElement.dataset.stale=String(stale);
  node('quota-status').textContent=(value.status==='available'?(!windows.length?'当前账号未返回额度窗口':stale?'上次额度 · 等待刷新':'额度每 2 分钟更新'):
    `${messages[value.status]||'额度暂时无法读取'}${windows.length?' · 上次额度':''}`)+updated;
  node('quota-notice').hidden=value.status==='available'&&!stale&&windows.length>0;
  node('quota-notice').textContent=windows.length&&stale?'上次额度 · 等待刷新':messages[value.status]||'当前账号未返回额度窗口';
}
renderTokens();window.gorkDesktop?.onTokenUsage(renderTokens);
window.GorkTokenHover?.attach(document.querySelector('.token-card'),window.gorkDesktop);
window.gorkDesktop?.onTokenReset?.(()=>{node('token-details').open=false;});
if(typeof ResizeObserver!=='undefined'&&window.gorkDesktop?.setTokenHeight){
  let previous=0;
  new ResizeObserver(()=>{
    const height=Math.ceil(document.querySelector('.token-card').getBoundingClientRect().height+20);
    if(height!==previous){previous=height;window.gorkDesktop.setTokenHeight(height).catch(()=>{});}
  }).observe(document.querySelector('.token-card'));
}
