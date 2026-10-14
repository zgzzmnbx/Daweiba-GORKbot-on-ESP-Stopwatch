// Polls may repeat or arrive late. Turn IDs preserve repeated questions as distinct turns.
export function createWatchChat(write) {
  const revisions = new Map(), seen = new Map();
  function consume(snapshot) {
    if (!snapshot?.history_id || !Array.isArray(snapshot.turns)) return;
    const namespace = snapshot.history_id, revision = snapshot.history_revision;
    if (!Number.isInteger(revision) || revision < (revisions.get(namespace) ?? -1)) return;
    revisions.set(namespace, revision);
    for (const turn of snapshot.turns) {
      if (typeof turn.id !== 'string' || !turn.id) continue;
      for (const [role, field] of [['user','recognized'],['assistant','answer']]) {
        const text = turn[field];
        if (typeof text !== 'string' || !text.trim()) continue;
        const id = `watch:${namespace}:${turn.id}:${role}`;
        let timing = role === 'assistant' ? Object.entries(turn.timings || {})
          .filter(([,value])=>Number.isFinite(value)).map(([name,value])=>`${{prepare:'录音准备',download:'录音到电脑',asr:'识别',answer:'回答',tts:'合成',playback:'传输与播放合计',encode:'编码',send:'音频发送',device_play:'设备播放',stop_to_play:'停录到播放回执'}[name] || name} ${value.toFixed(2)}秒`).join(' · ') : '';
        const voice=turn.voice;
        if(role==='assistant'&&/^[A-Za-z0-9_-]{1,40}$/.test(voice?.rendered||''))
          timing=[`音色 ${voice.rendered}`,timing].filter(Boolean).join(' · ');
        const signature = JSON.stringify([text,timing]);
        if (seen.get(id) === signature) continue;
        seen.set(id,signature);write(role,text,{id,source:'Watch',timing});
      }
    }
  }
  function clear(snapshot={}) {
    seen.clear();
    if (snapshot.history_id && Number.isInteger(snapshot.history_revision))
      revisions.set(snapshot.history_id,snapshot.history_revision);
  }
  return {consume,clear};
}
