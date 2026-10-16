const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('gorkDesktop', Object.freeze({
  indicatorDrag:value=>ipcRenderer.invoke('gork:indicator-drag',value),
  getIndicatorSettings:()=>ipcRenderer.invoke('gork:indicator-settings'),
  setIndicatorSettings:value=>ipcRenderer.invoke('gork:set-indicator-settings',value),
  onIndicators:callback=>{const listener=(_e,value)=>callback(value);ipcRenderer.on('gork:indicators',listener);return ()=>ipcRenderer.removeListener('gork:indicators',listener);},
  setTokenHover: enabled => ipcRenderer.invoke('gork:token-hover', enabled),
  setTokenHeight: height => ipcRenderer.invoke('gork:token-height', height),
  hideTokenCard: () => ipcRenderer.invoke('gork:hide-token-card'),
  onTokenReset: callback => {
    const listener=()=>callback();ipcRenderer.on('gork:token-reset',listener);
    return ()=>ipcRenderer.removeListener('gork:token-reset',listener);
  },
  onTraffic: callback => {
    const listener=(_event,value)=>callback(value);ipcRenderer.on('gork:traffic',listener);
    return ()=>ipcRenderer.removeListener('gork:traffic',listener);
  },
  onTokenUsage: callback => {
    const listener=(_event,value)=>callback(value);ipcRenderer.on('gork:token-usage',listener);
    return ()=>ipcRenderer.removeListener('gork:token-usage',listener);
  },
  onPointer: callback => {
    const listener = (_event, value) => callback(value);
    ipcRenderer.on('gork:pointer', listener);
    return () => ipcRenderer.removeListener('gork:pointer', listener);
  },
  getPointerFollow: () => ipcRenderer.invoke('gork:pointer-follow'),
  setPointerFollow: enabled => ipcRenderer.invoke('gork:set-pointer-follow', enabled),
  playCustomExpression: (itemId, mode) => ipcRenderer.invoke('gork:apply-motion-config', itemId, mode),
  motionApplied: ack => ipcRenderer.send('gork:motion-applied', ack),
  onMotionConfig: callback => { const listener = (_event, value) => callback(value); ipcRenderer.on('gork:motion-config', listener); return () => ipcRenderer.removeListener('gork:motion-config', listener); },
  getAppearance: () => ipcRenderer.invoke('gork:get-appearance'),
  setAppearance: value => ipcRenderer.invoke('gork:set-appearance', value),
  getBubblePosition: () => ipcRenderer.invoke('gork:bubble-position'),
  setBubblePosition: position => ipcRenderer.invoke('gork:set-bubble-position', position),
  dismissBubble: () => ipcRenderer.invoke('gork:dismiss-bubble'),
  onBubble: (callback) => {
    const listener = (_event, state) => callback(state);
    ipcRenderer.on('gork:bubble', listener);
    return () => ipcRenderer.removeListener('gork:bubble', listener);
  },
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
  previewQuotaDrop: (points, animation) => ipcRenderer.invoke('gork:preview-quota-drop', points, animation),
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
