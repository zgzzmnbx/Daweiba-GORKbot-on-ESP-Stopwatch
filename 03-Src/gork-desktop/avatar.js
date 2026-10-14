const avatar = document.getElementById('avatar');
const status = document.getElementById('status');
if(window.gorkDesktop?.setTokenHover)window.GorkTokenHover?.attach(avatar,window.gorkDesktop);
const face = window.GorkDesktopSceneAdapter.mount(document.getElementById('gork-face'));
let pointerFollow = true;
const pointerLook = window.GorkDesktopPointer?.attach(document.getElementById('gork-face'), () => {
  const scene = face.getState();
  return pointerFollow && scene.kind === 'legacy' && ['idle', 'listening'].includes(scene.name)
    && ['idle', 'listening'].some(mode => avatar.classList.contains(mode));
});
let characterRevision = -1;
let sceneRevision = -1;
let appliedMotionRequestId = null;
const quotaOuter = document.getElementById('quota-ring-outer');
const quotaInner = document.getElementById('quota-ring-inner');
const quotaDetail = document.getElementById('quota-detail');
const quotaTooltip = document.getElementById('quota-tooltip');
const quotaTrend = document.getElementById('quota-trend');

function renderQuota(codex = {}) {
  const trend = codex.trend;
  quotaTrend.hidden = !trend;
  avatar.dataset.quotaDrop = trend ? 'true' : 'false';
  if (trend) {
    quotaTrend.textContent = `↓${trend.drop_points}点`;
    const detail = `${trend.window_name}额度下降 ${trend.drop_points} 个百分点，剩余 ${trend.remaining}%`;
    quotaTrend.title = detail;
    quotaTrend.setAttribute?.('aria-label', detail);
  }
  const windows = codex.enabled ? (codex.bucket?.windows || []) : [];
  const stale = codex.stale || codex.status !== 'available';
  const display = codex.ring_mode === 'hover' ? 'hover' : 'visible';
  quotaDetail.hidden = !codex.enabled;
  quotaDetail.dataset.display = display;
  [quotaOuter, quotaInner].forEach((ring, index) => {
    const value = windows[index]?.remaining_percent;
    ring.hidden = !windows[index];
    ring.dataset.display = display;
    ring.style?.setProperty('--ring-fill', Number.isFinite(value) && !stale ? `${Math.max(0, Math.min(100, value))}%` : '0%');
    ring.style?.setProperty('--ring-color', stale || !Number.isFinite(value) ? '#9b9d98' : value <= 20 ? '#c06a4d' : '#3f9e79');
  });
  const detail = windows.length ? windows.map((item, i) => {
    const remaining = item.remaining_percent == null ? '未知' : `${item.remaining_percent}%`;
    const reset = item.resets_at ? new Date(item.resets_at * 1000).toLocaleString() : '未知';
    return `${item.name || `窗口 ${i + 1}`} 剩余 ${remaining}，重置 ${reset}`;
  }).join('；') : '暂无可用额度窗口';
  const text = `当前监测账号额度：${detail}${stale ? '；数据过期或不可用' : ''}`;
  quotaDetail.title = text;
  quotaDetail.setAttribute?.('aria-label', text);
  quotaTooltip.textContent = text;
}

function render(state) {
  const follow = state.pointerFollow !== false;
  if (follow !== pointerFollow) {pointerFollow=follow;pointerLook?.reset();}
  renderQuota(state.codex);
  face.setAppearance?.(state.appearance);
  const next = ['idle', 'listening', 'thinking', 'happy', 'confused'].includes(state.mode) ? state.mode : 'idle';
  avatar.className = `avatar ${next}`;
  const scene = state.scene;
  if (scene && Number.isInteger(scene.revision)) {
    if (scene.revision !== sceneRevision) {
      sceneRevision = scene.revision;
      if(scene.custom){
        if(!Number.isInteger(scene.requestId)||scene.requestId!==appliedMotionRequestId){face.playCustom(scene.custom,{mode:scene.mode,startedAt:scene.startedAt});appliedMotionRequestId=scene.requestId;}
      }
      else face.set(scene.expression, {mode:scene.mode,startedAt:scene.startedAt,force:true});
    }
  } else {
  const manual = state.character || {};
  if (Number.isInteger(manual.revision) && manual.revision !== characterRevision && manual.manual) {
    characterRevision = manual.revision;
    if(manual.custom_motion)face.playCustom(manual.custom_motion,{mode:manual.mode});
    else face.set(manual.expression || 'idle', {mode:manual.mode,force:true});
  } else if (!manual.manual || characterRevision < 0) face.set(next);
  }
  status.textContent = state.label || '就绪';
}

document.getElementById('console').addEventListener('click', () => window.gorkDesktop.openConsole());
document.getElementById('hide').addEventListener('click', () => window.gorkDesktop.hideAvatar());
avatar.addEventListener('click', (event) => { if (!event.target.closest('button') && !event.target.closest('.drag-zone, #status')) window.gorkDesktop.openConsole(); });
if (window.gorkDesktop) {
  window.gorkDesktop.onMotionConfig?.(({record,scene,requestId})=>{try {face.playCustom(record,scene);appliedMotionRequestId=requestId;window.gorkDesktop.motionApplied({requestId,revision:record.revision,ok:true});}catch(error){window.gorkDesktop.motionApplied({requestId,ok:false,error:error.message});}});
  window.gorkDesktop.getState().then(render).catch(() => render({ mode: 'confused', label: '后端未就绪' }));
  window.gorkDesktop.onState(render);
} else {
  // Read-only visual preview; no device/voice connection outside the desktop shell.
  render({mode:'idle',label:'外观预览'});
  document.querySelector('.actions').hidden=true;
}
