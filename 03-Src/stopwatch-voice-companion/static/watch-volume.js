/* One device writer for the header and StopWatch page; no guessed readback. */
export function createWatchVolume({document,api,report}){
  const $=id=>document.getElementById(id);
  const inputs=[$('header-watch-volume'),$('sound-volume')];
  const labels=[$('header-watch-volume-label'),$('sound-volume-label')];
  const hints=[$('header-watch-volume-hint'),$('sound-volume-hint')];
  let state={connected:false,owned:false,busy:false,route:''},confirmed=null,draft=null,saving=false,revision=0,failed=false;
  const allowed=()=>state.connected&&state.owned&&!state.busy&&!saving;
  function paint(){
    const value=draft??confirmed;
    const hint=!state.connected?'Watch 未连接。':!state.owned?'请先取得工作台控制权。':saving?'正在应用到 Watch…':state.busy?'音频任务进行中，请结束后调节。':
      failed?'提交未确认，请重试；设备当前值未知。':draft!==null?'松开滑块后应用到 Watch。':confirmed!==null?'本次已确认；与 StopWatch 页同步。':'设备当前值未读取，拖动后设置。';
    for(let i=0;i<inputs.length;i++){
      const input=inputs[i];input.disabled=!allowed();
      input.value=String(value??20);
      input.setAttribute('aria-valuetext',value===null?'Watch 当前音量未知，拖动可设置':`Watch 音量 ${value}%${draft!==null?'，待确认':''}`);
      labels[i].textContent=value===null?'—':`${value}%`;
      hints[i].textContent=hint;
    }
  }
  async function save(input){
    if(!allowed()){paint();return;}
    const value=Number(input.value);
    if(!Number.isInteger(value)||value<0||value>100){draft=null;paint();return;}
    if(value===confirmed){draft=null;paint();return;}
    const mine=revision;saving=true;draft=value;failed=false;paint();
    try{
      await api('/device/sound/volume','PUT',{volume:value});
      if(mine!==revision)return;
      confirmed=value;draft=null;
      report(`Watch 输出音量已确认：${value}%。`);
    }catch{
      if(mine!==revision)return;
      confirmed=null;draft=null;failed=true;
      report('Watch 音量未确认，请检查连接后重试。',true);
    }finally{saving=false;paint();}
  }
  for(const input of inputs){
    input.oninput=()=>{if(!allowed()){paint();return;}draft=Number(input.value);failed=false;paint();};
    input.onchange=()=>save(input);
  }
  paint();
  return {update(next){
    if(state.connected!==next.connected||state.owned!==next.owned||state.route!==next.route){revision++;confirmed=null;draft=null;failed=false;}
    state=next;paint();
  }};
}
