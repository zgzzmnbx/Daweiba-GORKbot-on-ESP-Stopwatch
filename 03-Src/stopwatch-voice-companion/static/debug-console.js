// Read-only status summaries only; never request bodies, transcripts or raw exceptions.
export function createDebugConsole(doc, storage, copyText) {
  const get = id => doc.getElementById(id);
  const root = get('debug-console'), log = get('debug-log'), theme = get('debug-theme');
  const full = get('logs-full'), filter = get('logs-filter'), follow = get('logs-follow');
  const last = new Map(), rows = [];
  let selected = 'dark';
  try { if (storage?.getItem('gork.debug-theme') === 'light') selected = 'light'; } catch {}
  function setTheme(value) {
    selected = value === 'light' ? 'light' : 'dark';
    root.dataset.theme = selected; get('page-logs').dataset.theme = selected; theme.value = selected;
    try { storage?.setItem('gork.debug-theme', selected); } catch {}
  }
  setTheme(selected);
  theme.onchange = () => setTheme(theme.value);
  filter.value = 'all'; follow.checked = true;
  const matches = row => filter.value === 'ble' ? ['BLE','DEVICE'].includes(row.channel)
    : filter.value === 'voice' ? ['VOICE','SERVICE','AUDIO'].includes(row.channel)
    : filter.value === 'error' ? ['error','warning'].includes(row.level) : true;
  function line(row) {
    const node = doc.createElement('div');
    node.className = 'debug-line debug-' + row.level;
    node.textContent = row.text;
    return node;
  }
  function renderFull() {
    const top = full.scrollTop, visible = rows.filter(matches);
    full.replaceChildren(...visible.map(line));
    if (!visible.length) {
      const empty = doc.createElement('p'); empty.className = 'logs-empty';
      empty.textContent = '暂无符合条件的记录'; full.append(empty);
    }
    get('logs-count').textContent = `${visible.length} / ${rows.length} 条`;
    full.scrollTop = follow.checked ? full.scrollHeight : top;
  }
  function clear() { rows.length = 0; last.clear(); log.replaceChildren(); renderFull(); }
  get('debug-clear').onclick = clear; get('logs-clear').onclick = clear;
  filter.onchange = renderFull;
  follow.onchange = () => { if (follow.checked) full.scrollTop = full.scrollHeight; };
  full.onscroll = () => {
    if (full.scrollHeight - full.scrollTop - full.clientHeight > 32) follow.checked = false;
  };
  get('logs-copy').onclick = async () => {
    const text = rows.filter(matches).map(row => row.text).join('\n');
    if (!text) { get('logs-feedback').textContent = '当前筛选没有可复制的记录。'; return; }
    try {
      if (!copyText) throw new Error('Clipboard unavailable');
      await copyText(text); get('logs-feedback').textContent = '已复制当前筛选的日志。';
    } catch { get('logs-feedback').textContent = '复制失败，请选中日志文字后手动复制。'; }
  };
  function push(channel, text, error = false) {
    if (!text || last.get(channel) === text) return;
    last.set(channel, text);
    const bottom = log.scrollHeight - log.scrollTop - log.clientHeight < 32;
    const level = error ? 'error' : /未连接|离线|等待|取消|加载中/.test(text) ? 'warning'
      : /已连接|就绪|完成|成功/.test(text) ? 'success' : 'info';
    rows.push({channel, level, text: `${new Date().toLocaleTimeString('zh-CN', {hour12:false})} [${channel}] ${String(text).slice(0,240)}`});
    if (rows.length > 120) rows.shift();
    const top = log.scrollTop;
    log.replaceChildren(...rows.map(line));
    log.scrollTop = bottom ? log.scrollHeight : top;
    renderFull();
  }
  push('SYS', '状态监视已开启 · 只读 / 本页内存 / 最多 120 条');
  return {push};
}
