const codexKeys=['enabled','mode','thread_id','target','sound','sound_target','threshold','bucket_id','ring_mode','drop_step','drop_animation'];
export function createHeaderTools({document,api,acquireWorkspace,hasWorkspace,onCodex,refreshExternal,report}){
  const external=document.getElementById('header-notifications'),codex=document.getElementById('header-codex');
  let externalState=null,codexState=null,externalBusy=false,codexBusy=false;
  function paint(button,enabled,busy,title){
    button.disabled=busy||enabled===null;
    button.setAttribute('aria-checked',String(enabled===true));
    button.setAttribute('aria-busy',String(busy));
    button.dataset.known=String(enabled!==null);
    button.title=title;
    button.setAttribute('aria-label',title);
  }
  function render(){
    const enabled=externalState===null?null:!externalState.paused;
    paint(external,enabled,externalBusy,enabled===null?'通知哨兵：等待读取':`通知哨兵（程序推送）：${enabled?'接收中，点击暂停':'已暂停，点击恢复'}`);
    paint(codex,codexState===null?null:codexState.enabled===true,codexBusy,codexState===null?'Codex 哨兵：等待读取':`Codex 哨兵：${codexState.enabled?'已开启，点击关闭':'已关闭，点击开启'}`);
  }
  external.onclick=async()=>{
    if(externalBusy||externalState===null)return;
    externalBusy=true;render();
    try{
      if(!hasWorkspace()&&!await acquireWorkspace())throw Error('请先取得工作台控制权。');
      const result=await api(`/external/${externalState.paused?'resume':'pause'}`,'POST');
      externalState={...externalState,paused:result.paused};
      report(result.paused?'程序通知已暂停；各程序的授权保持。':'程序通知已恢复；旧通知不会补播。');
      await refreshExternal();
    }catch(error){report(error.message,true);}
    finally{externalBusy=false;render();}
  };
  codex.onclick=async()=>{
    if(codexBusy||codexState===null)return;
    codexBusy=true;render();
    try{
      if(!hasWorkspace()&&!await acquireWorkspace())throw Error('请先取得工作台控制权。');
      // Read the saved settings, rather than committing a form's unsaved edits.
      const current=await api('/codex/sentinel');
      const values=Object.fromEntries(codexKeys.filter(k=>k in current).map(k=>[k,current[k]]));
      values.enabled=current.enabled!==true;
      codexState=await api('/codex/sentinel','PUT',values);onCodex(codexState);
      report(codexState.enabled?'Codex 哨兵已开启。':'Codex 哨兵已关闭。');
    }catch(error){report(error.message,true);}
    finally{codexBusy=false;render();}
  };
  render();
  return {paintExternal(data){externalState=data;render();},paintCodex(data){codexState=data;render();}};
}
