(function(root,factory){const api=factory();if(typeof module==='object')module.exports=api;else root.GorkIndicators=api;})(this,function(){
  const keys=['vpn','quota','tokens','network','proxy'];
  const defaults={mode:'bubbles',items:['quota','tokens','proxy']};
  function normalize(value){return {mode:value?.mode==='menu'?'menu':'bubbles',items:Array.isArray(value?.items)?keys.filter(k=>value.items.includes(k)):[...defaults.items]};}
  function valid(value){return value&&['menu','bubbles'].includes(value.mode)&&Array.isArray(value.items)&&value.items.length<=5&&new Set(value.items).size===value.items.length&&value.items.every(k=>keys.includes(k));}
  function compact(value,base=1000){if(!Number.isFinite(value)||value<0)return '—';let i=0;while(value>=base&&i<4){value/=base;i++;}return `${i?value.toFixed(value<10?2:1):Math.round(value)}${['','K','M','G','T'][i]}`;}
  function rows(settings,data={}){
    const traffic=data.traffic||{},physical=traffic.physical||{},clash=traffic.clash||{},latest=clash.latest||{};
    const token=data.tokens||{},quota=data.quota||{},bucket=quota.buckets?.[quota.bucket_id]||Object.values(quota.buckets||{})[0];
    const windows=(bucket?.windows||[]).filter(w=>Number.isFinite(w.remaining_percent)&&w.remaining_percent>=0&&w.remaining_percent<=100);
    const limiting=windows.reduce((a,b)=>!a||b.remaining_percent<a.remaining_percent?b:a,null);
    const known=value=>value?.status==='available'&&!value.stale;
    const sum=(a,b)=>Number.isFinite(a)&&a>=0&&Number.isFinite(b)&&b>=0?a+b:NaN;
    const speed=(name,up,down,ok)=>({text:ok&&Number.isFinite(sum(up,down))?`${compact(sum(up,down),1024)}/s`:'—',title:`${name} · 收发合计；下载 ${compact(down,1024)}B/s，上传 ${compact(up,1024)}B/s。K/M/G 按 1024 换算。${ok?'':'监测未开启或数据不可用。'}`});
    const proxy=clash.routes?.PROXY;
    const values={
      vpn:{text:traffic.enabled&&known(clash)&&proxy&&Number.isFinite(sum(proxy.upload,proxy.download))?compact(sum(proxy.upload,proxy.download),1024)+'B':'—',title:'今日 VPN / 代理累计收发量 · Gork 监测到的 Clash 代理增量，非套餐总用量；K/M/G 按 1024 换算。'},
      quota:{text:known(quota)&&limiting?`${Math.round(limiting.remaining_percent)}%`:'—',title:known(quota)&&limiting?`Codex 剩余额度 · ${limiting.name||'额度窗口'}；多个窗口显示最低剩余比例。${windows.map(w=>`${w.name}: ${w.remaining_percent}%`).join('；')}`:'Codex 剩余额度 · 正在读取、已过期或不可用'},
      tokens:{text:known(token)?compact(token.total_tokens):'—',title:'Codex 今日 token · CC Switch 本机统计，含缓存；K/M/G 按 1000 换算。'+(known(token)?'':'正在读取、已过期或不可用。')},
      network:speed('普通网速（整机物理网卡，含代理）',physical.up_speed,physical.down_speed,traffic.enabled&&known(physical)),
      proxy:speed('代理网速',latest.proxy_up_speed,latest.proxy_down_speed,traffic.enabled&&known(clash))
    };
    return normalize(settings).items.filter(key=>traffic.enabled===true||!['vpn','network','proxy'].includes(key)).map(key=>({key,...values[key]}));
  }
  return {keys,defaults,normalize,valid,rows};
});
