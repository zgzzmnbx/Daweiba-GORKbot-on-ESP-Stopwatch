const labels = {idle:'待机',happy:'开心',laughing:'大笑',excited:'兴奋',curious:'好奇',surprised:'惊讶',thinking:'思考',listening:'聆听',sleeping:'睡觉',waking:'醒来',searching:'搜索',working:'工作',bored:'无聊',suspicious:'怀疑',angry:'生气',drowsy:'困倦',confused:'疑惑',proud:'得意',shy:'害羞',sad:'难过',scared:'害怕',playful:'俏皮',celebrate:'庆祝'};

// Thumbnails and hover animation use the same pinned catalog as the actual robot.
export function createExpressionMenu(document, {catalog, renderer, motion, send}) {
  const get = id => document.getElementById(id);
  const details = get('expression-menu'), grid = get('expression-grid');
  const target = get('expression-target'), mode = get('expression-mode'), feedback = get('expression-feedback');
  const cards = [];
  let appearance;
  let customEntries = [];
  let live = null, busy = false, blocked = '', watchConnected = false, built = false, lastReason = '';
  target.value = 'both'; mode.value = 'once';
  function stopPreview() { live?.dispose(); live = null; }
  const previewAppearance=()=>target.value==='watch'?{id:'gork'}:appearance;
  function still(card) { if(card.entry)motion?.mount(card.canvas,card.entry,{still:true}).dispose();else renderer?.mount(card.canvas, catalog, {still:true,expression:card.name,appearance:previewAppearance()}).dispose(); }
  function update() {
    const reason = busy ? '正在发送，请稍候。' : blocked || (target.value === 'watch' && !watchConnected ? 'Watch 未连接，请先在 StopWatch 页连接。' : '');
    for (const card of cards) {
      card.button.disabled = busy;
      const cardReason=reason;
      card.button.setAttribute('aria-disabled', String(Boolean(cardReason)));
      card.button.title = cardReason || `${card.entry?.name || labels[card.name] || card.name}：悬停预览，点击发送`;
    }
    target.disabled = mode.disabled = busy;
    if (reason) feedback.textContent = reason;
    else if (feedback.textContent === lastReason) feedback.textContent = '选择目标，再点击表情。待机可结束循环。';
    lastReason = reason;
    return reason;
  }
  function build() {
    if (built) return;
    built = true;
    const names = new Set((catalog?.sequences || []).map(item => item.id));
    for (const entry of [...Object.keys(labels).filter(name => names.has(name)).map(id=>({id,builtin:true})),...customEntries]) {
      const name=entry.id, title=entry.builtin?labels[name]:entry.name;
      const button = document.createElement('button'), canvas = document.createElement('canvas'), label = document.createElement('span');
      button.type = 'button'; button.className = 'expression-tile'; button.setAttribute('aria-label', `播放${title}`);button.dataset.expression=name;
      canvas.setAttribute('aria-hidden','true'); label.textContent = entry.builtin?title:title+' · 自定义';
      button.append(canvas,label); grid.append(button);
      const card = {name,button,canvas,entry:entry.builtin?null:entry}; cards.push(card);
      const preview = () => {
        stopPreview();
        if (!details.open) return;
        if(card.entry)live=motion?.mount(canvas,card.entry);
        else{live = renderer?.mount(canvas,catalog,{appearance:previewAppearance(),idleMotion:target.value!=='watch'}); live?.set(name,{mode:'loop',force:true});}
      };
      button.addEventListener('pointerenter',preview); button.addEventListener('focus',preview);
      button.addEventListener('pointerleave',()=>{stopPreview();still(card);});
      button.addEventListener('blur',()=>{stopPreview();still(card);});
      button.onclick = async () => {
        if (update()) return;
        busy = true; update();
        try { feedback.textContent = await send(name,target.value,mode.value); }
        catch (error) { feedback.textContent = error.name === 'AbortError' ? '操作已取消。' : error.message; }
        finally { busy = false; update(); }
      };
    }
  }
  details.addEventListener('toggle',()=>{
    stopPreview();
    if (details.open) { build(); cards.forEach(still); update(); }
  });
  details.addEventListener('keydown',event=>{
    if(event.key==='Escape') {
      stopPreview();
      if(details.closest?.('[role=tabpanel]'))document.querySelector('[data-companion-tab][aria-selected=true]')?.focus();
      else{details.open=false;details.querySelector('summary')?.focus();}
    }
  });
  for (const select of [target,mode]) select.addEventListener('change',()=>{
    stopPreview();if(details.open)cards.forEach(still);
    feedback.textContent='选择目标，再点击表情。待机可结束循环。'; update();
  });
  if(details.open){build();cards.forEach(still);update();}
  return {setCustomEntries(values){customEntries=values||[];stopPreview();built=false;cards.length=0;grid.replaceChildren();if(details.open){build();cards.forEach(still);update();}},setAppearance(value){appearance=value;stopPreview();if(details.open)cards.forEach(still);},update(state) { blocked=state.blocked || ''; watchConnected=state.watchConnected; update(); },dispose:stopPreview};
}
