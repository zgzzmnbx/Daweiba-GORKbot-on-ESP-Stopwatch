const labels = {idle:'待机',happy:'开心',laughing:'大笑',excited:'兴奋',curious:'好奇',surprised:'惊讶',thinking:'思考',listening:'聆听',sleeping:'睡觉',waking:'醒来',searching:'搜索',working:'工作',bored:'无聊',suspicious:'怀疑',angry:'生气',drowsy:'困倦',confused:'疑惑',proud:'得意',shy:'害羞',sad:'难过',scared:'害怕',playful:'俏皮',celebrate:'庆祝'};

// Thumbnails and hover animation use the same pinned catalog as the actual robot.
export function createExpressionMenu(document, {catalog, renderer, send}) {
  const get = id => document.getElementById(id);
  const details = get('expression-menu'), grid = get('expression-grid');
  const target = get('expression-target'), mode = get('expression-mode'), feedback = get('expression-feedback');
  const cards = [];
  let appearance;
  let live = null, busy = false, blocked = '', watchConnected = false, built = false, lastReason = '';
  target.value = 'desktop'; mode.value = 'once';
  function stopPreview() { live?.dispose(); live = null; }
  const previewAppearance=()=>target.value==='watch'?{id:'gork'}:appearance;
  function still(card) { renderer?.mount(card.canvas, catalog, {still:true,expression:card.name,appearance:previewAppearance()}).dispose(); }
  function update() {
    const reason = busy ? '正在发送，请稍候。' : blocked || (target.value !== 'desktop' && !watchConnected ? 'Watch 未连接，请先在 StopWatch 页连接。' : '');
    for (const card of cards) {
      card.button.disabled = busy;
      card.button.setAttribute('aria-disabled', String(Boolean(reason)));
      card.button.title = reason || `${labels[card.name] || card.name}：悬停预览，点击发送`;
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
    for (const name of Object.keys(labels).filter(name => names.has(name))) {
      const button = document.createElement('button'), canvas = document.createElement('canvas'), label = document.createElement('span');
      button.type = 'button'; button.className = 'expression-tile'; button.setAttribute('aria-label', `播放${labels[name]}`);
      canvas.setAttribute('aria-hidden','true'); label.textContent = labels[name];
      button.append(canvas,label); grid.append(button);
      const card = {name,button,canvas}; cards.push(card);
      const preview = () => {
        stopPreview();
        if (!details.open) return;
        live = renderer?.mount(canvas,catalog,{appearance:previewAppearance(),idleMotion:target.value!=='watch'}); live?.set(name,{mode:'loop',force:true});
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
    if(event.key==='Escape') { details.open=false; stopPreview(); details.querySelector('summary')?.focus(); }
  });
  for (const select of [target,mode]) select.addEventListener('change',()=>{
    stopPreview();if(details.open)cards.forEach(still);
    feedback.textContent='选择目标，再点击表情。待机可结束循环。'; update();
  });
  return {setAppearance(value){appearance=value;stopPreview();if(details.open)cards.forEach(still);},update(state) { blocked=state.blocked || ''; watchConnected=state.watchConnected; update(); },dispose:stopPreview};
}
