export function bytes(value){
  if(!Number.isFinite(value))return '—';
  const sign=value<0?'-':'';value=Math.abs(value);
  const units=['B','KiB','MiB','GiB','TiB'];let i=0;
  while(value>=1024&&i<units.length-1){value/=1024;i++;}
  return `${sign}${value.toFixed(i?1:0)} ${units[i]}`;
}
export function createTrafficUI({document,api,acquireWorkspace,hasWorkspace,report}){
  const $=id=>document.getElementById(id),button=$('header-traffic');
  let state=null,busy=false,timer=null,inflight=false,disposed=false,revision=0;
  const status={available:'正在采集',baseline:'建立基线',connecting:'正在连接',disabled:'已关闭',unavailable:'暂不可用',stale:'旧值 · 等待更新',partial:'部分可用',unknown:'等待读取'};
  function rate(value){return Number.isFinite(value)?`${bytes(value)}/s`:'—';}
  function controls(){
    button.disabled=busy||state===null;button.setAttribute('aria-checked',String(state?.enabled===true));
    button.title=button.ariaLabel=`流量监测：${state===null?'等待读取':state.enabled?'已开启，点击关闭':'已关闭，点击开启'}`;
    button.setAttribute('aria-busy',String(busy));
  }
  function render(value){
    state=value;controls();
    const n=value.physical||{},c=value.clash||{},latest=c.latest||{},fresh=c.status==='available';
    $('traffic-status').textContent=value.enabled?'每秒采样 · 本机保存':'采集已关闭；点击标题栏流量开关开启。';
    $('traffic-physical-status').textContent=status[n.status]||'未知';
    $('traffic-proxy-status').textContent=status[c.status]||'未知';
    $('traffic-physical-down').textContent=rate(n.status==='available'?n.down_speed:null);
    $('traffic-physical-up').textContent=rate(n.status==='available'?n.up_speed:null);
    $('traffic-proxy-down').textContent=rate(fresh?latest.proxy_down_speed:null);
    $('traffic-proxy-up').textContent=rate(fresh?latest.proxy_up_speed:null);
    for(const [id,key] of [['proxy','PROXY'],['direct','DIRECT']]){
      const r=c.routes?.[key];$('traffic-total-'+id).textContent=r?bytes(r.upload+r.download):'—';
    }
    $('traffic-difference').textContent=c.difference?`未归属差额：↑ ${bytes(c.difference.upload)} / ↓ ${bytes(c.difference.download)}。`:'尚无 Clash 采样。';
    $('traffic-history-status').textContent=value.history?`${status[value.history.status]||'未知'}${value.history.updated_at?' · 读取于 '+new Date(value.history.updated_at*1000).toLocaleString('zh-CN'):''}；每 15 分钟读取，Windows 记账本身有延迟。`:'等待读取';
    table();
  }
  function table(){
    if(!state)return;
    const view=$('traffic-view').value,query=$('traffic-search').value.trim().toLowerCase();
    const windows=view==='windows',connections=view==='connections';
    const rows=windows?(state.history?.rows||[]):state[view]||[];
    $('traffic-col-name').textContent=windows?'Windows 应用':connections?'进程 / 目标':view==='domains'?'域名':'Clash 进程';
    $('traffic-col-route').textContent=windows?'统计日期':connections?'线路':'代理 / DIRECT';
    const body=$('traffic-rows');body.replaceChildren();
    const filtered=rows.filter(r=>(r.name||`${r.process} ${r.destination}`).toLowerCase().includes(query));
    for(const row of filtered.slice(0,150)){
      const tr=document.createElement('tr');
      const values=[row.name||`${row.process} · ${row.destination}`,bytes(row.upload),bytes(row.download),
        windows?row.day:connections?row.route:`${bytes(row.proxy)} / ${bytes(row.direct)}`];
      for(const value of values){const td=document.createElement('td');td.textContent=value;tr.append(td);}body.append(tr);
    }
    if(!filtered.length){const tr=document.createElement('tr'),td=document.createElement('td');td.colSpan=4;td.textContent='当前没有可显示的记录。';tr.append(td);body.append(tr);}
    $('traffic-table-count').textContent=`显示 ${Math.min(150,filtered.length)} 条${filtered.length>150?'（按流量排序，最多 150 条）':''}`;
  }
  async function poll(){
    clearTimeout(timer);if(disposed||document.hidden||inflight)return;
    inflight=true;const rev=revision;
    try{const value=await api('/traffic?details=true');if(!disposed&&rev===revision&&!busy)render(value);}
    catch{if(!disposed&&rev===revision&&!busy){state=null;controls();$('traffic-status').textContent='流量模块连接失败；请确认新版后台已重开。';for(const id of ['physical-down','physical-up','proxy-down','proxy-up'])$('traffic-'+id).textContent='—';}}
    finally{inflight=false;if(!disposed&&!document.hidden)timer=setTimeout(poll,document.defaultView.location.hash==='#traffic'?1000:5000);}
  }
  button.onclick=async()=>{
    if(busy||state===null)return;busy=true;revision++;controls();
    try{
      if(!hasWorkspace()&&!await acquireWorkspace())throw Error('请先取得工作台控制权。');
      const result=await api('/traffic','PUT',{enabled:!state.enabled});
      render({...state,...result});report(result.enabled?'流量监测已开启。':'流量监测已关闭，记录已保留。');
    }catch(e){report(e.message,true);}
    finally{busy=false;controls();poll();}
  };
  $('traffic-search').oninput=table;$('traffic-view').onchange=table;
  const visibility=()=>{revision++;clearTimeout(timer);if(!document.hidden)poll();};
  const navigate=()=>poll();
  function dispose(){disposed=true;revision++;clearTimeout(timer);document.removeEventListener('visibilitychange',visibility);document.defaultView.removeEventListener('hashchange',navigate);}
  document.addEventListener('visibilitychange',visibility);document.defaultView.addEventListener('hashchange',navigate);
  document.defaultView.addEventListener('pagehide',dispose,{once:true});poll();
  return {render,dispose};
}
