const { app, BrowserWindow, ipcMain, Menu, nativeImage, screen, session, Tray, dialog } = require('electron');
const fs = require('node:fs');
const MotionConfig = require('./motion/gork-config.js');
const avatarSceneNames = new Set(require('./motion/legacy-scene-names.json'));
const { createMotionBridge } = require('./motion-bridge');
if (process.env.GORK_TEST_USER_DATA) app.setPath('userData', process.env.GORK_TEST_USER_DATA);
const path = require('node:path');
const { ensureBackend, stopOwnedBackend } = require('./backend-manager');
const { registerQuitCleanup } = require('./quit-manager');
const { visibleBounds, avatarBoundsForScale } = require('./window-state');
const { createTrayIcon } = require('./tray-icon');
const { createCursorTracker } = require('./cursor-tracker');
const { createTokenWindow } = require('./token-window');
const { createBubbleWindow, BUBBLE_POSITIONS } = require('./bubble-window');
const { normalize:normalizeAppearance } = require('./gork-appearance');

const backendPort = Number(process.env.GORK_BACKEND_PORT || 8766);
if (!Number.isInteger(backendPort) || backendPort < 1024 || backendPort > 65535) throw new Error('GORK_BACKEND_PORT must be 1024..65535');
const BACKEND_URL = `http://127.0.0.1:${backendPort}`;
const ROOT = app.isPackaged ? path.join(process.resourcesPath, 'project') : path.resolve(__dirname, '..', '..');
let backend;
let avatarWindow;
let consoleWindow;
let bubbleWindow;
let tokenWindow;
let bubblePosition = 'above';
let tray;
let quitting = false;
let sharedState = { mode: 'idle', label: '正在启动', robotConnected: false, character: { revision: 0, bubble: '' } };
let avatarScene = null;
let appearance = normalizeAppearance(null);
let stateTimer;
let cursorTracker;
let pointerFollow = true;
let quotaPreview = null;
let quotaPreviewRevision = 0;

const hasSingleInstanceLock = app.requestSingleInstanceLock();
if (!hasSingleInstanceLock) app.quit();
else app.on('second-instance', () => showConsole());

function statePath() { return path.join(app.getPath('userData'), 'window-state.json'); }
function readState() {
  try { const saved = JSON.parse(fs.readFileSync(statePath(), 'utf8')); return saved && typeof saved === 'object' ? saved : {}; }
  catch { return {}; }
}
function saveState() {
  if (avatarWindow && !avatarWindow.isDestroyed())
    fs.writeFileSync(statePath(), JSON.stringify({ ...avatarWindow.getBounds(), alwaysOnTop: avatarWindow.isAlwaysOnTop(), bubblePosition, appearance, pointerFollow }));
}

function securePreferences() {
  return { preload: path.join(__dirname, 'preload.js'), contextIsolation: true, nodeIntegration: false, sandbox: true };
}

