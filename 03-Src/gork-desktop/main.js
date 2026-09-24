const { app, BrowserWindow, ipcMain, Menu, nativeImage, screen, session, Tray } = require('electron');
const fs = require('node:fs');
const path = require('node:path');
const { ensureBackend, stopOwnedBackend } = require('./backend-manager');
const { visibleBounds, avatarBoundsForScale } = require('./window-state');
const { createTrayIcon } = require('./tray-icon');

const backendPort = Number(process.env.GORK_BACKEND_PORT || 8766);
if (!Number.isInteger(backendPort) || backendPort < 1024 || backendPort > 65535) throw new Error('GORK_BACKEND_PORT must be 1024..65535');
const BACKEND_URL = `http://127.0.0.1:${backendPort}`;
const ROOT = app.isPackaged ? path.join(process.resourcesPath, 'project') : path.resolve(__dirname, '..', '..');
let backend;
let avatarWindow;
let consoleWindow;
let tray;
let quitting = false;
let sharedState = { mode: 'idle', label: '正在启动', robotConnected: false, character: { revision: 0, bubble: '' } };
let avatarScene = null;
let stateTimer;

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
    fs.writeFileSync(statePath(), JSON.stringify({ ...avatarWindow.getBounds(), alwaysOnTop: avatarWindow.isAlwaysOnTop() }));
}

function securePreferences() {
  return { preload: path.join(__dirname, 'preload.js'), contextIsolation: true, nodeIntegration: false, sandbox: true };
}

function createAvatar() {
  const saved = readState();
  const restored = visibleBounds(saved, screen.getAllDisplays());
  avatarWindow = new BrowserWindow({
    width: 240, height: 280, ...(restored || {}), minWidth: 60, minHeight: 70, maxWidth: 360, maxHeight: 420,
    frame: false, transparent: true, alwaysOnTop: saved.alwaysOnTop !== false, resizable: true, show: false, skipTaskbar: true,
    webPreferences: securePreferences(),
  });
  avatarWindow.loadFile(path.join(__dirname, 'avatar.html'));
  avatarWindow.once('ready-to-show', () => avatarWindow.showInactive());
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
  try { await fetch(`${BACKEND_URL}/api/desktop/stop`, { method: 'POST' }); } catch {}
}
async function pollState() {
  try {
    const response = await fetch(`${BACKEND_URL}/api/desktop/state`, { signal: AbortSignal.timeout(2000) });
    const data = await response.json();
    const modes = { listening: 'listening', processing: 'thinking', generating: 'thinking', speaking: 'happy', error: 'confused' };
    sharedState = { mode: modes[data.phase] || 'idle', label: data.phase === 'idle' ? '就绪' : ({listening:'正在聆听',processing:'处理中',generating:'正在回答',speaking:'正在说话',error:'需要检查'}[data.phase] || data.phase), robotConnected: Boolean(data.robot?.connected), character: data.character || { revision: 0, bubble: '' }, scene: avatarScene };
  } catch { sharedState = { mode: 'confused', label: '后端未就绪', robotConnected: false, character: { revision: 0, bubble: '' }, scene: avatarScene }; }
  if (avatarWindow && !avatarWindow.isDestroyed()) avatarWindow.webContents.send('gork:state', sharedState);
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
  ipcMain.handle('gork:open-console', () => showConsole());
  ipcMain.handle('gork:hide-avatar', () => avatarWindow.hide());
  ipcMain.handle('gork:stop-all', () => stopAll());
  ipcMain.handle('gork:get-state', () => sharedState);
  ipcMain.handle('gork:set-avatar-scene', (event, scene) => {
    if (event.sender !== consoleWindow?.webContents) throw new Error('Only the console can set the avatar scene');
    if (!scene || typeof scene.expression !== 'string' || !['once', 'loop'].includes(scene.mode)) throw new Error('Invalid avatar scene');
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
      script: path.join(ROOT, '03-Src', 'stopwatch-voice-companion', 'run_companion.py'), cwd: ROOT,
      args: backendConfig ? ['--config', backendConfig] : [] });
    createAvatar(); createConsole(); createTray();
    await pollState(); stateTimer = setInterval(pollState, 500);
    if (process.argv.includes('--smoke-test')) {
      console.log(`GORK_DESKTOP_READY backend=${backend.ownership}`);
      setTimeout(() => { quitting = true; app.quit(); }, 500);
    }
  }).catch((error) => { console.error(error); quitting = true; app.quit(); });

  app.on('before-quit', async () => { quitting = true; clearInterval(stateTimer); saveState(); await stopAll(); await stopOwnedBackend(backend); });
  app.on('window-all-closed', (event) => event.preventDefault());
}
