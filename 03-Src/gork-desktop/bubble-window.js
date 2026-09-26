const path = require('node:path');

// All dimensions are DIP. Keep text readable even with a 25% avatar.
const BUBBLE_POSITIONS = ['above', 'below', 'left', 'right'];
function bubblePlacement(avatar, area, text = '', preferred = 'above') {
  const lines = String(text).split('\n').reduce((sum, line) => sum + Math.max(1, Math.ceil(Array.from(line).length / 18)), 0);
  const width = Math.min(328, area.width), height = Math.min(264, Math.max(160, 132 + lines * 25), area.height);
  const gap = 6, cx = avatar.x + avatar.width / 2, cy = avatar.y + avatar.height / 2;
  if (!BUBBLE_POSITIONS.includes(preferred)) preferred = 'above';
  const opposite = {above:'below',below:'above',left:'right',right:'left'};
  const choices = {
    above:{x:cx-width/2,y:avatar.y-height-gap},
    below:{x:cx-width/2,y:avatar.y+avatar.height+gap},
    left:{x:avatar.x-width-gap,y:cy-height/2},
    right:{x:avatar.x+avatar.width+gap,y:cy-height/2},
  };
  const fits = side => ['above','below'].includes(side)
    ? choices[side].y >= area.y && choices[side].y + height <= area.y + area.height
    : choices[side].x >= area.x && choices[side].x + width <= area.x + area.width;
  const side = [preferred,opposite[preferred],...BUBBLE_POSITIONS].find(fits) || preferred;
  const x = Math.round(Math.max(area.x,Math.min(choices[side].x,area.x+area.width-width)));
  const y = Math.round(Math.max(area.y,Math.min(choices[side].y,area.y+area.height-height)));
  const vertical = ['above','below'].includes(side);
  const anchor = Math.round(Math.max(34,Math.min((vertical ? width : height)-34,vertical ? cx-x : cy-y)));
  return {bounds:{x,y,width,height},side,anchor};
}

function createBubbleWindow({BrowserWindow, screen, avatar, preferences, getPosition = () => 'above'}) {
  let win, ready = false, current = '', dismissed = false, revision = -1, disposed = false;
  function sync() {
    if (!win || win.isDestroyed() || !ready) return;
    if (!current || dismissed || avatar.isDestroyed() || !avatar.isVisible()) { win.hide(); return; }
    const place = bubblePlacement(avatar.getBounds(), screen.getDisplayMatching(avatar.getBounds()).workArea, current, getPosition());
    win.setBounds(place.bounds);
    win.setAlwaysOnTop(avatar.isAlwaysOnTop());
    win.webContents.send('gork:bubble', {text:current, side:place.side, anchor:place.anchor});
    if (!win.isVisible()) win.showInactive();
  }
  function update(character = {}) {
    if (disposed) return;
    const next = typeof character.bubble === 'string' ? character.bubble.slice(0, 2000) : '';
    if (next !== current || character.revision !== revision) dismissed = false;
    current = next; revision = character.revision;
    if (current && !dismissed && !win) {
      win = new BrowserWindow({width:328,height:224,frame:false,transparent:true,
        resizable:false,show:false,skipTaskbar:true,alwaysOnTop:avatar.isAlwaysOnTop(),
        webPreferences:preferences});
      win.webContents.setWindowOpenHandler(() => ({action:'deny'}));
      win.webContents.on('will-navigate', event => event.preventDefault());
      win.on('closed', () => { win = null; ready = false; dismissed = true; });
      win.once('ready-to-show', () => { ready = true; sync(); });
      win.loadFile(path.join(__dirname, 'bubble.html'));
    }
    sync();
  }
  return {update, sync, owns:sender => Boolean(win && !win.isDestroyed() && sender === win.webContents),
    dismiss() { dismissed = true; sync(); },
    hide() { if (win && !win.isDestroyed()) win.hide(); },
    destroy() { disposed = true; if (win && !win.isDestroyed()) win.destroy(); win = null; ready = false; }};
}
module.exports = {bubblePlacement, createBubbleWindow, BUBBLE_POSITIONS};
