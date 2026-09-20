import {toPCM16, Epoch} from './pcm.js';

const $ = id => document.getElementById(id);
const epoch = new Epoch();
let client = crypto.randomUUID(), connected = false, dirty = false, phase = 'idle';
let turnReady = false;
let context, stream, capture, source, playback, deadline, chunks = [], rate = 16000;
let tick = false, polling = false, suggestedAddress = '';
const labels = {idle: '待机', listening: '正在聆听', processing: '处理中', speaking: '正在回读', ready: '文字已就绪', error: '请检查连接'};

function message(text, error = false) { $('message').textContent = text; $('message').className = 'message' + (error ? ' error' : ''); }
function render(next = phase) {
  phase = next; document.body.dataset.phase = phase;
  $('phase').textContent = connected ? labels[phase] : '未连接';
  const busy = ['listening', 'processing', 'speaking'].includes(phase);
  $('record').disabled = !connected || dirty; $('record').hidden = phase === 'listening';
  $('finish').hidden = phase !== 'listening'; $('stop').disabled = !connected;
  $('speak').disabled = !connected || dirty || busy || !$('transcript').value.trim();
  $('transcript').readOnly = busy;
  $('connect').hidden = connected; $('release').hidden = !connected;
  $('scan').disabled = !connected; $('apply').disabled = !connected;
  $('count').textContent = `${Array.from($('transcript').value).length} / 300`;
}
async function api(path, method = 'GET', body, options = {}) {
  const headers = {'X-Companion-Client': client, ...options.headers};
  let payload = body;
  if (body !== undefined && !(body instanceof ArrayBuffer)) { headers['Content-Type'] = 'application/json'; payload = JSON.stringify(body); }
  const response = await fetch('/api' + path, {method, headers, body: payload, signal: options.signal, keepalive: options.keepalive});
  if (!response.ok) {
    const detail = await response.json().catch(() => ({}));
    const error = new Error(detail.error?.message || `请求失败（${response.status}）`);
    error.code = detail.error?.code; error.status = response.status; throw error;
  }
  return options.audio ? response.arrayBuffer() : response.json();
}
function localStop() {
  clearTimeout(deadline); clearInterval(tick); tick = false;
  if (playback) { playback.onended = null; try { playback.stop(); } catch {} playback.disconnect(); playback = null; }
  stream?.getTracks().forEach(track => track.stop()); stream = null;
  if (capture) { capture.port.onmessage = null; capture.disconnect(); capture = null; }
  source?.disconnect(); source = null;
  const oldContext = context; context = null;
  if (oldContext && oldContext.state !== 'closed') { oldContext.suspend().catch(() => {}); oldContext.close().catch(() => {}); }
  chunks = [];
}
function failed(error, gen) {
  if (error.name === 'AbortError' || (gen !== undefined && !epoch.valid(gen))) return;
  localStop();
  if (error.status === 401) { connected = false; epoch.next(); $('takeover').hidden = true; }
  render('error'); message(error.message || '连接中断，请检查服务后重试。', true);
  if (connected && gen !== undefined && epoch.valid(gen)) state('error', gen).catch(() => {});
}
async function stop() {
  turnReady = false;
  localStop(); const gen = epoch.next(); render('idle'); message('已停止本地录音与播放，正在取消服务请求。');
  if (connected) {
    try { await api('/stop', 'POST', {generation: gen}); if (epoch.valid(gen)) message('已停止。旧结果不会继续播放；已提交的云端请求可能仍产生费用。'); }
    catch (error) { failed(error, gen); }
  }
}
async function state(name, gen) { await api('/state', 'POST', {generation: gen, state: name}, {signal: epoch.abort.signal}); }
async function begin() {
  localStop(); const gen = epoch.next();
  await api('/begin', 'POST', {generation: gen}, {signal: epoch.abort.signal});
  if (!epoch.valid(gen)) throw new DOMException('旧操作', 'AbortError');
  turnReady = true;
  return gen;
}
async function record() {
  let gen;
  try {
    gen = await begin(); render('processing');
    const audio = new AudioContext({sampleRate: 16000}); context = audio;
    await audio.resume();
    const acquired = await navigator.mediaDevices.getUserMedia({audio: {channelCount: 1, echoCancellation: true, noiseSuppression: true}, video: false});
    if (!epoch.valid(gen)) { acquired.getTracks().forEach(track => track.stop()); return; }
    stream = acquired; rate = audio.sampleRate;
    await audio.audioWorklet.addModule('/static/capture.js');
    if (!epoch.valid(gen)) return;
    source = audio.createMediaStreamSource(stream); capture = new AudioWorkletNode(audio, 'capture');
    let frames = 0;
    capture.port.onmessage = event => { if (epoch.valid(gen) && frames < rate * 30) { chunks.push(event.data); frames += event.data.length; } };
    source.connect(capture); capture.connect(audio.destination);
    await state('listening', gen);
    if (!epoch.valid(gen)) return;
    render('listening'); message('正在收音。结束后可编辑识别文字，再点击回读。');
    const started = performance.now();
    tick = setInterval(() => { $('record-hint').textContent = `正在录音 ${Math.min(30, (performance.now() - started) / 1000).toFixed(1)} / 30 秒`; }, 100);
    deadline = setTimeout(finish, 30000);
  } catch (error) { failed(error, gen); }
}
async function finish() {
  if (phase !== 'listening') return;
  const gen = epoch.value, wav = toPCM16(chunks, rate);
  localStop(); render('processing'); $('record-hint').textContent = '录音已结束，正在转写…';
  try {
    const result = await api('/asr', 'POST', wav, {headers: {'Content-Type': 'audio/wav', 'X-Generation': String(gen)}, signal: epoch.abort.signal});
    if (!epoch.valid(gen)) return;
    // Keep the full transcript visible. TTS has a separate 300-character boundary.
    $('transcript').value = result.text; render('ready'); $('record-hint').textContent = '本轮转写完成。';
    message(result.text ? '文字已就绪，可以编辑后回读。' : '没有识别到文字，请重新录音。');
  } catch (error) { failed(error, gen); }
}
async function speak() {
  const text = $('transcript').value.trim();
  if (!text || Array.from(text).length > 300) { message('回读内容需要 1–300 字，请先编辑。', true); return; }
  let gen;
  // Resume inside the click gesture so delayed network audio is playable.
  localStop(); const audio = new AudioContext(); context = audio;
  const resumed = audio.resume();
  try {
    gen = epoch.next();
    await api('/begin', 'POST', {generation: gen, reuse_turn: turnReady}, {signal: epoch.abort.signal});
    if (!epoch.valid(gen)) return;
    turnReady = true;
    await resumed; render('processing'); message('正在合成完整语音，不会自动重复提交。');
    const bytes = await api('/tts', 'POST', {generation: gen, text}, {signal: epoch.abort.signal, audio: true});
    if (!epoch.valid(gen)) return;
    const buffer = await audio.decodeAudioData(bytes);
    if (!epoch.valid(gen)) return;
    playback = audio.createBufferSource(); playback.buffer = buffer; playback.connect(audio.destination);
    playback.onended = () => {
      if (!epoch.valid(gen)) return;
      localStop(); render('ready'); message('回读完成。可以修改文字，或开始新一轮。');
      const endGen = epoch.next();
      api('/stop', 'POST', {generation: endGen}).catch(error => failed(error, endGen));
    };
    playback.start(); render('speaking'); message('电脑正在播放；“停止”会立即静音。');
    await state('speaking', gen);
  } catch (error) { failed(error, gen); }
}
async function refresh() {
  try {
    const data = await api('/health'); suggestedAddress = data.device_address;
    $('service-url').textContent = data.voice_url;
    $('voice-status').textContent = data.voice_error ? '离线' : '在线';
    $('engine-status').textContent = data.voice_error ? data.voice_error.message : `本地引擎：${data.voice.ready ? '已就绪' : '正在加载或尚未就绪'}；云端能力以服务配置为准。`;
    paintRobot(data.robot);
    if (data.capabilities && data.capabilities.protocol_version !== 1) message('接口协议版本不兼容，请更新独立语音服务。', true);
  } catch (error) { $('voice-status').textContent = '工作台断开'; failed(error); }
}
function paintRobot(robot) {
  $('robot-status').textContent = robot.connected ? '已连接' : '离线 · 语音仍可用';
  $('receipt').textContent = robot.error || (robot.receipt ? `设备回执 ${robot.receipt}` : '未收到设备回执');
  $('unpair').disabled = !connected || !robot.enabled;
}
async function connect(replace = false) {
  if (replace && !confirm('接管会使已有语音会话失效。确认接管？')) return;
  localStop(); epoch.next(); client = crypto.randomUUID(); $('connect').disabled = true;
  try {
    await api('/session', 'POST', {replace}); epoch.value = 0; connected = true; dirty = false; turnReady = false;
    $('asr').value = $('tts').value = 'local'; $('audio-consent').checked = $('text-consent').checked = false;
    $('settings-status').textContent = '本地 / 本地 · 上传关闭'; $('takeover').hidden = true;
    render('idle'); message('已连接，默认全部本地。可直接录音，或输入文字回读。'); $('record-hint').textContent = '准备好时，开始录音。';
  } catch (error) { if (error.code === 'SESSION_BUSY') $('takeover').hidden = false; failed(error); }
  finally { $('connect').disabled = false; }
}
async function apply() {
  const routing = {asr: $('asr').value, tts: $('tts').value, allow_audio_upload: $('audio-consent').checked, allow_text_upload: $('text-consent').checked};
  if ((routing.asr === 'cloud' && !routing.allow_audio_upload) || (routing.tts === 'cloud' && !routing.allow_text_upload)) { message('请单独勾选所选云端路径的上传许可，或切回本地。', true); return; }
  localStop(); const gen = epoch.next();
  try {
    await api('/settings', 'PATCH', {generation: gen, routing});
    if (!epoch.valid(gen)) return;
    dirty = false; render('idle'); $('settings-status').textContent = `${routing.asr === 'local' ? '本地' : '云端'} / ${routing.tts === 'local' ? '本地' : '云端'} · 已应用`;
    message('设置已应用。新请求使用新路径，旧结果不会播放。');
  } catch (error) { failed(error, gen); }
}
async function release() {
  localStop(); epoch.next(); connected = false; render('idle');
  try { await api('/session', 'DELETE'); message('已释放语音会话。'); } catch (error) { message(error.message, true); }
}
async function heartbeat() {
    if (!connected || polling) return;
    const tab = client;
  polling = true;
  try { const data = await api('/session', 'GET', undefined, {signal: AbortSignal.timeout(4000)}); if (client === tab) paintRobot(data.robot); }
  catch (error) { if (client === tab) { localStop(); epoch.next(); connected = false; render('idle'); message(`会话连接已失效，已停止本地播放。${error.message}`, true); } }
  finally { polling = false; }
}
for (const id of ['asr', 'tts', 'audio-consent', 'text-consent']) $(id).addEventListener('change', () => {
  dirty = true; $('settings-status').textContent = '尚未应用 · 已停止当前操作';
  stop(); render();
  // Revocation is immediate at the service too, even before Apply. Selected routes
  // fall back to local when their independent permission was revoked.
  if (connected && (id === 'audio-consent' || id === 'text-consent') && !$(id).checked) {
    if (id === 'audio-consent') $('asr').value = 'local'; else $('tts').value = 'local';
    apply();
  }
});
$('record').onclick = record; $('finish').onclick = finish; $('stop').onclick = stop; $('speak').onclick = speak;
$('connect').onclick = () => connect(); $('takeover').onclick = () => connect(true); $('release').onclick = release;
$('apply').onclick = apply; $('refresh').onclick = refresh; $('transcript').oninput = () => render();
$('scan').onclick = async () => {
  $('scan').disabled = true; message('扫描蓝牙设备中…');
  try {
    const {devices} = await api('/devices'); $('device').replaceChildren();
    for (const item of devices) $('device').add(new Option(`${item.name} · ${item.address}`, item.address));
    if (devices.some(x => x.address === suggestedAddress)) $('device').value = suggestedAddress;
    $('device').disabled = !devices.length; $('pair').disabled = !devices.length;
    message(devices.length ? '选择设备后连接。首次配对请同时检查设备 Pair 状态。' : '未发现设备。检查 BLE 开关、Pair 状态和电脑蓝牙。');
  } catch (error) { message(error.message, true); }
  finally { $('scan').disabled = !connected; }
};
$('pair').onclick = async () => { $('pair').disabled = true; try { paintRobot(await api('/device', 'POST', {address: $('device').value})); message('蓝牙已连接；回执不等于实屏效果，请看设备。'); } catch (error) { message(error.message, true); } finally { $('pair').disabled = false; } };
$('unpair').onclick = async () => { try { paintRobot(await api('/device', 'DELETE')); } catch (error) { message(error.message, true); } };
window.addEventListener('pagehide', () => { localStop(); epoch.next(); if (connected) api('/session', 'DELETE', undefined, {keepalive: true}).catch(() => {}); });
render(); refresh(); setInterval(heartbeat, 1000);
