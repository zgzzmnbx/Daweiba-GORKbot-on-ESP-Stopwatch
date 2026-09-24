const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('gorkDesktop', Object.freeze({
  openConsole: () => ipcRenderer.invoke('gork:open-console'),
  hideAvatar: () => ipcRenderer.invoke('gork:hide-avatar'),
  stopAll: () => ipcRenderer.invoke('gork:stop-all'),
  getAvatarScale: () => ipcRenderer.invoke('gork:avatar-scale'),
  setAvatarScale: (percent) => ipcRenderer.invoke('gork:set-avatar-scale', percent),
  getAvatarVisible: () => ipcRenderer.invoke('gork:avatar-visible'),
  setAvatarVisible: (visible) => ipcRenderer.invoke('gork:set-avatar-visible', visible),
  getAvatarAlwaysOnTop: () => ipcRenderer.invoke('gork:avatar-always-on-top'),
  setAvatarAlwaysOnTop: (enabled) => ipcRenderer.invoke('gork:set-avatar-always-on-top', enabled),
  getState: () => ipcRenderer.invoke('gork:get-state'),
  setAvatarScene: (scene) => ipcRenderer.invoke('gork:set-avatar-scene', scene),
  onState: (callback) => {
    const listener = (_event, state) => callback(state);
    ipcRenderer.on('gork:state', listener);
    return () => ipcRenderer.removeListener('gork:state', listener);
  },
  onStopAll: (callback) => {
    const listener = () => callback();
    ipcRenderer.on('gork:stop-local', listener);
    return () => ipcRenderer.removeListener('gork:stop-local', listener);
  },
}));
