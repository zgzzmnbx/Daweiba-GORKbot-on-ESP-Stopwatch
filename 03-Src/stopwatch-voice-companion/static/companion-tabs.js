/* Shared companion panels; switching does not reconnect or rebuild their state. */
(function(){
  const tabs=[...document.querySelectorAll('[data-companion-tab]')];
  if(tabs.length!==2)return;
  const menu=document.getElementById('expression-menu'),log=document.getElementById('debug-log');
  let active,logTop=0,followLog=true,storage;
  try{storage=window.localStorage;}catch{}
  function select(name,focus=false){
    if(!['expressions','logs'].includes(name))name='expressions';
    if(active==='logs'&&name!=='logs'){
      logTop=log.scrollTop;followLog=log.scrollHeight-log.scrollTop-log.clientHeight<32;
    }
    for(const tab of tabs){
      const selected=tab.dataset.companionTab===name;
      tab.setAttribute('aria-selected',String(selected));tab.tabIndex=selected?0:-1;
      document.getElementById(tab.getAttribute('aria-controls')).hidden=!selected;
      if(selected&&focus)tab.focus();
    }
    menu.open=name==='expressions';active=name;
    if(name==='logs')requestAnimationFrame(()=>{if(active==='logs')log.scrollTop=followLog?log.scrollHeight:logTop;});
    try{storage?.setItem('gork.companion-tab',name);}catch{}
  }
  for(const [index,tab] of tabs.entries()){
    tab.addEventListener('click',()=>select(tab.dataset.companionTab));
    tab.addEventListener('keydown',event=>{
      const next=event.key==='Home'?0:event.key==='End'?1:
        ['ArrowLeft','ArrowRight'].includes(event.key)?1-index:null;
      if(next!==null){event.preventDefault();select(tabs[next].dataset.companionTab,true);}
    });
  }
  let saved;try{saved=storage?.getItem('gork.companion-tab');}catch{}
  select(saved);
})();
