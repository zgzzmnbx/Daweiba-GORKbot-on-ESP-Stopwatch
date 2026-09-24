import {Epoch} from './pcm.js';
import {Recorder, WavPlayer} from './audio-client.js';
import {createDebugConsole} from './debug-console.js';

const $ = id => document.getElementById(id);
let debugStorage;
try { debugStorage = window.localStorage; } catch {}
const debugConsole = createDebugConsole(document, debugStorage, text => navigator.clipboard.writeText(text));
const face = window.GorkAvatar?.mount($('gork-face'));
const characterFace = face;
let manualPreview = false, lastFaceState = '', renderedPage = '';
function shareAvatarScene(expression, mode = 'loop', startedAt = Date.now()) {
  window.gorkDesktop?.setAvatarScene?.({expression, mode, startedAt})?.catch(() => {});
}
let appliedTts = '';
let recordingPending = false, connectionPending = false, previewSerial = 0;
for (const id of ['auto-read', 'expression-follow']) {
  try { $(id).checked = window.localStorage?.getItem('gork.' + id) !== 'false'; } catch { $(id).checked = true; }
}
$('tts').value = 'cloud';
const consentIds = ['audio-consent','text-consent','answer-consent'];
for (const id of consentIds) {
  let saved = null;
  try { saved = window.localStorage?.getItem('gork.' + id); } catch {}
  $(id).checked = saved !== 'false';
}
const epoch = new Epoch();
let client = crypto.randomUUID(), connected = false, workspace = false, dirty = false, phase = 'idle';
let turnReady = false;
let context, playback, deadline;
let previewContext, previewPlayback, robotConnected = false;
const previewPlayer = new WavPlayer();
const recorder = new Recorder();
let delayBusy = false, outputPending = false, composerWatchAudio = false, composerWatchProgress = '';
let tick = false, polling = false, suggestedAddress = '';
let capabilities = null, serviceStarting = false, startupVoiceTimer = null;
const startupVoice = {enabled: true, done: false, active: false, attempts: 0, maxAttempts: 60};
let savedSpeech = {speaker_id:3, cloud_voice:'Cherry', speed:1.0};
try {
  const saved = JSON.parse(window.localStorage?.getItem('gork.speech') || 'null');
  if (saved && typeof saved === 'object') savedSpeech = {...savedSpeech,...saved};
  for (const id of ['asr','tts']) {
    const value = window.localStorage?.getItem('gork.' + id);
    if (['local','cloud'].includes(value)) $(id).value = value;
  }
} catch {}
if (!$('text-consent').checked) $('tts').value = 'local';
if (!$('audio-consent').checked) $('asr').value = 'local';
$('voice-speed').value = String(savedSpeech.speed);
const labels = {idle: '待机', listening: '正在聆听', processing: '处理中', speaking: '正在回读', ready: '文字已就绪', error: '请检查连接'};
$('output-mode').value = 'pc';
$('bubble-target').value = 'watch';

