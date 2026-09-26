/* Presentation only: never reload, replace controls, or touch session/device APIs. */
(function(root){
  const key='gork.console-theme',valid=value=>value==='classic'?'classic':'mantine';
  function apply(value,remember=false){
    const theme=valid(value),doc=root.document;
    doc.documentElement.dataset.consoleTheme=theme;
    for(const [id,active] of [['classic-style',theme==='classic'],['classic-bridge',theme==='classic'],['mantine-style',theme==='mantine'],['mantine-components',theme==='mantine'],['modern-style',theme==='mantine']]){
      const link=doc.getElementById(id);if(link)link.media=active?'all':'not all';
    }
    const button=doc.getElementById('theme-toggle');
    if(button){button.textContent=theme==='mantine'?'经典主题':'Mantine 主题';button.setAttribute('aria-label',`切换为${theme==='mantine'?'经典':'Mantine'}主题`);button.title='仅切换外观，保留输入、聊天和连接';}
    if(remember)try{root.localStorage.setItem(key,theme);}catch{}
    return theme;
  }
  let initial;try{initial=root.localStorage.getItem(key);}catch{}
  apply(initial);
  root.document.addEventListener('DOMContentLoaded',()=>{
    apply(root.document.documentElement.dataset.consoleTheme);
    root.document.getElementById('theme-toggle')?.addEventListener('click',()=>apply(root.document.documentElement.dataset.consoleTheme==='mantine'?'classic':'mantine',true));
  },{once:true});
})(window);
