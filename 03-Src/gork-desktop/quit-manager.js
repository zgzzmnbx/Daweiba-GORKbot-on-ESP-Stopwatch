// Hold Electron open until cancellation and owned backend cleanup have finished.
function registerQuitCleanup(app, { prepare, stopAll, stopBackend, warn = console.error }) {
  let finished = false, pending;
  app.on('before-quit', event => {
    if (finished) return;
    event.preventDefault();
    if (pending) return;
    pending = Promise.resolve().then(async () => {
      try { prepare(); } catch { warn('Gork退出时窗口状态保存未完成'); }
      try { await stopAll(); } catch { warn('Gork退出时任务停止未完成'); }
      try { await stopBackend(); } catch { warn('Gork退出时托管后台停止未完成'); }
    }).finally(() => { finished = true; app.quit(); });
  });
}
module.exports = { registerQuitCleanup };
