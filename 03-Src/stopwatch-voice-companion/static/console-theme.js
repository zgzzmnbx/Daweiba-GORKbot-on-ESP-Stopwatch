/* Presentation only: never reload, replace controls, or touch session/device APIs. */
(function(root){
  const key='gork.console-theme',colorKey='gork.console-color',schemeKey='gork.console-scheme',valid=value=>value==='classic'?'classic':'mantine';
  const colors=new Set(['gork','blue','indigo','cyan','teal','violet']);
  const validColor=value=>colors.has(value)?value:'gork';
  function apply(value,remember=false){
    const theme=valid(value),doc=root.document;
    doc.documentElement.dataset.consoleTheme=theme;
    for(const [id,active] of [['classic-style',theme==='classic'],['classic-bridge',theme==='classic'],['mantine-style',theme==='mantine'],['mantine-components',theme==='mantine'],['modern-style',theme==='mantine']]){
      const link=doc.getElementById(id);if(link)link.media=active?'all':'not all';
    }
    const button=doc.getElementById('theme-toggle');
    if(button){button.textContent=theme==='mantine'?'经典主题':'Mantine 主题';button.setAttribute('aria-label',`切换为${theme==='mantine'?'经典':'Mantine'}主题`);button.title='仅切换外观，保留输入、聊天和连接';}
    doc.documentElement.dataset.mantineColorScheme=theme==='mantine'&&doc.documentElement.dataset.consoleScheme==='dark'?'dark':'light';
    if(remember)try{root.localStorage.setItem(key,theme);}catch{}
    return theme;
  }
  function applyScheme(value,remember=false){
    const scheme=value==='dark'?'dark':'light',doc=root.document;
    doc.documentElement.dataset.consoleScheme=scheme;
    doc.documentElement.dataset.mantineColorScheme=doc.documentElement.dataset.consoleTheme==='mantine'?scheme:'light';
    const button=doc.getElementById('color-scheme-toggle');
    if(button){const label=button.querySelector('.tool-label');if(label)label.textContent=scheme==='dark'?'浅色模式':'暗色模式';else button.textContent=scheme==='dark'?'浅色模式':'暗色模式';button.dataset.icon=scheme==='dark'?'sun':'moon';button.title=`切换为${scheme==='dark'?'浅色':'暗色'}模式`;button.setAttribute('aria-label',`切换为${scheme==='dark'?'浅色':'暗色'}模式`);button.setAttribute('aria-pressed',String(scheme==='dark'));}
    if(remember)try{root.localStorage.setItem(schemeKey,scheme);}catch{}
    return scheme;
  }
  function applyColor(value,remember=false){
    const color=validColor(value),doc=root.document;
    doc.documentElement.dataset.consoleColor=color;
    const selected=doc.querySelector(`input[name="console-color"][value="${color}"]`);
    if(selected)selected.checked=true;
    if(remember)try{root.localStorage.setItem(colorKey,color);}catch{}
    return color;
  }
  let initial,initialColor,initialScheme;try{initial=root.localStorage.getItem(key);initialColor=root.localStorage.getItem(colorKey);initialScheme=root.localStorage.getItem(schemeKey);}catch{}
  apply(initial);
  applyScheme(initialScheme);
  applyColor(initialColor);
  root.document.addEventListener('DOMContentLoaded',()=>{
    apply(root.document.documentElement.dataset.consoleTheme);
    applyScheme(root.document.documentElement.dataset.consoleScheme);
    applyColor(root.document.documentElement.dataset.consoleColor);
    root.document.getElementById('theme-toggle')?.addEventListener('click',()=>apply(root.document.documentElement.dataset.consoleTheme==='mantine'?'classic':'mantine',true));
    root.document.getElementById('color-scheme-toggle')?.addEventListener('click',()=>{
      applyScheme(root.document.documentElement.dataset.consoleScheme==='dark'?'light':'dark',true);
      if(root.document.documentElement.dataset.consoleTheme==='classic')apply('mantine',true);
    });
    const menu=root.document.getElementById('theme-color-menu');
    menu?.addEventListener('change',event=>{
      if(event.target?.name!=='console-color')return;
      applyColor(event.target.value,true);
      if(root.document.documentElement.dataset.consoleTheme==='classic')apply('mantine',true);
      menu.open=false;
    });
    root.document.addEventListener('click',event=>{if(menu?.open&&!menu.contains(event.target))menu.open=false;});
    menu?.addEventListener('keydown',event=>{if(event.key==='Escape'){menu.open=false;menu.querySelector('summary')?.focus();}});
  },{once:true});
})(window);
