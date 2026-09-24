const avatar = document.getElementById('avatar');
const status = document.getElementById('status');
const bubble = document.getElementById('bubble');
const face = window.GorkAvatar.mount(document.getElementById('gork-face'));
let characterRevision = -1;
let sceneRevision = -1;

function render(state) {
  const next = ['idle', 'listening', 'thinking', 'happy', 'confused'].includes(state.mode) ? state.mode : 'idle';
  avatar.className = `avatar ${next}`;
  const scene = state.scene;
  if (scene && Number.isInteger(scene.revision)) {
    if (scene.revision !== sceneRevision) {
      sceneRevision = scene.revision;
      face.set(scene.expression, {mode:scene.mode,startedAt:scene.startedAt,force:true});
    }
  } else {
  const manual = state.character || {};
  if (Number.isInteger(manual.revision) && manual.revision !== characterRevision && manual.manual) {
    characterRevision = manual.revision;
    face.set(manual.expression || 'idle', {mode:manual.mode,force:true});
  } else if (!manual.manual || characterRevision < 0) face.set(next);
  }
  bubble.textContent = manual.bubble || '';
  bubble.hidden = !manual.bubble;
  status.textContent = state.label || '就绪';
}

document.getElementById('console').addEventListener('click', () => window.gorkDesktop.openConsole());
document.getElementById('hide').addEventListener('click', () => window.gorkDesktop.hideAvatar());
avatar.addEventListener('click', (event) => { if (!event.target.closest('button') && !event.target.closest('.drag-zone')) window.gorkDesktop.openConsole(); });
if (window.gorkDesktop) {
  window.gorkDesktop.getState().then(render).catch(() => render({ mode: 'confused', label: '后端未就绪' }));
  window.gorkDesktop.onState(render);
} else {
  // Read-only visual preview; no device/voice connection outside the desktop shell.
  render({mode:'idle',label:'外观预览'});
  document.querySelector('.actions').hidden=true;
}
