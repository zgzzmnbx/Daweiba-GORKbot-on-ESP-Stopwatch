/* Local presentation only. The video is loaded after an explicit click. */
(() => {
  const openButton = document.getElementById('architecture-open');
  const playButton = document.getElementById('architecture-play');
  const closeButton = document.getElementById('architecture-close');
  const dialog = document.getElementById('architecture-dialog');
  const video = document.getElementById('architecture-video');
  const error = document.getElementById('architecture-error');
  if (!openButton || !playButton || !closeButton || !dialog || !video) return;
  function stopPlayback() {
    video.pause();
    video.removeAttribute('src');
    video.load();
    playButton.textContent = '暂停';
    openButton.focus();
  }

  openButton.addEventListener('click', () => {
    if (dialog.open) return;
    dialog.showModal();
    error.hidden = true;
    video.src = '/static/architecture-landscape.mp4';
    video.load();
    playButton.textContent = '暂停';
    video.play().catch(() => { playButton.textContent = '播放'; });
    closeButton.focus();
  });
  playButton.addEventListener('click', () => {
    if (video.paused) {
      video.play().then(() => { playButton.textContent = '暂停'; })
        .catch(() => { playButton.textContent = '播放'; });
    } else {
      video.pause();
      playButton.textContent = '继续';
    }
  });
  closeButton.addEventListener('click', () => { dialog.close(); stopPlayback(); });
  dialog.addEventListener('click', event => {
    if (event.target === dialog) { dialog.close(); stopPlayback(); }
  });
  dialog.addEventListener('cancel', stopPlayback);
  dialog.addEventListener('close', stopPlayback);
  video.addEventListener('error', () => { error.hidden = false; });
})();
