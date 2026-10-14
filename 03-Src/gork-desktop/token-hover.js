(function(root){
  function attach(avatar,bridge) {
    let timer=null,hover=false,disposed=false;
    function send(value){if(disposed||hover===value)return;hover=value;bridge.setTokenHover(value).catch(()=>{});}
    function enter(){clearTimeout(timer);send(true);}
    function leave(){clearTimeout(timer);timer=setTimeout(()=>send(false),150);}
    function hide(){clearTimeout(timer);send(false);}
    function focusOut(e){if(!avatar.contains(e.relatedTarget))leave();}
    function key(e){if(e.key==='Escape'){hide();bridge.hideTokenCard?.().catch(()=>{});}}
    avatar.addEventListener('pointerenter',enter);avatar.addEventListener('pointermove',enter);avatar.addEventListener('pointerleave',leave);
    avatar.addEventListener('focusin',enter);avatar.addEventListener('focusout',focusOut);
    avatar.addEventListener('keydown',key);
    const visibility=()=>{if(root.document.hidden)hide();};
    root.document.addEventListener('visibilitychange',visibility);
    const unsubscribe=bridge.onTokenReset?.(hide);
    function dispose(){hide();disposed=true;
      avatar.removeEventListener('pointerenter',enter);avatar.removeEventListener('pointermove',enter);avatar.removeEventListener('pointerleave',leave);
      avatar.removeEventListener('focusin',enter);avatar.removeEventListener('focusout',focusOut);
      avatar.removeEventListener('keydown',key);root.document.removeEventListener('visibilitychange',visibility);
      root.removeEventListener('pagehide',dispose);
      unsubscribe?.();
    }
    root.addEventListener('pagehide',dispose,{once:true});return {dispose};
  }
  root.GorkTokenHover={attach};
})(window);
