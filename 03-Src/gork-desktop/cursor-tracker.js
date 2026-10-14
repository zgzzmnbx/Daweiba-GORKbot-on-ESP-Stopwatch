/* Desktop cursor and window bounds are all Electron DIP coordinates. */
function createCursorTracker(win, screen, {enabled=true, timers={setInterval, clearInterval}} = {}) {
  let timer = null, previous = '', disposed = false;
  function sample() {
    if (disposed || !enabled || win.isDestroyed() || !win.isVisible() || win.isMinimized()) return;
    const point = screen.getCursorScreenPoint(), bounds = win.getContentBounds();
    const display = screen.getDisplayMatching(bounds).bounds;
    const value = {clientX:point.x-bounds.x, clientY:point.y-bounds.y,
      viewport:{width:display.width,height:display.height}};
    const key = JSON.stringify([point.x,point.y,bounds,display]);
    if (key === previous) return;
    previous = key;
    win.webContents.send('gork:pointer', value);
  }
  function start() {
    if (disposed || !enabled || win.isDestroyed() || !win.isVisible() || win.isMinimized()) return;
    previous = ''; sample();
    if (timer === null) timer = timers.setInterval(sample, 50);
  }
  function stop() {
    if (timer !== null) timers.clearInterval(timer);
    timer = null; previous = '';
    if (!win.isDestroyed()) win.webContents.send('gork:pointer', null);
  }
  const events = {show:start, restore:start, hide:stop, minimize:stop, closed:dispose};
  for (const [name, handler] of Object.entries(events)) win.on(name, handler);
  win.webContents.on('did-finish-load', start);
  function dispose() {
    if (disposed) return;
    disposed = true; stop();
    for (const [name, handler] of Object.entries(events)) win.removeListener(name, handler);
    win.webContents.removeListener('did-finish-load', start);
  }
  return {dispose,setEnabled(value) {enabled=value;if(enabled)start();else stop();}};
}
module.exports = {createCursorTracker};
