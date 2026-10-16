(function(){
  const badge=document.getElementById('traffic-badge'),avatar=document.getElementById('avatar');
  function bytes(n){if(!Number.isFinite(n))return '—';let i=0;const u=['B','K','M','G','T'];while(n>=1024&&i<4){n/=1024;i++;}return `${n.toFixed(i?1:0)}${u[i]}`;}
  function render(data){
    badge.hidden=!data?.enabled;avatar.dataset.traffic=String(!badge.hidden);if(badge.hidden)return;
    const n=data.physical||{},c=data.clash||{},l=c.latest||{},r=c.routes?.PROXY;
    document.getElementById('traffic-nic').textContent=n.status==='available'?`网 ↓${bytes(n.down_speed)} ↑${bytes(n.up_speed)}/s`:'网速 —';
    document.getElementById('traffic-proxy').textContent=c.status==='available'?`代理 ↓${bytes(l.proxy_down_speed)} ↑${bytes(l.proxy_up_speed)}/s`:'代理 —';
    document.getElementById('traffic-today').textContent=`今日代理 ${r?bytes(r.upload+r.download):'—'}`;
    badge.title='物理网卡与 Clash 代理采样速度；K/M 为 KiB/MiB。今日代理为 Gork 监测增量。打开控制台查看明细。';
  }
  const unsubscribe=window.gorkDesktop?.onTraffic(render);
  badge.addEventListener('click',()=>window.gorkDesktop?.openConsole());
  window.addEventListener('pagehide',()=>unsubscribe?.(),{once:true});
})();