function message(text, error = false) {
  $('message').textContent = text; $('message').className = 'message' + (error ? ' error' : '');
  // Raw failures may contain provider payloads. Keep them out of telemetry history.
  debugConsole.push('UI', error ? '操作失败；请查看工作区提示（原始错误不写入日志）' : text, error);
}
function addMessage(role, text) {
  if (!document.createElement) return;
  $('empty-chat')?.remove();
  const row = document.createElement('article'); row.className = 'chat-message ' + role;
  const label = document.createElement('small'); label.textContent = role === 'user' ? '你' : 'Gork';
  const content = document.createElement('div'); content.textContent = text;
  row.append(label, content);
  if (role === 'assistant') {
    const actions = document.createElement('div'); actions.className = 'actions compact';
    const read = document.createElement('button'); read.textContent = '朗读';
    read.onclick = () => speak(false, text);
    const copy = document.createElement('button'); copy.textContent = '复制';
    copy.onclick = async () => { try { await navigator.clipboard.writeText(text); message('已复制。'); } catch { message('无法访问剪贴板，请选择文字复制。', true); } };
    actions.append(read, copy); row.append(actions);
  }
  $('chat-log').append(row); $('chat-log').scrollTop = $('chat-log').scrollHeight;
}
function navigate() {
  if (!globalThis.location) return;
  const page = ['dialogue', 'character', 'watch', 'settings', 'logs'].includes(location.hash.slice(1)) ? location.hash.slice(1) : 'dialogue';
  if (location.hash !== `#${page}`) history.replaceState(null, '', `#${page}`);
  document.querySelectorAll?.('[data-page]').forEach(item => { item.hidden = item.dataset.page !== page; });
  document.querySelectorAll?.('[data-page-link]').forEach(item => {
    const active = item.dataset.pageLink === page;
    item.classList.toggle('active', active); item.setAttribute('aria-selected', String(active)); item.tabIndex = active ? 0 : -1;
  });
  if (renderedPage && renderedPage !== page && (phase === 'listening' || recordingPending)) stop();
  renderedPage = page;
}
function render(next = phase) {
  phase = next; document.body.dataset.phase = phase;
  const faceState = $('expression-follow').checked ? next : 'idle';
  if (!manualPreview && faceState !== lastFaceState) {
    const startedAt = Date.now();
    face?.set(faceState, {startedAt, force:true}); shareAvatarScene(faceState, 'loop', startedAt); lastFaceState = faceState;
  }
  $('companion-phase').textContent = labels[phase] || '待机';
  $('robot-voice-summary').textContent = connected ? labels[phase] : '未连接';
  $('robot-device-summary').textContent = robotConnected ? '已连接' : '未连接';
  $('robot-route-summary').textContent = (appliedTts || $('tts').value) === 'cloud' ? '云端朗读' : '本地朗读';
  debugConsole.push('VOICE', `${connected ? '会话已连接' : '会话未连接'} · ${labels[phase] || '待机'} · ${$('robot-route-summary').textContent}`);
  $('quick-connect').textContent = connected ? '语音已连接' : '连接语音';
  $('quick-connect').disabled = connected || connectionPending;
  $('phase').textContent = connected ? labels[phase] : '未连接';
  const busy = ['listening', 'processing', 'speaking'].includes(phase);
  $('voice-preview').disabled = !connected || dirty || busy || delayBusy;
  $('voice-stop').disabled = !connected;
  $('voice-start').disabled = serviceStarting;
  $('record').disabled = !connected || !appliedTts || busy || delayBusy; $('record').hidden = phase === 'listening';
  $('finish').hidden = phase !== 'listening'; $('stop').disabled = !connected;
  const output = $('output-mode').value, bubbleTarget = $('bubble-target').value;
  const text = $('transcript').value.trim(), answerMode = $('interaction-mode').value === 'answer';
  const watchTarget = bubbleTarget !== 'desktop';
  const watchBytes = new TextEncoder().encode(text).length;
  const bubbleTooLong = output === 'bubble' && !answerMode && watchTarget && (Array.from(text).length > 24 || watchBytes > 72);
  $('bubble-target-control').hidden = output !== 'bubble';
  $('speak').disabled = busy || delayBusy || outputPending || !text || bubbleTooLong ||
    (output === 'pc' && (!connected || !appliedTts)) ||
    (output === 'bubble' && (!workspace || (watchTarget && !robotConnected) || (answerMode && !connected))) ||
    (output === 'watch-audio' && (!workspace || !robotConnected || !connected || !appliedTts));
  $('speak-label').textContent = output === 'bubble' ? `显示到${bubbleTarget === 'watch' ? ' Watch' : bubbleTarget === 'both' ? '两端' : '桌面'}` :
    output === 'watch-audio' ? 'Watch 朗读' : answerMode && !$('auto-read').checked ? '生成回答' : '电脑朗读';
  $('answer-status').textContent = bubbleTooLong ? `Watch 文字超限：${Array.from(text).length}/24 字、${watchBytes}/72 字节` :
    output === 'bubble' ? (!workspace ? '请先取得工作台控制权；Watch 最多 24 字、72 字节' :
      watchTarget && !robotConnected ? '请先连接 Watch；最多 24 字、72 字节' :
      watchTarget ? 'Watch 最多 24 字、72 字节；桌面最多 300 字' : '桌面小人显示 8 秒；最多 300 字') :
    output === 'watch-audio' ? (!workspace || !robotConnected ? '请先取得工作台控制权并连接 Watch；设备朗读仍是延迟实验功能' :
      '旧版 Watch 固件需进入 Audio test；新版小人页面可朗读。音频最长 10 秒') :
    !connected ? '请先连接语音，再通过电脑扬声器朗读' :
    answerMode ? '先取得 AI 回答，再按自动朗读设置决定是否播放' : '使用电脑扬声器朗读输入文字';
  $('transcript').readOnly = busy;
  $('connect').hidden = connected; $('release').hidden = !connected;
  $('scan').disabled = !workspace; $('apply').disabled = !connected;
  $('clear-answer').disabled = busy || delayBusy;
  $('sound-preview').disabled = busy;
  $('sound-play').disabled = busy || !workspace || !robotConnected;
  $('sound-stop').disabled = !robotConnected && !previewPlayer.playing;
  $('sound-volume').disabled = busy || !workspace || !robotConnected;
  $('delay-start').disabled = busy || delayBusy || !connected || !robotConnected;
  $('delay-cancel').disabled = !delayBusy;
  $('count').textContent = output === 'bubble' && watchTarget && !answerMode ?
    `${Array.from($('transcript').value).length}/24字 · ${new TextEncoder().encode($('transcript').value).length}/72B` :
    `${Array.from($('transcript').value).length} / 300`;
  $('global-voice').textContent = `语音：${connected ? labels[phase] : '未连接'}`;
  $('global-watch').textContent = `Watch：${robotConnected ? '已连接' : '未连接'}`;
  $('global-operation').textContent = delayBusy ? '设备音频任务进行中' : labels[phase] || '待机';
  $('workspace-acquire').textContent = workspace ? '已取得控制权' : '取得控制权';
  $('character-play').disabled = !workspace || busy || delayBusy;
  $('bubble-clear').disabled = !workspace || busy || delayBusy;
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
  recorder.stop();
  const oldContext = context; context = null;
  if (oldContext && oldContext.state !== 'closed') { oldContext.suspend().catch(() => {}); oldContext.close().catch(() => {}); }
}
function stopPreview() {
  previewSerial++; previewPlayer.stop();
  if (previewPlayback) { previewPlayback.onended = null; try { previewPlayback.stop(); } catch {} previewPlayback.disconnect(); previewPlayback = null; }
  const audio = previewContext; previewContext = null;
  if (audio && audio.state !== 'closed') audio.close().catch(() => {});
  render();
}
function failed(error, gen) {
  if (error.name === 'AbortError' || (gen !== undefined && !epoch.valid(gen))) return;
  recordingPending = false; localStop();
  if (error.status === 401) { connected = false; epoch.next(); $('takeover').hidden = true; }
  render('error'); message(error.message || '连接中断，请检查服务后重试。', true);
  if (connected && gen !== undefined && epoch.valid(gen)) state('error', gen).catch(() => {});
}
function clearStartupVoiceTimer() {
  if (startupVoiceTimer !== null) clearTimeout(startupVoiceTimer);
  startupVoiceTimer = null;
}
function cancelStartupVoice() {
  clearStartupVoiceTimer(); startupVoice.done = true;
}
function scheduleStartupVoice(delay = 0) {
  if (!startupVoice.enabled || startupVoice.done || startupVoice.active || connected || connectionPending
      || startupVoice.attempts >= startupVoice.maxAttempts || startupVoiceTimer !== null) return;
  startupVoiceTimer = setTimeout(() => { startupVoiceTimer = null; autoConnectVoice(); }, delay);
}
async function autoConnectVoice() {
  if (!startupVoice.enabled || startupVoice.done || startupVoice.active || connected || connectionPending) return;
  startupVoice.active = true; startupVoice.attempts += 1;
  message(startupVoice.attempts === 1 ? '正在自动连接语音…' : '语音服务尚未就绪，正在重试自动连接…');
  let result;
  try { result = await connect(false, {startup:true}); }
  catch (error) { result = {ok:false, error}; }
  finally { startupVoice.active = false; }
  if (result?.ok || connected) { startupVoice.done = true; return; }
  const code = result?.error?.code;
  if (code === 'SESSION_BUSY' || code === 'WORKSPACE_BUSY') {
    startupVoice.done = true;
    message('已有语音会话正在使用，请点击“接管会话”。', true);
    return;
  }
  if (startupVoice.attempts >= startupVoice.maxAttempts) {
    startupVoice.done = true;
    message('开机自动连接语音失败，请点击“连接语音”重试。', true);
    return;
  }
  scheduleStartupVoice(1000);
}
async function stop() {
  turnReady = false;
  recordingPending = false; localStop(); const gen = epoch.next(); render('idle'); message('已停止本地录音与播放，正在取消服务请求。');
  const deviceCancel = robotConnected ? api('/device/audio', 'DELETE').catch(() => {}) : Promise.resolve();
  if (connected) {
    try { await api('/stop', 'POST', {generation: gen}); if (epoch.valid(gen)) message('已停止。旧结果不会继续播放；已提交的云端请求可能仍产生费用。'); }
    catch (error) { failed(error, gen); }
  }
  await deviceCancel;
  delayBusy = false; render();
}
async function stopAll() {
  stopPreview();
  await stop();
  try { const result = await api('/desktop/stop', 'POST'); if (Number.isInteger(result.generation)) epoch.value = Math.max(epoch.value, result.generation); message('已停止电脑音频、在途语音与设备操作；设备停止回执以实际返回为准。'); }
  catch (error) { message(error.message, true); }
}
async function state(name, gen) { await api('/state', 'POST', {generation: gen, state: name}, {signal: epoch.abort.signal}); }
async function begin() {
  manualPreview = false; localStop(); const gen = epoch.next();
  await api('/begin', 'POST', {generation: gen}, {signal: epoch.abort.signal});
  if (!epoch.valid(gen)) throw new DOMException('旧操作', 'AbortError');
  turnReady = true;
  return gen;
}
async function record() {
  if (!connected || !appliedTts || delayBusy || ['listening','processing','speaking'].includes(phase)) return;
  recordingPending = true; render('processing');
  let gen;
  try {
    gen = await begin(); render('processing');
    const recorderStarted = await recorder.start({maxSeconds: 30});
    if (!recorderStarted || !epoch.valid(gen)) return;
    await state('listening', gen);
    if (!epoch.valid(gen)) return;
    recordingPending = false; render('listening'); message('正在收音。结束后可编辑识别文字，再点击回读。');
    const started = performance.now();
    tick = setInterval(() => { $('record-hint').textContent = `正在录音 ${Math.min(30, (performance.now() - started) / 1000).toFixed(1)} / 30 秒`; }, 100);
    deadline = setTimeout(finish, 30000);
  } catch (error) { failed(error, gen); }
}
async function finish() {
  if (phase !== 'listening') return;
  const gen = epoch.value, wav = recorder.finish();
  localStop(); render('processing'); $('record-hint').textContent = '录音已结束，正在转写…';
  try {
    const result = await api('/asr', 'POST', wav, {headers: {'Content-Type': 'audio/wav', 'X-Generation': String(gen)}, signal: epoch.abort.signal});
    if (!epoch.valid(gen)) return;
    // Keep the full transcript visible. TTS has a separate 300-character boundary.
    $('transcript').value = result.text; render('ready'); $('record-hint').textContent = '本轮转写完成。';
    message(result.text ? '文字已就绪，可以编辑后回读。' : '没有识别到文字，请重新录音。');
  } catch (error) { failed(error, gen); }
}
async function speak(preview = false, explicitText = null) {
  if (!connected || !appliedTts || (preview && dirty) || delayBusy || ['listening','processing','speaking'].includes(phase)) return;
  const text = preview ? '你好，我是 Gork。这是当前音色的试听。' : (explicitText ?? $('transcript').value.trim());
  if (!text || Array.from(text).length > 300) { message('回读内容需要 1–300 字，请先编辑。', true); return; }
  manualPreview = false; render('processing');
  if (!preview && explicitText === null) addMessage('user', text);
  let gen;
  // Resume inside the click gesture so delayed network audio is playable.
  localStop(); const audio = new AudioContext(); context = audio;
  const resumed = audio.resume();
  try {
    gen = epoch.next();
    await api('/begin', 'POST', {generation: gen, reuse_turn: turnReady}, {signal: epoch.abort.signal});
    if (!epoch.valid(gen)) return;
    turnReady = true;
    await resumed; render('processing');
    let spoken = text;
    if (!preview && explicitText === null && $('interaction-mode').value === 'answer') {
      message('正在请求回答；内容仅发送给已配置的文字回答服务。');
      const result = await api('/answer', 'POST', {generation: gen, text}, {signal: epoch.abort.signal});
      if (!epoch.valid(gen)) return;
      spoken = result.text; addMessage('assistant', spoken); render('processing');
      if (!$('auto-read').checked || Array.from(spoken).length > 300) {
        localStop(); render('ready');
        message(Array.from(spoken).length > 300 ? '回答已完整显示，超过 300 字未自动朗读；可复制片段后朗读。' : '回答已显示；自动朗读已关闭。');
        return;
      }
    }
    message('正在合成完整语音，不会自动重复提交。');
    const bytes = await api('/tts', 'POST', {generation: gen, text: spoken}, {signal: epoch.abort.signal, audio: true});
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
async function displayComposerText() {
  const original = $('transcript').value.trim(), target = $('bubble-target').value;
  const answerMode = $('interaction-mode').value === 'answer';
  if (!original || !workspace || (target !== 'desktop' && !robotConnected) || (answerMode && !connected) || outputPending) return;
  if (!answerMode && target !== 'desktop' && (Array.from(original).length > 24 || new TextEncoder().encode(original).length > 72)) {
    message('Watch 文字最多 24 字、72 字节，请缩短后发送。', true); return;
  }
  outputPending = true; render(); addMessage('user', original);
  let gen;
  try {
    gen = answerMode ? await begin() : epoch.next();
    let text = original;
    if (answerMode) {
      message('正在获取 AI 回答，回答不会自动截断。');
      text = (await api('/answer', 'POST', {generation:gen, text:original}, {signal:epoch.abort.signal})).text;
      if (!epoch.valid(gen)) return;
      addMessage('assistant', text);
    }
    if (target !== 'desktop' && (Array.from(text).length > 24 || new TextEncoder().encode(text).length > 72)) {
      message('文字已显示在会话中，但超过 Watch 的 24 字或 72 字节限制，未发送到任何小人；请缩短文字。', true); return;
    }
    const result = await api('/character/bubble', 'POST', {text, target}, {signal:epoch.abort.signal});
    if (!epoch.valid(gen)) return;
    characterResult(result);
    const desktopOk = !result.desktop?.requested || result.desktop.accepted;
    const watchOk = !result.watch?.requested || result.watch.accepted;
    message(desktopOk && watchOk ? '文字已发送到所选小人；Watch 实屏效果请以设备为准。' :
      `文字未完整送达：${$('character-result').textContent}`, !(desktopOk && watchOk));
  } catch (error) {
    if (answerMode) failed(error, gen);
    else if (error.name !== 'AbortError' && epoch.valid(gen)) message(error.message || '文字发送失败。', true);
  } finally { outputPending = false; render(); }
}
async function speakOnWatch() {
  const original = $('transcript').value.trim(), answerMode = $('interaction-mode').value === 'answer';
  if (!original || !connected || !appliedTts || !workspace || !robotConnected || delayBusy) return;
  delayBusy = true; composerWatchAudio = true; composerWatchProgress = '';
  render('processing'); addMessage('user', original);
  let gen;
  try {
    gen = await begin();
    let text = original;
    if (answerMode) {
      message('正在获取 AI 回答。');
      text = (await api('/answer', 'POST', {generation:gen, text:original}, {signal:epoch.abort.signal})).text;
      if (!epoch.valid(gen)) return;
      addMessage('assistant', text);
    }
    if (!text || Array.from(text).length > 300) throw new Error('文字超过 300 字，已保留在会话中，未合成或发送到 Watch。');
    message('正在合成完整语音；新版 Watch 可在小人页朗读，旧版请保持 Audio test 页面。');
    const wav = await api('/tts', 'POST', {generation:gen, text}, {signal:epoch.abort.signal, audio:true});
    if (!epoch.valid(gen)) return;
    if (wav.byteLength > 484096) throw new Error('合成音频超过 Watch 的 10 秒上限，未发送到设备。');
    const job = await api('/device/audio/play', 'POST', wav, {headers:{'Content-Type':'audio/wav'}, signal:epoch.abort.signal});
    if (!epoch.valid(gen)) return;
    await waitAudio(job.job_id, gen, 'played');
    if (epoch.valid(gen)) { render('ready'); message('Watch 报告播放完成；实际听感请以设备为准。'); }
  } catch (error) { failed(error, gen); }
  finally { delayBusy = false; composerWatchAudio = false; composerWatchProgress = ''; render(); }
}
function submitComposer() {
  const output = $('output-mode').value;
  if (output === 'bubble') return displayComposerText();
  if (output === 'watch-audio') return speakOnWatch();
  return speak();
}
async function refresh() {
  try {
    const data = await api('/health'); suggestedAddress = data.device_address;
    startupVoice.enabled = data.auto_connect_voice !== false;
    if (!startupVoice.enabled) { clearStartupVoiceTimer(); startupVoice.done = true; }
    $('service-url').textContent = data.voice_url;
    $('voice-status').textContent = data.voice_error ? '离线' : '在线';
    $('engine-status').textContent = data.voice_error ? data.voice_error.message : `本地引擎：${data.voice.ready ? '已就绪' : '正在加载或尚未就绪'}；云端能力以服务配置为准。`;
    const service = data.voice_service || {};
    debugConsole.push('SERVICE', data.voice_error ? '语音服务离线' : data.voice?.ready ? '语音服务就绪' : '语音模型加载中');
    serviceStarting = service.mode === 'starting';
    $('voice-lifecycle').textContent = serviceStarting ? '后台启动中…可留在此页面等待。' :
      data.voice_error ? (service.error || '服务离线，可点击启动 / 重试。') :
      service.owned ? '由 Gork 托管 · 退出控制台时关闭' : '复用已运行的服务 · 退出控制台不会关闭它';
    const voiceCatalogue = caps => JSON.stringify([caps?.tts?.speakers,caps?.cloud?.voices,caps?.cloud?.request_voice]);
    if (data.capabilities && voiceCatalogue(data.capabilities) !== voiceCatalogue(capabilities)) {
      capabilities = data.capabilities; fillVoices();
    }
    paintRobot(data.robot);
    const answer = data.answer || {enabled:false, reason:'未配置回答服务；当前为跟读/朗读模式'};
    $('answer-option').disabled = !answer.enabled;
    $('answer-option').textContent = answer.enabled ? 'AI 回答' : 'AI 回答（未配置）';
    if (!answer.enabled && $('interaction-mode').value === 'answer') $('interaction-mode').value = 'read';
    render();
    if (data.capabilities && data.capabilities.protocol_version !== 1) message('接口协议版本不兼容，请更新独立语音服务。', true);
    if (startupVoice.enabled && !startupVoice.done && !connected && !connectionPending) {
      const ready = !data.voice_error && data.voice && data.voice.ready !== false;
      scheduleStartupVoice(ready ? 0 : 1000);
    }
  } catch (error) {
    $('voice-status').textContent = '工作台断开'; failed(error);
    scheduleStartupVoice(1000);
  }
}
function fillVoices() {
  const cloud = $('tts').value === 'cloud';
  $('voice-speed').disabled = cloud;
  $('voice-speed').value = cloud ? '1' : String(savedSpeech.speed);
  if (!capabilities) return;
  const list = cloud ? capabilities.cloud?.voices || [] : capabilities.tts?.speakers || [];
  const select = $('voice-select');
  select.replaceChildren();
  for (const item of list) select.add(new Option(item.label, String(item.id)));
  const desired = String(cloud ? savedSpeech.cloud_voice : savedSpeech.speaker_id);
  if (list.some(item => String(item.id) === desired)) select.value = desired;
  select.disabled = !list.length;
  $('voice-speed').disabled = cloud;
  $('voice-speed').value = cloud ? '1' : String(savedSpeech.speed);
  $('voice-hint').textContent = cloud ? (capabilities.cloud?.request_voice ?
    '云端试听会上传固定示例文字并可能计费；当前接口仅支持 1.0×。' :
    '当前运行的是旧语音服务，仅提供默认音色；更新服务后可选择更多音色。') :
    '本地合成，不上传文字。选择音色后点击应用设置，再试听。';
}
function speechSettings() {
  const cloud = $('tts').value === 'cloud';
  return {speaker_id: cloud ? Number(savedSpeech.speaker_id) : Number($('voice-select').value || 3),
    cloud_voice: cloud ? $('voice-select').value || 'Cherry' : savedSpeech.cloud_voice,
    speed: cloud ? 1.0 : Number($('voice-speed').value || 1)};
}
function paintRobot(robot) {
  robotConnected = Boolean(robot.connected);
  debugConsole.push('BLE', robotConnected ? 'StopWatch 已连接' : 'StopWatch 未连接');
  debugConsole.push('DEVICE', robot.error ? '设备操作异常；展开设备诊断查看' : robot.receipt ? '已收到设备回执（不代表实屏/发声验收）' : '等待设备回执', Boolean(robot.error));
  $('robot-status').textContent = robot.connected ? '已连接' : '离线 · 语音仍可用';
  $('receipt').textContent = robot.error || (robot.receipt ? `设备回执 ${robot.receipt}` : '未收到设备回执');
  $('watch-diagnostics').textContent = robot.error || (robot.receipt ? `最近回执：${robot.receipt}` : '暂无设备回执。');
  $('unpair').disabled = !workspace || !robot.enabled;
  render();
}
async function previewSound() {
  stopPreview(); const serial = previewSerial;
  try {
    const bytes = await api(`/sounds/${$('sound-select').value}/preview`, 'GET', undefined, {audio: true});
    if (serial !== previewSerial) return;
    await previewPlayer.play(bytes, () => { render(); message('电脑试听完成；未向设备发送命令。'); });
    render(); message('电脑正在试听内置声音样本。');
  } catch (error) { stopPreview(); message(error.message || '电脑试听失败。', true); }
}
async function deviceSound(method, path, body) {
  try {
    const result = await api(path, method, body);
    const eventNames = {128:'已接受',129:'正在播放',130:'播放完成',131:'已停止',132:'状态已更新'};
    const label = result.event_name || eventNames[result.event] || result.status || '已完成';
    $('receipt').textContent = `声音回执 ${label}`;
    message(method === 'DELETE' ? '已向设备发送停止命令。' : '设备声音命令已收到有效回执；实际声音请以设备为准。');
    return result;
  } catch (error) { message(error.message, true); }
}
function delayStatus(value) {
  const names = {starting:'正在建立音频会话',armed:'设备已 ARM，请按住 A',recording:'设备正在录音',receiving:'设备 → 电脑传输',received:'接收完成',sending:'电脑 → 设备传输',playing:'设备报告开始播放',played:'设备报告播放结束',cancelled:'已取消',error:'失败'};
  const percent = value.total ? Math.min(100, value.bytes * 100 / value.total) : 0;
  $('delay-progress').value = percent;
  const speed = value.rate ? ` · ${Math.round(value.rate)} B/s` : '';
  const codec = value.codec === 'opus' ? 'Opus' : value.codec === 'pcm16' ? 'PCM' : '格式待协商';
  const compression = value.codec === 'opus' && value.source_bytes
    ? ` · 原始 ${Math.round(value.source_bytes / 1024)} KB`
    : '';
  $('delay-status').textContent = `${names[value.stage] || value.stage} · ${codec} ${value.bytes || 0}/${value.total || '?'} bytes${compression} · ${percent.toFixed(1)}%${speed}`;
  const summary = `${names[value.stage] || '设备音频处理中'} · ${codec} · ${Math.floor(percent / 10) * 10}%`;
  debugConsole.push('AUDIO', summary, value.stage === 'error');
  if (composerWatchAudio && summary !== composerWatchProgress) {
    composerWatchProgress = summary;
    message(`Watch 朗读：${summary}`);
  }
}
async function waitAudio(jobId, gen, expectedStage) {
  while (epoch.valid(gen)) {
    const value = await api('/device/audio'); delayStatus(value);
    if (value.job_id !== jobId) throw new Error('设备音频任务已被替换');
    if (!value.running) {
      if (value.stage === 'cancelled') throw new Error('设备音频任务已取消');
      if (value.stage === 'error' || value.error)
        throw new Error(value.error || 'Watch 音频任务失败，未收到成功回执；请打开设备的 Audio test 页面后重试');
      if (value.stage !== expectedStage)
        throw new Error(`设备音频任务意外结束（${value.stage || '未知状态'}），尚未收到${expectedStage === 'played' ? '播放完成' : '录音接收完成'}回执`);
      return value;
    }
    await new Promise(resolve => setTimeout(resolve, 300));
  }
  throw new DOMException('旧操作', 'AbortError');
}
async function playOnPc(bytes, gen) {
  const audio = new AudioContext(); context = audio; await audio.resume();
  const buffer = await audio.decodeAudioData(bytes); if (!epoch.valid(gen)) return;
  playback = audio.createBufferSource(); playback.buffer = buffer; playback.connect(audio.destination);
  const active = playback; active.onended = () => { if (playback === active) playback = null; };
  active.start(); render('speaking'); message('电脑正在播放设备录音；“停止”会立即静音。');
  while (epoch.valid(gen) && playback === active) await new Promise(resolve => setTimeout(resolve, 100));
  if (epoch.valid(gen)) { localStop(); render('ready'); }
}
async function delayedAudio() {
  let gen;
  try {
    delayBusy = true; render('processing'); gen = await begin();
    const mode = $('delay-mode').value;
    const job = await api('/device/audio/record', 'POST', {echo:false});
    message('设备已准备录音；请在 Audio test 页按住 A，说完松开。');
    await waitAudio(job.job_id, gen, 'received');
    const wav = await api(`/device/audio/result/${job.job_id}`, 'GET', undefined, {audio:true});
    if (mode === 'device-pc') await playOnPc(wav, gen);
    else {
      render('processing'); message('设备录音已接收，正在识别。');
      const asr = await api('/asr', 'POST', wav, {headers:{'Content-Type':'audio/wav','X-Generation':String(gen)},signal:epoch.abort.signal});
      let text = asr.text;
      if ($('interaction-mode').value === 'answer') text = (await api('/answer','POST',{generation:gen,text},{signal:epoch.abort.signal})).text;
      if (Array.from(text).length > 300) throw new Error('处理结果超过 300 字，未合成或发送；请改用电脑输出');
      $('transcript').value = text; render('processing');
      const reply = await api('/tts','POST',{generation:gen,text},{signal:epoch.abort.signal,audio:true});
      const output = await api('/device/audio/play','POST',reply,{headers:{'Content-Type':'audio/wav'}});
      await waitAudio(output.job_id, gen, 'played');
    }
    if (epoch.valid(gen)) { render('ready'); message('延迟音频任务完成；实际听感请以播放端为准。'); }
  } catch (error) { failed(error, gen); }
  finally { delayBusy = false; render(); }
}
async function connect(replace = false, {startup = false} = {}) {
  if (connectionPending) return;
  if (replace && !confirm('接管会使已有语音会话失效。确认接管？')) return;
  if (!startup) cancelStartupVoice();
  connectionPending = true; localStop(); epoch.next(); $('connect').disabled = true; render();
  try {
    await api('/session', 'POST', {replace}); epoch.value = 0; connected = true; workspace = true; dirty = true; appliedTts = ''; turnReady = false;
    $('takeover').hidden = true;
    await apply();
    $('record-hint').textContent = '准备好时，开始录音。';
    return {ok:true};
  } catch (error) {
    if (error.code === 'SESSION_BUSY' || error.code === 'WORKSPACE_BUSY') $('takeover').hidden = false;
    if (!startup) failed(error);
    return {ok:false, error};
  }
  finally { connectionPending = false; $('connect').disabled = false; render(); }
}
async function apply(revoking = false) {
  const routing = {asr: $('asr').value, tts: $('tts').value, allow_audio_upload: $('audio-consent').checked, allow_text_upload: $('text-consent').checked};
  if ((routing.asr === 'cloud' && !routing.allow_audio_upload) || (routing.tts === 'cloud' && !routing.allow_text_upload)) { message('请单独勾选所选云端路径的上传许可，或切回本地。', true); return; }
  localStop(); const gen = epoch.next();
  try {
    const speech = speechSettings();
    await api('/settings', 'PATCH', {generation: gen, routing, allow_answer_upload: $('answer-consent').checked, speech: revoking ? null : speech});
    if (!epoch.valid(gen)) return;
    if (!revoking) savedSpeech = {...speech, speed: routing.tts === 'cloud' ? savedSpeech.speed : speech.speed};
    try {
      window.localStorage?.setItem('gork.speech', JSON.stringify(savedSpeech));
      for (const id of ['asr','tts']) window.localStorage?.setItem('gork.' + id, routing[id]);
    } catch {}
    dirty = Boolean(revoking); appliedTts = routing.tts; render('idle'); $('settings-status').textContent = `${routing.asr === 'local' ? '本地' : '云端'} / ${routing.tts === 'local' ? '本地' : '云端'} · 已应用`;
    if (revoking) { $('settings-status').textContent = '上传许可已撤销 · 音色草稿仍需保存'; message('上传许可已撤销，相关路径已停止。'); }
    else message('设置已应用。新请求使用新路径，旧结果不会播放。');
  } catch (error) { appliedTts = ''; failed(error, gen); }
}
async function release() {
  localStop(); epoch.next(); connected = false; render('idle');
  try { await api('/voice/session', 'DELETE'); message('已释放语音会话；角色和 StopWatch 控制权保留。'); } catch (error) { message(error.message, true); }
}
async function acquireWorkspace(replace = false) {
  if (replace && !confirm('接管会使另一窗口的操作失效。确认接管工作台？')) return;
  try {
    const result = await api('/workspace', 'POST', {replace}); workspace = true;
    if (Number.isInteger(result.generation)) epoch.value = Math.max(epoch.value, result.generation);
    $('character-status').textContent = result.voice_connected ? '工作台与语音已连接' : '工作台控制中';
    $('workspace-takeover').hidden = true; render(); message('已取得工作台控制权；语音服务仍按需连接。');
  } catch (error) {
    if (error.code === 'WORKSPACE_BUSY') { $('workspace-takeover').hidden = false; message('另一窗口正在控制；如需接管，请点击“接管工作台”。', true); }
    else message(error.message, true);
  }
}
function characterOptions() {
  const names = [...new Set([...(window.GorkCatalog?.sequences || []).map(item => item.id), 'happy-work'])];
  const select = $('character-expression'); select.replaceChildren();
  const chinese = {waking:'醒来',searching:'搜索',working:'工作',suspicious:'怀疑',idle:'待机',listening:'聆听',thinking:'思考',happy:'开心',excited:'兴奋',surprised:'惊讶',confused:'疑惑',angry:'生气',sleeping:'睡觉',drowsy:'困倦',love:'喜爱',wink:'眨眼',curious:'好奇',focused:'专注',bored:'无聊',tired:'疲惫',proud:'得意',shy:'害羞',sad:'难过',laughing:'大笑',scared:'害怕',playful:'俏皮',celebrate:'庆祝','happy-work':'开心工作（仅 StopWatch）'};
  for (const name of names) select.add(new Option((chinese[name] || name) + ' · ' + name, name));
  if (names.includes('idle')) select.value = 'idle';
}
function characterTarget() { return $('character-target').value; }
function characterResult(value) {
  const desktop = value.desktop?.requested ? (value.desktop.accepted ? '桌面：已接收' : '桌面：未接收') : '桌面：未发送';
  const watch = value.watch?.requested ? (value.watch.accepted ? `Watch：${value.watch.receipt || '已接收'}` : `Watch：${value.watch.error || '失败'}`) : 'Watch：未发送';
  $('character-result').textContent = `${desktop}；${watch}`;
}
async function previewCharacter() {
  const name = $('character-expression').value;
  if (name === 'happy-work') { message('开心工作包含设备专属纸笔层，请发送到 StopWatch 查看。'); return; }
  const startedAt = Date.now();
  manualPreview = true; characterFace?.set(name, {mode:$('character-mode').value, startedAt, force:true});
  shareAvatarScene(name, $('character-mode').value, startedAt);
  $('character-status').textContent = `正在本地预览：${name}`;
}
async function playCharacter() {
  const expression = $('character-expression').value, target = characterTarget();
  if (expression === 'happy-work' && target !== 'watch') { message('happy-work 只有 StopWatch 的纸笔层，不能发送到桌面或两端。', true); return; }
  try {
    characterResult(await api('/character', 'POST', {expression, mode:$('character-mode').value, target}));
    if (target !== 'watch') await previewCharacter();
  }
  catch (error) { message(error.message, true); }
}
async function clearBubble() {
  const target = characterTarget();
  try {
    const result = await api('/character/bubble', 'DELETE', {target});
    characterResult(result); render();
  } catch (error) { message(error.message, true); }
}
async function heartbeat() {
    if (!connected || polling) return;
    const tab = client;
  polling = true;
  try { const data = await api('/session', 'GET', undefined, {signal: AbortSignal.timeout(4000)}); if (client === tab) paintRobot(data.robot); }
  catch (error) { if (client === tab) { localStop(); epoch.next(); connected = false; render('idle'); message(`会话连接已失效，已停止本地播放。${error.message}`, true); } }
  finally { polling = false; }
}
async function workspaceHeartbeat() {
  if (!workspace || connected || polling) return;
  polling = true;
  try { const data = await api('/workspace', 'GET', undefined, {signal: AbortSignal.timeout(4000)}); paintRobot(data.robot); }
  catch (error) { workspace = false; render(); message(`工作台控制权已失效。${error.message}`, true); }
  finally { polling = false; }
}
for (const id of ['asr', 'tts', 'audio-consent', 'text-consent', 'answer-consent']) $(id).addEventListener('change', async () => {
  if (consentIds.includes(id)) {
    try { window.localStorage?.setItem('gork.' + id, String($(id).checked)); } catch {}
  }
  dirty = true; $('settings-status').textContent = '有未保存设置 · 当前会话仍使用已应用设置';
  if (consentIds.includes(id) && !$(id).checked) {
    if (id === 'audio-consent') $('asr').value = 'local';
    if (id === 'text-consent') { $('tts').value = 'local'; fillVoices(); }
    if (id === 'answer-consent') $('interaction-mode').value = 'read';
    await stop();
    if (connected) await apply(true);
  }
  render();
});
$('record').onclick = record; $('finish').onclick = finish; $('stop').onclick = stop; $('speak').onclick = submitComposer;
$('voice-preview').onclick = () => speak(true);
$('voice-stop').onclick = stop;
$('voice-start').onclick = async () => {
  serviceStarting = true; render(); $('voice-lifecycle').textContent = '正在启动语音服务…';
  try { await api('/voice-service/start', 'POST'); await refresh(); }
  catch (error) { serviceStarting = false; render(); message(error.message, true); }
};
for (const id of ['voice-select','voice-speed']) $(id).onchange = () => {
  dirty = true; $('settings-status').textContent = '音色设置未应用'; render();
};
$('tts').addEventListener('change', fillVoices);
$('connect').onclick = () => connect(); $('takeover').onclick = () => connect(true); $('release').onclick = release;
$('voice-release').onclick = release; $('workspace-acquire').onclick = () => acquireWorkspace();
$('apply').onclick = () => apply(); $('refresh').onclick = refresh; $('transcript').oninput = () => render();
$('transcript').addEventListener('keydown', event => { if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) { event.preventDefault(); submitComposer(); } });
$('output-mode').onchange = () => render(); $('bubble-target').onchange = () => render();
$('interaction-mode').onchange = () => { render(); message($('interaction-mode').value === 'answer' ? '先获取 AI 回答，再按所选方式输出；需已应用独立许可。' : '直接输出原文，不调用回答服务。'); };
$('clear-answer').onclick = async () => { try { if (connected) await api('/answer/history', 'DELETE'); $('chat-log').replaceChildren(); message('会话记录与回答上下文已清空。'); } catch (error) { message(error.message, true); } };
$('sound-preview').onclick = previewSound;
$('sound-play').onclick = () => deviceSound('POST', '/device/sound', {sound_id: Number($('sound-select').value)});
$('sound-stop').onclick = () => { stopPreview(); if (workspace && robotConnected) return deviceSound('DELETE', '/device/sound'); };
$('sound-volume').oninput = () => { $('sound-volume-label').textContent = `${$('sound-volume').value}%`; };
$('sound-volume').onchange = () => deviceSound('PUT', '/device/sound/volume', {volume: Number($('sound-volume').value)});
$('delay-start').onclick = delayedAudio;
$('delay-cancel').onclick = stop;
$('global-stop').onclick = stopAll;
$('character-preview').onclick = previewCharacter; $('character-play').onclick = playCharacter;
$('character-idle').onclick = async () => { try { if (workspace) await api('/character', 'DELETE'); manualPreview = false; lastFaceState = ''; render(); $('character-status').textContent = '已返回自动联动'; } catch (error) { message(error.message, true); } };
$('character-expression').onchange = previewCharacter;
$('bubble-clear').onclick = clearBubble;
$('scan').onclick = async () => {
  $('scan').disabled = true; message('扫描蓝牙设备中…');
  try {
    const {devices} = await api('/devices'); $('device').replaceChildren();
    for (const item of devices) $('device').add(new Option(`${item.name} · ${item.address}`, item.address));
    if (devices.some(x => x.address === suggestedAddress)) $('device').value = suggestedAddress;
    $('device').disabled = !devices.length; $('pair').disabled = !devices.length;
    message(devices.length ? '选择设备后连接。首次配对请同时检查设备 Pair 状态。' : '未发现设备。检查 BLE 开关、Pair 状态和电脑蓝牙。');
  } catch (error) { message(error.message, true); }
  finally { $('scan').disabled = !workspace; }
};
$('pair').onclick = async () => { $('pair').disabled = true; try { paintRobot(await api('/device', 'POST', {address: $('device').value})); message('蓝牙已连接；回执不等于实屏效果，请看设备。'); } catch (error) { message(error.message, true); } finally { $('pair').disabled = false; } };
$('unpair').onclick = async () => { try { paintRobot(await api('/device', 'DELETE')); } catch (error) { message(error.message, true); } };
window.addEventListener('hashchange', navigate);
window.addEventListener('blur', () => { if (phase === 'listening' || recordingPending) stop(); });
$('character-acquire').onclick = () => acquireWorkspace();
$('workspace-takeover').onclick = () => acquireWorkspace(true);
window.addEventListener('pagehide', () => { cancelStartupVoice(); stopPreview(); localStop(); epoch.next(); if (workspace) api('/workspace', 'DELETE', undefined, {keepalive: true}).catch(() => {}); });
if (window.gorkDesktop?.onStopAll) window.gorkDesktop.onStopAll(() => {
  stopPreview(); localStop(); epoch.next(); delayBusy = false; render('idle'); message('已由桌面控制台停止本地录音、播放和在途任务。');
});
characterOptions(); fillVoices(); navigate(); render(); refresh(); setInterval(heartbeat, 1000); setInterval(workspaceHeartbeat, 1000);
setInterval(refresh, 5000);

$('quick-connect').onclick = () => connect();
for (const id of ['auto-read','expression-follow']) $(id).onchange = () => {
  try { window.localStorage?.setItem('gork.' + id, String($(id).checked)); } catch {}
  if (id === 'expression-follow') { manualPreview = false; lastFaceState = ''; }
  render();
};
document.querySelectorAll?.('[data-page-link]').forEach((tab, index, tabs) => {
  tab.addEventListener('keydown', event => {
    let target;
    if (event.key === 'ArrowRight') target = (index + 1) % tabs.length;
    if (event.key === 'ArrowLeft') target = (index + tabs.length - 1) % tabs.length;
    if (event.key === 'Home') target = 0;
    if (event.key === 'End') target = tabs.length - 1;
    if (target !== undefined) { event.preventDefault(); tabs[target].focus(); location.hash = tabs[target].dataset.pageLink; }
  });
});
async function refreshDesktopVisibility() {
  if (!window.gorkDesktop?.getAvatarVisible) return;
  try { $('desktop-visible').checked = await window.gorkDesktop.getAvatarVisible(); $('desktop-visible').disabled = false; $('desktop-hint').textContent = '显示独立桌面窗口'; }
  catch { $('desktop-visible').disabled = true; }
}
$('desktop-visible').onchange = async () => {
  $('desktop-visible').disabled = true;
  try { await window.gorkDesktop.setAvatarVisible($('desktop-visible').checked); }
  catch (error) { message(error.message || '无法切换桌面小人', true); }
  await refreshDesktopVisibility();
};
refreshDesktopVisibility(); setInterval(refreshDesktopVisibility, 2000);

let avatarTopBusy = false;
async function refreshAvatarAlwaysOnTop() {
  if (!window.gorkDesktop?.getAvatarAlwaysOnTop || avatarTopBusy) return;
  try {
    $('desktop-always-on-top').checked = await window.gorkDesktop.getAvatarAlwaysOnTop();
    $('desktop-always-on-top').disabled = false;
    $('desktop-top-hint').textContent = '开启后显示在其他窗口前方，自动记住';
  } catch { $('desktop-always-on-top').disabled = true; }
}
$('desktop-always-on-top').onchange = async () => {
  if (!window.gorkDesktop?.setAvatarAlwaysOnTop) return;
  avatarTopBusy = true;
  $('desktop-always-on-top').disabled = true;
  try { await window.gorkDesktop.setAvatarAlwaysOnTop($('desktop-always-on-top').checked); }
  catch (error) { message(error.message || '无法切换始终置顶', true); }
  finally { avatarTopBusy = false; await refreshAvatarAlwaysOnTop(); }
};
refreshAvatarAlwaysOnTop(); setInterval(refreshAvatarAlwaysOnTop, 2000);

let pendingAvatarScale = null, avatarScaleBusy = false;
async function refreshAvatarScale() {
  if (!window.gorkDesktop?.getAvatarScale || avatarScaleBusy || document.activeElement === $('desktop-size')) return;
  try {
    const scale = await window.gorkDesktop.getAvatarScale();
    if (avatarScaleBusy) return;
    $('desktop-size').value = String(scale); $('desktop-size-value').textContent = `${scale}%`;
    $('desktop-size').disabled = false; $('desktop-size-hint').textContent = '只调整桌面小人，自动记住大小';
  } catch { $('desktop-size').disabled = true; }
}
async function applyAvatarScale() {
  if (avatarScaleBusy || !window.gorkDesktop?.setAvatarScale) return;
  avatarScaleBusy = true;
  try {
    while (pendingAvatarScale !== null) {
      const scale = pendingAvatarScale; pendingAvatarScale = null;
      const actual = await window.gorkDesktop.setAvatarScale(scale);
      if (pendingAvatarScale === null) { $('desktop-size').value = String(actual); $('desktop-size-value').textContent = `${actual}%`; }
    }
  } catch (error) { pendingAvatarScale = null; message(error.message || '桌面小人大小调整失败', true); }
  finally { avatarScaleBusy = false; }
}
$('desktop-size').oninput = () => {
  $('desktop-size-value').textContent = `${$('desktop-size').value}%`;
  pendingAvatarScale = Number($('desktop-size').value); applyAvatarScale();
};
refreshAvatarScale(); setInterval(refreshAvatarScale, 2000);