function createAvatar() {
  const saved = readState();
  pointerFollow = saved.pointerFollow !== false; sharedState.pointerFollow = pointerFollow;
  appearance = normalizeAppearance(saved.appearance);sharedState.appearance=appearance;
  bubblePosition = BUBBLE_POSITIONS.includes(saved.bubblePosition) ? saved.bubblePosition : 'above';
  const restored = visibleBounds(saved, screen.getAllDisplays());
  avatarWindow = new BrowserWindow({
    width: 240, height: 280, ...(restored || {}), minWidth: 60, minHeight: 70, maxWidth: 360, maxHeight: 420,
    frame: false, transparent: true, alwaysOnTop: saved.alwaysOnTop !== false, resizable: true, show: false, skipTaskbar: true,
    webPreferences: securePreferences(),
  });
  avatarWindow.loadFile(path.join(__dirname, 'avatar.html'));
  cursorTracker = createCursorTracker(avatarWindow, screen, {enabled:pointerFollow});
  avatarWindow.once('ready-to-show', () => avatarWindow.showInactive());
  bubbleWindow = createBubbleWindow({BrowserWindow, screen, avatar:avatarWindow, preferences:securePreferences(), getPosition:() => bubblePosition});
  tokenWindow = createTokenWindow({BrowserWindow,screen,avatar:avatarWindow,preferences:securePreferences(),
    async readUsage(){const response=await fetch(`${BACKEND_URL}/api/desktop/token-usage`,{signal:AbortSignal.timeout(4000)});
      if(!response.ok)throw Error('Token usage unavailable');return response.json();},
    async readQuota(){const response=await fetch(`${BACKEND_URL}/api/desktop/quota-usage`,{signal:AbortSignal.timeout(15000)});
      if(!response.ok)throw Error('Quota unavailable');return response.json();}});
  avatarWindow.on('move', () => bubbleWindow.sync());
  avatarWindow.on('resize', () => bubbleWindow.sync());
  avatarWindow.on('show', () => bubbleWindow.sync());
  avatarWindow.on('hide', () => bubbleWindow.hide());
  avatarWindow.on('moved', saveState);
  avatarWindow.on('resized', saveState);
  avatarWindow.on('close', (event) => { if (!quitting) { event.preventDefault(); avatarWindow.hide(); } });
  avatarWindow.webContents.setWindowOpenHandler(() => ({ action: 'deny' }));
  avatarWindow.webContents.on('will-navigate', (event) => event.preventDefault());
  avatarWindow.webContents.on('context-menu', () => tray?.popUpContextMenu());
}

function createConsole() {
  if (consoleWindow && !consoleWindow.isDestroyed()) return consoleWindow;
  consoleWindow = new BrowserWindow({ width: 1180, height: 820, show: false, webPreferences: securePreferences() });
  consoleWindow.loadURL(BACKEND_URL);
  consoleWindow.on('close', (event) => { if (!quitting) { event.preventDefault(); stopAll(); consoleWindow.hide(); } });
  consoleWindow.webContents.setWindowOpenHandler(() => ({ action: 'deny' }));
  consoleWindow.webContents.on('will-navigate', (event, url) => { if (new URL(url).origin !== BACKEND_URL) event.preventDefault(); });
  return consoleWindow;
}

function showConsole() { const win = createConsole(); win.show(); win.focus(); }
function showAvatar() { if (avatarWindow) avatarWindow.showInactive(); }
async function stopAll() {
  if (consoleWindow && !consoleWindow.isDestroyed()) consoleWindow.webContents.send('gork:stop-local');
  try { await fetch(`${BACKEND_URL}/api/desktop/stop`, { method: 'POST', signal: AbortSignal.timeout(3000) }); } catch {}
}
async function fetchMotionRecord(itemId) {
  const response = await fetch(`${BACKEND_URL}/api/motion/expressions/${encodeURIComponent(itemId)}`, {signal:AbortSignal.timeout(2000)});
  if (!response.ok) throw new Error('动效配置读取失败');
  const record = await response.json();
  if (!Number.isSafeInteger(record.revision) || record.revision < 1) throw new Error('动效修订号无效');
  record.config = MotionConfig.parse(JSON.stringify(record.config));
  return record;
}
async function pollState() {
  try {
    const response = await fetch(`${BACKEND_URL}/api/desktop/state`, { signal: AbortSignal.timeout(2000) });
    const data = await response.json();
    const modes = { listening: 'listening', processing: 'thinking', generating: 'thinking', speaking: 'happy', error: 'confused' };
    const character = data.character || { revision: 0, bubble: '' };
    const autoRevision=1000000+character.revision;
    const autoScene = character.auto ? {expression:character.expression, mode:character.mode||'loop', custom:character.custom_motion,
      startedAt:sharedState.scene?.revision===autoRevision?sharedState.scene.startedAt:Date.now(), revision:autoRevision} : null;
    sharedState = { mode: modes[data.phase] || 'idle', label: data.phase === 'idle' ? '就绪' : ({listening:'正在聆听',processing:'处理中',generating:'正在回答',speaking:'正在说话',error:'需要检查'}[data.phase] || data.phase), robotConnected: Boolean(data.robot?.connected), character, codex:data.codex || {enabled:false}, scene: autoScene || avatarScene };
    if (data.phase === 'idle' && data.codex?.trend) sharedState.label = '额度下降';
  } catch { sharedState = { mode: 'confused', label: '后端未就绪', robotConnected: false, character: { revision: 0, bubble: '' }, scene: avatarScene }; }
  if (quotaPreview && quotaPreview.until > Date.now()) {
    const preview = quotaPreview;
    sharedState = {...sharedState, label:preview.animation ? '额度下降预览' : sharedState.label,
      character:{...sharedState.character, revision:preview.revision,
        bubble:`预览：Codex 额度下降 ${preview.points} 个百分点，现剩余 42%。`},
      codex:{...sharedState.codex, trend:preview.animation ? {
        drop_points:preview.points, window_name:'预览窗口', remaining:42} : null},
      scene:preview.animation ? {expression:'curious', mode:'loop',
        startedAt:preview.startedAt, revision:preview.revision} : sharedState.scene};
  } else quotaPreview = null;
  sharedState.appearance=appearance;
  sharedState.pointerFollow=pointerFollow;
  if (avatarWindow && !avatarWindow.isDestroyed()) avatarWindow.webContents.send('gork:state', sharedState);
  bubbleWindow?.update(sharedState.character);
  updateTrayMenu();
}

