// Pure functions, shared with the Node regression tests. Never relabel 48 kHz as 16 kHz.
export function toPCM16(chunks, sourceRate) {
  const count = chunks.reduce((sum, x) => sum + x.length, 0);
  const source = new Float32Array(count);
  let cursor = 0;
  for (const chunk of chunks) { source.set(chunk, cursor); cursor += chunk.length; }
  const frames = Math.min(480000, Math.floor(count * 16000 / sourceRate));
  const buffer = new ArrayBuffer(44 + frames * 2), view = new DataView(buffer);
  const ascii = (at, text) => [...text].forEach((x, i) => view.setUint8(at + i, x.charCodeAt(0)));
  ascii(0, 'RIFF'); view.setUint32(4, 36 + frames * 2, true); ascii(8, 'WAVEfmt ');
  view.setUint32(16, 16, true); view.setUint16(20, 1, true); view.setUint16(22, 1, true);
  view.setUint32(24, 16000, true); view.setUint32(28, 32000, true); view.setUint16(32, 2, true);
  view.setUint16(34, 16, true); ascii(36, 'data'); view.setUint32(40, frames * 2, true);
  for (let i = 0; i < frames; i++) {
    const start = Math.floor(i * sourceRate / 16000);
    const end = Math.max(start + 1, Math.floor((i + 1) * sourceRate / 16000));
    let sum = 0;
    for (let j = start; j < end; j++) sum += source[j] || 0;
    const sample = Math.max(-1, Math.min(1, sum / (end - start)));
    view.setInt16(44 + i * 2, Math.round(sample * (sample < 0 ? 32768 : 32767)), true);
  }
  return buffer;
}

export class Epoch {
  constructor() { this.value = 0; this.abort = new AbortController(); }
  next() { this.abort.abort(); this.abort = new AbortController(); return ++this.value; }
  valid(value) { return this.value === value; }
}
