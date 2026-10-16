const states={queued:'排队中',dispatching:'输出中',active:'显示中',completed:'已完成',partial:'部分完成',failed:'失败',cancelled:'已取消',superseded:'已替换',expired:'已过期',interrupted:'重启中断'};
const rank={queued:0,dispatching:1,active:2,partial:3,completed:4,failed:4,cancelled:4,superseded:4,expired:4,interrupted:4};

// Read existing receipts only. Rendering a receipt never dispatches it again.
export function createNoticeChat(write,now=()=>Date.now()) {
  const seen=new Map();let clearedAt=-Infinity;
  return {
    consume(data){
      const labels=new Map((data.clients||[]).map(c=>[c.source,c.label]));
      for(const receipt of [...(data.receipts||[])].reverse()){
        const {source,event_id,status,accepted_at}=receipt;
        if(!source||!event_id)continue;
        const stamp=Date.parse(accepted_at);
        if(!Number.isFinite(stamp)||stamp<=clearedAt)continue;
        const text=receipt.request?.text||receipt.request?.speech?.text;
        if(typeof text!=='string'||!text.trim())continue;
        const id=`notice:${source}:${event_id}`,previous=seen.get(id);
        const signature=JSON.stringify([text,status,labels.get(source)]);
        if(previous&&(previous.signature===signature||(rank[status]??0)<previous.rank))continue;
        seen.set(id,{signature,rank:rank[status]??0});
        const time=new Date(stamp).toLocaleTimeString('zh-CN',{hour12:false});
        write('assistant',text,{id,kind:'notice',source:labels.get(source)||source,
          tag:['astra','legacy','zhisuan-astra','guankanzhisuan'].includes(source)?'造价智算信息':'',
          timing:`${time} · ${states[status]||'状态未知'}`});
      }
    },
    clear(){clearedAt=now();seen.clear();}
  };
}