function updateTrayMenu() {
  if (!tray) return;
  tray.setContextMenu(Menu.buildFromTemplate([
    { label: `StopWatch：${sharedState.robotConnected ? '已连接' : '离线'}`, enabled: false },
    { type: 'separator' }, { label: '打开控制台', click: showConsole },
    { label: '显示桌面小人', click: showAvatar }, { label: '停止全部', click: stopAll },
    { type: 'separator' }, { label: '退出', click: () => { quitting = true; app.quit(); } },
  ]));
}

function createTray() {
  tray = new Tray(createTrayIcon(nativeImage));
  tray.setToolTip('Gork 机器人控制台');
  updateTrayMenu();
  tray.on('double-click', showConsole);
}

if (hasSingleInstanceLock) {
  ipcMain.handle('gork:token-hover',(event,enabled)=>{
    const fromCard=tokenWindow?.owns(event.sender);
    if((event.sender!==avatarWindow?.webContents&&!fromCard)||typeof enabled!=='boolean')throw Error('Invalid token hover request');
    tokenWindow?.setHover(enabled,fromCard?'card':'avatar');return true;
  });
  ipcMain.handle('gork:token-height',(event,height)=>{
    if(!tokenWindow?.owns(event.sender)||!Number.isInteger(height)||height<180||height>900)throw Error('Invalid token height request');
    tokenWindow.setHeight(height);return true;
  });
  ipcMain.handle('gork:hide-token-card',event=>{
    if(event.sender!==avatarWindow?.webContents&&!tokenWindow?.owns(event.sender))throw Error('Invalid token dismiss request');
    tokenWindow?.hide();return true;
  });
  ipcMain.handle('gork:pointer-follow', event => {
    if (event.sender !== consoleWindow?.webContents) throw new Error('Only the console can inspect pointer follow');
    return pointerFollow;
  });
  ipcMain.handle('gork:set-pointer-follow', (event, enabled) => {
    if (event.sender !== consoleWindow?.webContents || typeof enabled !== 'boolean') throw new Error('Invalid pointer follow request');
    if (!avatarWindow || avatarWindow.isDestroyed()) throw new Error('Avatar window unavailable');
    const previous = pointerFollow; pointerFollow = enabled;
    try {saveState();} catch(error) {pointerFollow=previous;throw error;}
    sharedState.pointerFollow=pointerFollow;
    avatarWindow.webContents.send('gork:state', sharedState);
    cursorTracker?.setEnabled(enabled);
    return pointerFollow;
  });
  createMotionBridge({ipcMain,getConsole:()=>consoleWindow,getAvatar:()=>avatarWindow,fetchRecord:fetchMotionRecord,
    onApplied(record,scene){avatarScene={...scene,custom:record,revision:(avatarScene?.revision||0)+1};sharedState.scene=avatarScene;}});
  ipcMain.handle('gork:get-appearance',event=>{
    if(event.sender!==consoleWindow?.webContents)throw new Error('Only the console can inspect appearance');
    return appearance;
  });
  ipcMain.handle('gork:set-appearance',(event,value)=>{
    if(event.sender!==consoleWindow?.webContents)throw new Error('Only the console can set appearance');
    const next=normalizeAppearance(value),previous=appearance;
    appearance=next;
    try {saveState();} catch(error) {appearance=previous;throw error;}
    sharedState.appearance=appearance;
    if(avatarWindow&&!avatarWindow.isDestroyed())avatarWindow.webContents.send('gork:state',sharedState);
    return appearance;
  });
  ipcMain.handle('gork:open-console', () => showConsole());
  ipcMain.handle('gork:hide-avatar', () => avatarWindow.hide());
  ipcMain.handle('gork:stop-all', () => stopAll());
  ipcMain.handle('gork:get-state', () => sharedState);
  ipcMain.handle('gork:preview-quota-drop', (event, points, animation) => {
    if (event.sender !== consoleWindow?.webContents) throw new Error('Only the console can preview quota alerts');
    if (!Number.isInteger(points) || points < 1 || points > 20 || typeof animation !== 'boolean')
      throw new Error('Invalid quota preview settings');
    quotaPreview = {points, animation, startedAt:Date.now(), until:Date.now()+10000,
      revision:++quotaPreviewRevision+2000000};
    showAvatar();
    void pollState();
    return {preview:true};
  });
  ipcMain.handle('gork:bubble-position', event => {
    if (event.sender !== consoleWindow?.webContents) throw new Error('Only the console can inspect bubble position');
    return bubblePosition;
  });
  ipcMain.handle('gork:set-bubble-position', (event, position) => {
    if (event.sender !== consoleWindow?.webContents || !BUBBLE_POSITIONS.includes(position)) throw new Error('Invalid bubble position');
    if (!avatarWindow || avatarWindow.isDestroyed()) throw new Error('Avatar window unavailable');
    bubblePosition = position; saveState(); bubbleWindow?.sync();
    return bubblePosition;
  });
  ipcMain.handle('gork:dismiss-bubble', event => {
    if (!bubbleWindow?.owns(event.sender)) throw new Error('Only the bubble can dismiss itself');
    bubbleWindow.dismiss();
  });
  ipcMain.handle('gork:set-avatar-scene', (event, scene) => {
    if (event.sender !== consoleWindow?.webContents) throw new Error('Only the console can set the avatar scene');
    if (!scene || !avatarSceneNames.has(scene.expression) || Object.keys(scene).some(k=>!['expression','mode','startedAt'].includes(k)) || !['once', 'loop'].includes(scene.mode)) throw new Error('Invalid avatar scene');
    const now = Date.now();
    const startedAt = Number.isFinite(scene.startedAt) && Math.abs(now - scene.startedAt) < 10000 ? scene.startedAt : now;
    avatarScene = { expression: scene.expression, mode: scene.mode, startedAt, revision: (avatarScene?.revision || 0) + 1 };
    sharedState.scene = avatarScene;
    if (avatarWindow && !avatarWindow.isDestroyed()) avatarWindow.webContents.send('gork:state', sharedState);
    return avatarScene;
  });
  ipcMain.handle('gork:avatar-scale', (event) => {
    if (event.sender !== consoleWindow?.webContents) throw new Error('Only the console can inspect size');
    if (!avatarWindow || avatarWindow.isDestroyed()) throw new Error('Avatar window unavailable');
    return Math.round(avatarWindow.getBounds().width / 240 * 100);
  });
  ipcMain.handle('gork:set-avatar-scale', (event, percent) => {
    if (event.sender !== consoleWindow?.webContents) throw new Error('Only the console can resize the avatar');
    if (!avatarWindow || avatarWindow.isDestroyed()) throw new Error('Avatar window unavailable');
    const bounds = avatarWindow.getBounds();
    const area = screen.getDisplayMatching(bounds).workArea;
    avatarWindow.setBounds(avatarBoundsForScale(bounds, percent, area));
    saveState();
    return Math.round(avatarWindow.getBounds().width / 240 * 100);
  });
  ipcMain.handle('gork:avatar-visible', (event) => {
    if (event.sender !== consoleWindow?.webContents) throw new Error('Only the console can inspect visibility');
    return Boolean(avatarWindow && !avatarWindow.isDestroyed() && avatarWindow.isVisible());
  });
  ipcMain.handle('gork:set-avatar-visible', (event, visible) => {
    if (event.sender !== consoleWindow?.webContents || typeof visible !== 'boolean') throw new Error('Invalid visibility request');
    if (!avatarWindow || avatarWindow.isDestroyed()) throw new Error('Avatar window unavailable');
    if (visible) avatarWindow.showInactive(); else avatarWindow.hide();
    return avatarWindow.isVisible();
  });
  ipcMain.handle('gork:avatar-always-on-top', (event) => {
    if (event.sender !== consoleWindow?.webContents) throw new Error('Only the console can inspect avatar stacking');
    if (!avatarWindow || avatarWindow.isDestroyed()) throw new Error('Avatar window unavailable');
    return avatarWindow.isAlwaysOnTop();
  });
  ipcMain.handle('gork:set-avatar-always-on-top', (event, enabled) => {
    if (event.sender !== consoleWindow?.webContents || typeof enabled !== 'boolean') throw new Error('Invalid avatar stacking request');
    if (!avatarWindow || avatarWindow.isDestroyed()) throw new Error('Avatar window unavailable');
    avatarWindow.setAlwaysOnTop(enabled);
    bubbleWindow?.sync();
    tokenWindow?.sync();
    saveState();
    return avatarWindow.isAlwaysOnTop();
  });

  app.whenReady().then(async () => {
    const allowedOrigin = BACKEND_URL;
    session.defaultSession.setPermissionCheckHandler((_contents, permission, origin, details) =>
      permission === 'media' && typeof origin === 'string' && new URL(origin).origin === allowedOrigin
        && (!details || !details.mediaType || details.mediaType === 'audio'));
    session.defaultSession.setPermissionRequestHandler((contents, permission, callback, details) => {
      const origin = new URL(contents.getURL()).origin;
      callback(permission === 'media' && origin === allowedOrigin && (details.mediaTypes || []).every((kind) => kind === 'audio'));
    });
    const python = path.join(ROOT, 'Codex-Temp', '.venv-companion', 'Scripts', 'python.exe');
    const backendConfig = process.env.GORK_BACKEND_CONFIG;
    backend = await ensureBackend({ baseUrl: BACKEND_URL, python,
      expectedVersion: app.getVersion(),
      script: path.join(ROOT, '03-Src', 'stopwatch-voice-companion', 'run_companion.py'), cwd: ROOT,
      args: backendConfig ? ['--config', backendConfig] : [] });
    createAvatar(); createConsole(); createTray();
    await pollState(); stateTimer = setInterval(pollState, 500);
    if (process.argv.includes('--smoke-test')) {
      console.log(`GORK_DESKTOP_READY backend=${backend.ownership}`);
      setTimeout(() => { quitting = true; app.quit(); }, 500);
    }
  }).catch((error) => {
    if (error.code === 'GORK_BACKEND_VERSION') dialog.showErrorBox('Gork后台版本未更新', error.message);
    else console.error(error);
    quitting = true; app.quit();
  });

  registerQuitCleanup(app, {
    prepare: () => { quitting = true; clearInterval(stateTimer); cursorTracker?.dispose(); tokenWindow?.destroy(); bubbleWindow?.destroy(); saveState(); },
    stopAll, stopBackend: () => stopOwnedBackend(backend),
  });
  app.on('window-all-closed', (event) => event.preventDefault());
}
