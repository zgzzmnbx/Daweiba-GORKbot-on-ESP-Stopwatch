const $ = id => document.getElementById(id);
const canvas = $('waveform'), painter = canvas.getContext('2d');
let session = sessionStorage.getItem('voice-session'), generation = 0, active = null, recording = null, pendingMic = false;
let playbackContext = null, playback = null, lastBuffer = null, frames = null;
let health = null, turn = 0, capabilities = null, microphoneHeld = false;
let routing = {asr:'local',tts:'local',allow_audio_upload:false,allow_text_upload:false};
let applyingRouting = false;
const observations = [];

function notice(message = '', info = false) { $('notice').textContent = message; $('notice').hidden = !message; $('notice').classList.toggle('info', info); }
function seconds(ms) { return `${(ms / 1000).toFixed(2)} s`; }
function controls() {
  const providerReady = kind => routing[kind] === 'local' ? health?.engines?.[kind]?.state === 'ready' : health?.cloud?.state === 'configured' && routing[kind === 'asr' ? 'allow_audio_upload':'allow_text_upload'];
  const asrReady = !!session && !applyingRouting && providerReady('asr');
  const ttsReady = !!session && !applyingRouting && providerReady('tts');
  $('holdRecord').disabled = !asrReady; $('toggleRecord').disabled = !asrReady; $('upload').disabled = !asrReady;
  $('synthesize').disabled = !ttsReady || active?.kind === 'tts';
  $('copyText').disabled = !$('transcript').value.trim(); $('useText').disabled = !$('transcript').value.trim();
  $('replay').disabled = !lastBuffer || !!recording || pendingMic;
  $('exportMetrics').disabled = observations.length === 0;
  $('applyRouting').disabled = !session || applyingRouting;
  $('speaker').disabled = routing.tts === 'cloud'; $('speed').disabled = routing.tts === 'cloud';
}
function showRouting() {
  $('asrMode').value=routing.asr; $('ttsMode').value=routing.tts;
  $('allowAudio').checked=routing.allow_audio_upload; $('allowText').checked=routing.allow_text_upload;
  $('runMode').textContent=routing.asr==='local' && routing.tts==='local' ? '本地模式':'包含云端处理';
  $('routeSummary').textContent=`当前：${routing.asr==='local'?'本地识别（录音不上传）':'云端识别（上传录音）'} + ${routing.tts==='local'?'本地朗读（文字不上传）':'云端朗读（上传播报文字）'}。选择变化在下一轮生效。`;
  $('ttsPrivacy').textContent=routing.tts==='cloud'?'电脑扬声器 · 文字上传百炼北京':'电脑扬声器 · 不上传文字';
  if(routing.tts==='cloud') $('speed').value='1';
  $('speaker').hidden=routing.tts==='cloud'; $('cloudVoice').hidden=routing.tts!=='cloud';
  controls();
}
async function refreshRouting() {
  try { routing=(await (await api('/v1/settings')).json()).routing; showRouting(); } catch(error) { notice(error.message); }
}
async function applyRouting() {
  const next={asr:$('asrMode').value,tts:$('ttsMode').value,allow_audio_upload:$('allowAudio').checked,allow_text_upload:$('allowText').checked};
  applyingRouting=true; stopAll('正在切换处理方式');
  try {
    const result=await json('/v1/settings',next,'PATCH'); routing=result.routing; showRouting();
    const blocked=(routing.asr==='cloud'&&!routing.allow_audio_upload)||(routing.tts==='cloud'&&!routing.allow_text_upload);
    notice(blocked?'云端上传权限已关闭，对应请求不会发出；正在执行的同类云端请求已取消。':(routing.asr==='cloud'||routing.tts==='cloud') && health?.cloud?.state!=='configured' ? '选择已保存。云端密钥尚未配置，请运行“配置云端语音.cmd”，或切回本地继续使用。':'选择已应用，下一轮按新的方式处理。',true);
  } catch(error) { notice(error.message); showRouting(); }
  finally { applyingRouting=false; controls(); await refreshHealth(); }
}
async function api(path, options = {}) {
  const response = await fetch(path, {...options, headers: {'X-Voice-Session': session || '', ...options.headers}});
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    if (response.status === 401) { session = null; sessionStorage.removeItem('voice-session'); $('takeoverBar').hidden = false; controls(); }
    const error = new Error(payload.error?.message || `请求失败（${response.status}）`); error.code = payload.error?.code; throw error;
  }
  return response;
}
async function json(path, body = {}, method = 'POST') { return (await api(path, {method, headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)})).json(); }
async function connect(replace = false) {
  if (session && !replace) {
    try { turn = (await (await api('/v1/session')).json()).turn_id; $('takeoverBar').hidden = true; await refreshRouting(); return; } catch { session = null; }
  }
  try {
    const result = await json('/v1/sessions', {replace}); session = result.session_id; turn = result.turn_id;
    sessionStorage.setItem('voice-session', session); $('takeoverBar').hidden = true; notice();
    await refreshRouting();
  } catch (error) { if (error.code === 'SESSION_BUSY') $('takeoverBar').hidden = false; else notice(error.message); }
  controls();
}
async function refreshHealth() {
  try {
    health = await (await api('/v1/health')).json();
    const labels = {ready: '就绪', loading: '加载中', error: '不可用'};
    const a = health.engines.asr, t = health.engines.tts;
    const selectedLocalReady = (routing.asr==='cloud' || a.state==='ready') && (routing.tts==='cloud' || t.state==='ready');
    const cloudSelected=routing.asr==='cloud'||routing.tts==='cloud';
    $('serviceState').textContent = cloudSelected ? (health.cloud.state==='configured' ? '云端已配置 · 调用后验证':'云端尚未配置') : selectedLocalReady ? '本地语音已就绪' : '本地模型正在加载或不可用';
    const permissionReady=(routing.asr==='local'||routing.allow_audio_upload)&&(routing.tts==='local'||routing.allow_text_upload);
    const selectedReady=selectedLocalReady && (!cloudSelected || health.cloud.state==='configured') && permissionReady;
    if(!permissionReady) $('serviceState').textContent='云端上传权限已关闭';
    $('serviceDot').className = `status-dot ${selectedReady ? 'ready' : 'error'}`;
    $('asrBadge').textContent = routing.asr==='cloud'?'Qwen ASR · 云端':`SenseVoice · ${labels[a.state]}`; $('ttsBadge').textContent = routing.tts==='cloud'?'Qwen TTS · 云端':`Kokoro · ${labels[t.state]}`;
    $('engineSummary').textContent = `识别：${routing.asr==='cloud'?'百炼北京':labels[a.state]} / 朗读：${routing.tts==='cloud'?'百炼北京':labels[t.state]}`;
    $('cloudStatus').textContent=`北京地域 · ${health.cloud.message} · 本会话 ${health.cloud.session_requests}/${health.cloud.session_request_limit} 次`;
    $('technicalStatus').textContent = `服务 ${health.version} · 等待队列 ${health.queue_depth} · 本进程云端请求 ${health.cloud.process_requests} 次 · 无自动重试/回退`;
    if (a.message || t.message) $('technicalStatus').textContent += ` · ${a.message || t.message}`;
  } catch {
    health = null; $('serviceState').textContent = '服务已断开'; $('serviceDot').className = 'status-dot error';
    $('engineSummary').textContent = '请运行项目中的启动语音模块.cmd';
  }
  controls();
}
function emptyWave() {
  painter.clearRect(0, 0, canvas.width, canvas.height);
  painter.strokeStyle = '#d8e1f4'; painter.lineWidth = 1; painter.beginPath(); painter.moveTo(0, 48); painter.lineTo(canvas.width, 48); painter.stroke();
}
function drawWave(recorder) {
  if (recording !== recorder) return;
  const values = new Uint8Array(recorder.analyser.fftSize); recorder.analyser.getByteTimeDomainData(values);
  painter.clearRect(0, 0, canvas.width, canvas.height); painter.strokeStyle = '#c83f52'; painter.lineWidth = 2; painter.beginPath();
  for (let i = 0; i < values.length; i++) { const x = i / (values.length - 1) * canvas.width, y = values[i] / 255 * canvas.height; i ? painter.lineTo(x, y) : painter.moveTo(x, y); }
  painter.stroke(); frames = requestAnimationFrame(() => drawWave(recorder));
}
function setRecordUI(on) {
  $('holdRecord').classList.toggle('recording', on); $('holdRecord').querySelector('span').textContent = on ? '松开结束' : '按住说话';
  $('toggleRecord').textContent = on ? '结束录音并识别' : '点击开始录音'; controls();
}
function stopPlayback() {
  if (playback) { playback.onended = null; try { playback.stop(); } catch {} playback.disconnect(); playback = null; }
  $('playIndicator').classList.remove('active');
}
function stopAll(message = '已停止') {
  generation++; pendingMic = false; microphoneHeld = false;
  if (active) {
    const previous = active; active = null;
    // Explicit cancel, not only AbortController; server may still be computing.
    json(`/v1/requests/${previous.id}/cancel`, {turn_id: previous.turn}).catch(() => {});
    previous.controller.abort();
    failedMetric(previous,'cancelled','CANCELLED');
  }
  stopPlayback();
  if (recording) finishRecording(false);
  $('recordState').textContent = message; $('playState').textContent = message;
  $('synthesize').innerHTML = '<span aria-hidden="true">▶</span> 合成并试听'; controls();
  return generation;
}
async function startRecording() {
  const token = stopAll('准备录音'); pendingMic = true; notice();
  if (!navigator.mediaDevices?.getUserMedia || !window.AudioWorkletNode) { pendingMic = false; notice('当前浏览器不支持本地录音，请使用近期版本 Chrome / Edge 或上传 WAV。'); return; }
  $('recordState').textContent = '等待麦克风权限';
  let stream, context;
  try {
    stream = await navigator.mediaDevices.getUserMedia({audio: {channelCount: 1, echoCancellation: true, noiseSuppression: true, autoGainControl: false}});
    if (token !== generation || !pendingMic) { stream.getTracks().forEach(t => t.stop()); return; }
    context = new AudioContext(); await context.audioWorklet.addModule('/static/recorder-worklet.js');
    if (token !== generation || !pendingMic) { stream.getTracks().forEach(t => t.stop()); await context.close(); return; }
    const source = context.createMediaStreamSource(stream), worklet = new AudioWorkletNode(context, 'pcm-recorder');
    const analyser = context.createAnalyser(); analyser.fftSize = 1024;
    const silent = context.createGain(); silent.gain.value = 0;
    const rec = {stream, context, source, worklet, analyser, silent, chunks: [], count: 0, started: performance.now(), token};
    worklet.port.onmessage = ({data}) => {
      if (data.samples) { rec.chunks.push(data.samples); rec.count += data.samples.length; }
      if (data.flushed) rec.flushed?.();
    };
    source.connect(analyser); source.connect(worklet); worklet.connect(silent); silent.connect(context.destination);
    await context.resume();
    if (token !== generation || !pendingMic) { stream.getTracks().forEach(t => t.stop()); await context.close(); return; }
    recording = rec; pendingMic = false; setRecordUI(true); $('recordState').textContent = '正在录音'; $('recordTime').textContent = '00:00';
    rec.timer = setInterval(() => {
      const elapsed = Math.min(30, Math.floor((performance.now() - rec.started) / 1000)); $('recordTime').textContent = `00:${String(elapsed).padStart(2, '0')}`;
      if (elapsed >= 30) finishRecording(true);
    }, 100);
    stream.getAudioTracks().forEach(track => { track.onended = () => { if (recording === rec) { notice('麦克风已断开，录音已停止。'); finishRecording(false); } }; });
    drawWave(rec);
  } catch (error) {
    stream?.getTracks().forEach(t => t.stop()); if (context && context.state !== 'closed') await context.close();
    if (token === generation) { pendingMic = false; $('recordState').textContent = '录音未开始'; notice(error.name === 'NotAllowedError' ? '麦克风权限未允许。请在浏览器中允许麦克风，或上传 WAV。' : `麦克风不可用：${error.message}`); }
    controls();
  }
}
async function finishRecording(submit) {
  if (pendingMic && !recording) { stopAll('录音已取消'); return; }
  const rec = recording; if (!rec) return; recording = null;
  clearInterval(rec.timer); cancelAnimationFrame(frames); emptyWave(); setRecordUI(false);
  try {
    await Promise.race([new Promise(resolve => { rec.flushed = resolve; rec.worklet.port.postMessage('flush'); }), new Promise(resolve => setTimeout(resolve, 200))]);
  } finally {
    rec.stream.getTracks().forEach(t => t.stop()); rec.source.disconnect(); rec.worklet.disconnect(); rec.silent.disconnect(); await rec.context.close();
  }
  if (!submit || rec.token !== generation) return;
  try {
    const count = Math.min(rec.count, rec.context.sampleRate * 30), samples = new Float32Array(count); let offset = 0;
    for (const chunk of rec.chunks) { const amount = Math.min(chunk.length, count - offset); if (amount <= 0) break; samples.set(chunk.subarray(0, amount), offset); offset += amount; }
    if (count < rec.context.sampleRate * 0.1) throw new Error('录音太短，请至少说一句话。');
    $('recordState').textContent = '准备识别';
    const wav = await toWav(samples, rec.context.sampleRate);
    if (rec.token === generation) await transcribe(wav, rec.token);
  } catch (error) { if (rec.token === generation) { notice(error.message); $('recordState').textContent = '录音未提交'; } }
}
async function toWav(samples, rate) {
  let converted = samples;
  if (rate !== 16000) {
    const renderer = new OfflineAudioContext(1, Math.ceil(samples.length * 16000 / rate), 16000);
    const buffer = renderer.createBuffer(1, samples.length, rate); buffer.copyToChannel(samples, 0);
    const source = renderer.createBufferSource(); source.buffer = buffer; source.connect(renderer.destination); source.start();
    converted = (await renderer.startRendering()).getChannelData(0);
  }
  const view = new DataView(new ArrayBuffer(44 + converted.length * 2));
  const text = (offset, value) => [...value].forEach((c, i) => view.setUint8(offset + i, c.charCodeAt(0)));
  text(0, 'RIFF'); view.setUint32(4, 36 + converted.length * 2, true); text(8, 'WAVE'); text(12, 'fmt '); view.setUint32(16, 16, true);
  view.setUint16(20, 1, true); view.setUint16(22, 1, true); view.setUint32(24, 16000, true); view.setUint32(28, 32000, true); view.setUint16(32, 2, true); view.setUint16(34, 16, true);
  text(36, 'data'); view.setUint32(40, converted.length * 2, true);
  converted.forEach((value, i) => view.setInt16(44 + i * 2, Math.max(-1, Math.min(1, value)) * 32767, true));
  return new Blob([view.buffer], {type: 'audio/wav'});
}
async function beginRequest(kind, token) {
  if (!session) throw new Error('会话未连接，请刷新页面或接管会话。');
  const next = await json(`/v1/sessions/${session}/turns`);
  if (token !== generation) return null;
  turn = next.turn_id;
  active = {id: crypto.randomUUID(), turn, kind, token, route:`${routing.asr==='local'?'L':'C'}${routing.tts==='local'?'L':'C'}`, mode:routing[kind], controller: new AbortController(), started: performance.now()}; controls(); return active;
}
function failedMetric(req,status,code) {
  if(!req || req.recorded) return;
  req.recorded=true;
  observations.push({timestamp:new Date().toISOString(),request_id:req.id,kind:req.kind,route:req.route,mode:req.mode,status,error:code||'REQUEST_FAILED',metrics:{client_response_ms:Math.round(performance.now()-req.started)}});
  if(observations.length>100) observations.shift();
  $('requestInfo').textContent=JSON.stringify(observations.at(-1),null,2); controls();
}
function showMetrics(data, extra = {}) {
  const entry = {timestamp: new Date().toISOString(), request_id: data.request_id, kind: data.kind, provider: data.provider, mode:data.mode, route:active?.route,status: data.status,usage:data.result?.usage||{}, metrics: {...data.metrics, ...extra}};
  if(active) active.recorded=true;
  observations.push(entry); if (observations.length > 100) observations.shift();
  $('metricQueue').textContent = seconds(data.metrics.queue_ms || 0);
  const elapsed=data.metrics.inference_ms??data.metrics.provider_elapsed_ms;
  const metricName=data.mode==='cloud'?'云端处理（含网络）':'本地推理';
  if (data.kind === 'asr') { $('metricAsr').textContent = seconds(elapsed); $('asrTime').textContent = `${seconds(elapsed)} ${metricName}`; }
  else { $('metricTts').textContent = seconds(elapsed); $('ttsTime').textContent = `${seconds(elapsed)} ${metricName}`; }
  if (extra.first_playable_ms !== undefined) $('metricPlayable').textContent = seconds(extra.first_playable_ms);
  $('requestInfo').textContent = JSON.stringify(entry, null, 2); controls();
}
async function transcribe(wav, token) {
  let req;
  try {
    req = await beginRequest('asr', token); if (!req) return;
    $('recordState').textContent = '正在识别'; notice();
    const body = new FormData(); body.append('audio', wav, 'recording.wav'); body.append('request_id', req.id); body.append('turn_id', req.turn);
    const result = await (await api('/v1/asr/transcribe', {method: 'POST', body, signal: req.controller.signal})).json();
    if (token !== generation) return;
    $('transcript').value = result.result.text; $('recordState').textContent = '识别完成';
    $('asrDetail').textContent = result.result.warning || `${result.result.input_seconds.toFixed(1)} 秒录音 · ${result.mode==='cloud'?'云端识别':'本地识别'}`;
    if (result.result.warning) notice(result.result.warning, true);
    showMetrics(result, {client_response_ms: Math.round(performance.now() - req.started)});
  } catch (error) { if (token === generation && error.name !== 'AbortError') { failedMetric(req,'failed',error.code); notice(error.message); $('recordState').textContent = '识别未完成'; } }
  finally { if (active === req) active = null; controls(); }
}
function getPlaybackContext() { if (!playbackContext || playbackContext.state === 'closed') playbackContext = new AudioContext(); return playbackContext; }
async function playBuffer(buffer, token) {
  const context = getPlaybackContext(); await context.resume();
  if (token !== generation) return;
  stopPlayback(); const source = context.createBufferSource(); source.buffer = buffer; source.connect(context.destination); playback = source;
  source.onended = () => { if (playback === source) { playback = null; $('playState').textContent = '播放结束'; $('playIndicator').classList.remove('active'); source.disconnect(); } };
  source.start(); $('playState').textContent = '正在播放'; $('playIndicator').classList.add('active');
}
async function synthesize() {
  const token = stopAll('准备合成'); getPlaybackContext().resume().catch(() => {}); notice(); lastBuffer = null; controls();
  const text = $('speakText').value.trim(); if (!text) { notice('先输入想要朗读的文字。'); return; }
  let req;
  try {
    req = await beginRequest('tts', token); if (!req) return;
    $('synthesize').textContent = '正在合成…'; $('playState').textContent = '正在合成完整音频';
    const response = await api('/v1/tts/synthesize', {method: 'POST', headers: {'Content-Type': 'application/json'}, signal: req.controller.signal,
      body: JSON.stringify({request_id: req.id, turn_id: req.turn, text, speaker_id: Number($('speaker').value), speed: Number($('speed').value), sample_rate: 24000})});
    const buffer = await getPlaybackContext().decodeAudioData(await response.arrayBuffer()); if (token !== generation) return;
    const firstPlayable = Math.round(performance.now() - req.started);
    lastBuffer = buffer;
    const result = await (await api(`/v1/requests/${req.id}`)).json(); if (token !== generation) return;
    showMetrics(result, {first_playable_ms: firstPlayable, output_seconds: Number(buffer.duration.toFixed(3))});
    await playBuffer(buffer, token);
  } catch (error) { if (token === generation && error.name !== 'AbortError') { failedMetric(req,'failed',error.code); notice(error.message); $('playState').textContent = lastBuffer ? '音频已生成，请点击重新播放' : '合成未完成'; } }
  finally { if (active === req) active = null; if (token === generation) $('synthesize').innerHTML = '<span aria-hidden="true">▶</span> 合成并试听'; controls(); }
}
$('holdRecord').addEventListener('pointerdown', event => { if (event.button !== 0) return; event.preventDefault(); $('holdRecord').setPointerCapture(event.pointerId); startRecording(); microphoneHeld = true; });
$('holdRecord').addEventListener('pointerup', () => { if (microphoneHeld) { microphoneHeld = false; finishRecording(true); } });
$('holdRecord').addEventListener('pointercancel', () => stopAll('录音已取消'));
$('holdRecord').addEventListener('keydown', event => { if ([' ', 'Enter'].includes(event.key) && !event.repeat) { event.preventDefault(); startRecording(); microphoneHeld = true; } });
$('holdRecord').addEventListener('keyup', event => { if ([' ', 'Enter'].includes(event.key)) { event.preventDefault(); microphoneHeld = false; finishRecording(true); } });
$('toggleRecord').addEventListener('click', () => recording || pendingMic ? finishRecording(true) : startRecording());
$('stop').addEventListener('click', () => stopAll());
document.addEventListener('keydown', event => { if (event.key === 'Escape') stopAll(); });
window.addEventListener('blur', () => { if (recording || pendingMic) stopAll('窗口失焦，录音已停止'); });
document.addEventListener('visibilitychange', () => { if (document.hidden && (recording || pendingMic)) stopAll('录音已停止'); });
$('upload').addEventListener('change', async () => {
  const file = $('upload').files[0]; $('upload').value = ''; if (!file) return;
  const token = stopAll('准备识别');
  if (file.size > 2097152) { notice('WAV 文件不能超过 2MiB。'); return; }
  await transcribe(file, token);
});
$('synthesize').addEventListener('click', synthesize);
$('replay').addEventListener('click', () => { const buffer = lastBuffer; if (buffer) { const token = stopAll(); playBuffer(buffer, token).catch(error => notice(error.message)); } });
$('transcript').addEventListener('input', controls);
$('copyText').addEventListener('click', async () => { try { await navigator.clipboard.writeText($('transcript').value); notice('识别文字已复制。', true); } catch { notice('无法自动复制，请选中文字复制。'); } });
$('useText').addEventListener('click', () => { $('speakText').value = $('transcript').value.slice(0, 300); updateCount(); $('speakText').focus(); });
function updateCount() { $('charCount').textContent = $('speakText').value.length; }
$('speakText').addEventListener('input', updateCount);
let sampleIndex = 0;
const samples = ['当前记录需要人工复核，请先查看计算依据，再决定是否确认结果。', '本次为语音模块测试，所有金额仅用于演示，不代表正式造价结果。', '请只解释当前行存在的问题，不要修改单价，也不要确认审核结果。'];
$('sampleText').addEventListener('click', () => { $('speakText').value = samples[sampleIndex++ % samples.length]; updateCount(); });
$('takeover').addEventListener('click', () => connect(true));
$('applyRouting').addEventListener('click',applyRouting);
$('exportMetrics').addEventListener('click', () => {
  const url = URL.createObjectURL(new Blob([JSON.stringify({version: '0.3.0', note: 'Per-request metrics including failures/cancellations; cloud timings include network; usage is not a price estimate; no transcript/audio.', observations}, null, 2)], {type: 'application/json'}));
  const anchor = document.createElement('a'); anchor.href = url; anchor.download = 'voice-metrics.json'; anchor.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
});
window.addEventListener('pagehide', () => { stopAll(); if (session) fetch(`/v1/sessions/${session}`, {method: 'DELETE', headers: {'X-Voice-Session': session}, keepalive: true}).catch(() => {}); });
emptyWave(); updateCount(); await connect(); await refreshHealth();
try {
  capabilities = await (await api('/v1/capabilities')).json();
  $('speaker').replaceChildren(...capabilities.tts.speakers.map(s => { const option = document.createElement('option'); option.value = s.id; option.textContent = s.label; return option; }));
} catch (error) { notice(error.message); }
setInterval(refreshHealth, 2000);
