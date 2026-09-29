const speech = document.getElementById('speech');
let dismissOnClick = false;
function renderBubble({text = '', side = 'above', anchor = 112, dismissOnClick: clickable = false}) {
  dismissOnClick = clickable === true;
  document.body.dataset.clickDismiss = dismissOnClick ? 'true' : 'false';
  document.getElementById('bubble-hint').textContent = dismissOnClick ? '点击气泡关闭 · 最多 5 分钟' : '桌面消息';
  if (speech.textContent !== text) { speech.textContent = text; speech.scrollTop = 0; }
  document.body.dataset.side = ['left','right','above','below'].includes(side) ? side : 'above';
  document.body.style.setProperty('--anchor', `${Number.isFinite(anchor) ? anchor : 112}px`);
}
document.getElementById('dismiss').onclick = () => window.gorkDesktop?.dismissBubble();
document.getElementById('open-console').onclick = () => window.gorkDesktop?.openConsole();
document.querySelector('.speech-card').addEventListener('click', event => {
  if (dismissOnClick && !event.target.closest('button')) window.gorkDesktop?.dismissBubble();
});
document.addEventListener('keydown', event => { if (event.key === 'Escape') window.gorkDesktop?.dismissBubble(); });
if (window.gorkDesktop) window.gorkDesktop.onBubble(renderBubble);
else renderBubble({text:'你好，大尾巴。\n我在这里，随时陪你聊两句。'});
