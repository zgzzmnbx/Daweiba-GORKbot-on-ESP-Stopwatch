/* Explicit named-expression playback; saving never invokes this bridge. AGPL-3.0-only. */
const Config = require('./motion/gork-config.js');

function createMotionBridge({ipcMain, getConsole, getAvatar, fetchRecord, onApplied, timeoutMs=4000}) {
  let serial = 0;
  const pending = new Map();
  ipcMain.on('gork:motion-applied', (event, ack) => {
    if (event.sender !== getAvatar()?.webContents || !ack || !Number.isInteger(ack.requestId)) return;
    const item = pending.get(ack.requestId);
    if (!item) return;
    pending.delete(ack.requestId); clearTimeout(item.timer);
    if (ack.ok === true && ack.revision === item.record.revision) {
      onApplied(item.record, item.scene); item.resolve({applied:true, revision:ack.revision});
    } else item.reject(new Error('配置已保存，但桌面播放器应用失败：' + String(ack.error || '修订号不一致').slice(0,120)));
  });
  ipcMain.handle('gork:apply-motion-config', async (event, itemId, mode='once') => {
    if (event.sender !== getConsole()?.webContents) throw new Error('Only the console can apply motion config');
    if (typeof itemId !== 'string' || !/^motion-[0-9a-f]{12}$/.test(itemId) || !['once','loop'].includes(mode)) throw new Error('Invalid custom expression');
    const record = await fetchRecord(itemId);
    if (record.id !== itemId || !Number.isSafeInteger(record.revision) || !Config.sceneNames.includes(record.scene)) throw new Error('Invalid saved expression');
    record.config = Config.parse(JSON.stringify(record.config));
    const win = getAvatar();
    if (!win || win.isDestroyed()) throw new Error('配置已保存，但桌面窗口不可用');
    const requestId = ++serial;
    const scene = {expression:itemId, mode, startedAt:Date.now(), requestId};
    return new Promise((resolve,reject) => {
      const timer = setTimeout(() => {pending.delete(requestId);reject(new Error('配置已保存，桌面应用回执超时'));}, timeoutMs);
      pending.set(requestId,{resolve,reject,timer,record,scene});
      try {win.webContents.send('gork:motion-config',{record,scene,requestId});}
      catch(error){pending.delete(requestId);clearTimeout(timer);reject(error);}
    });
  });
  return {dispose(){for(const item of pending.values()){clearTimeout(item.timer);item.reject(new Error('桌面窗口已关闭'));}pending.clear();}};
}
module.exports = {createMotionBridge};
