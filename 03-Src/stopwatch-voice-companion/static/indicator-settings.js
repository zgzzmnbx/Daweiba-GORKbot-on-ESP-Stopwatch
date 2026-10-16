(function(){
  const mode=document.getElementById('desktop-indicator-mode'),box=document.getElementById('desktop-indicator-items'),hint=document.getElementById('desktop-indicator-hint'),preview=document.getElementById('desktop-indicator-preview'),retry=document.getElementById('desktop-indicator-retry');
  const inputs=[...box.querySelectorAll('input')],bridge=window.gorkDesktop;
  let saved=null,busy=false;
  function paint(){
    mode.disabled=busy||!saved;box.disabled=busy||!saved||saved.mode==='menu';
    retry.disabled=busy||!bridge?.getIndicatorSettings;
    if(saved){mode.value=saved.mode;inputs.forEach(input=>input.checked=saved.items.includes(input.value));}
    preview.hidden=!saved||saved.mode!=='bubbles';
    preview.querySelectorAll('[data-metric]').forEach(item=>item.hidden=!saved?.items.includes(item.dataset.metric));
  }
  async function load(){
    if(!bridge?.getIndicatorSettings){hint.textContent='请在最新版桌面客户端中设置。';paint();return;}
    busy=true;paint();
    try{saved=await bridge.getIndicatorSettings();hint.textContent='选择后自动保存并立即生效。全部取消可只保留小人。';}
    catch{hint.textContent='读取失败，请重试；旧版客户端需正常退出后重新打开。';}
    finally{busy=false;paint();}
  }
  async function save(){
    if(busy||!saved)return;
    const next={mode:mode.value,items:inputs.filter(input=>input.checked).map(input=>input.value)};
    busy=true;paint();
    try{saved=await bridge.setIndicatorSettings(next);hint.textContent='已保存，桌面小人已更新。';}
    catch{hint.textContent='保存失败，已恢复上次设置；请重试。';}
    finally{busy=false;paint();}
  }
  mode.addEventListener('change',save);inputs.forEach(input=>input.addEventListener('change',save));retry.addEventListener('click',load);
  void load();
})();
