/* Browser-side capture and WAV playback primitives.
 * They have no Gork, BLE, HTTP, DOM or provider dependency, so another local
 * client can use them with the same capture/play/stop lifecycle. */
import {toPCM16} from './pcm.js';

export class WavPlayer {
  constructor(createContext = () => new AudioContext()) { this.createContext = createContext; this.context = null; this.source = null; }
  get playing() { return Boolean(this.source); }
  async play(bytes, onended = () => {}) {
    this.stop();
    const context = this.createContext(); this.context = context;
    await context.resume();
    const buffer = await context.decodeAudioData(bytes);
    if (this.context !== context) return false;
    const source = context.createBufferSource(); this.source = source; source.buffer = buffer; source.connect(context.destination);
    source.onended = () => { if (this.source !== source) return; this.source = null; this.context = null; context.close().catch(() => {}); onended(); };
    source.start(); return true;
  }
  stop() {
    const source = this.source; this.source = null;
    if (source) { source.onended = null; try { source.stop(); } catch {} source.disconnect(); }
    const context = this.context; this.context = null;
    if (context && context.state !== 'closed') context.close().catch(() => {});
  }
}

export class Recorder {
  constructor({createContext = options => new AudioContext(options), getUserMedia = constraints => navigator.mediaDevices.getUserMedia(constraints), AudioWorkletNodeClass = AudioWorkletNode} = {}) {
    this.createContext = createContext; this.getUserMedia = getUserMedia; this.AudioWorkletNodeClass = AudioWorkletNodeClass;
    this.context = null; this.stream = null; this.source = null; this.capture = null; this.chunks = []; this.rate = 16000;
  }
  async start({maxSeconds = 30, onFrames = () => {}} = {}) {
    this.stop();
    const context = this.createContext({sampleRate: 16000}); this.context = context; await context.resume();
    const stream = await this.getUserMedia({audio:{channelCount:1,echoCancellation:true,noiseSuppression:true},video:false});
    if (this.context !== context) { stream.getTracks().forEach(track => track.stop()); return false; }
    this.stream = stream; this.rate = context.sampleRate; await context.audioWorklet.addModule('/static/capture.js');
    this.source = context.createMediaStreamSource(stream); this.capture = new this.AudioWorkletNodeClass(context, 'capture');
    let frames = 0; this.capture.port.onmessage = event => { if (frames < this.rate * maxSeconds) { this.chunks.push(event.data); frames += event.data.length; onFrames(frames, this.rate); } };
    this.source.connect(this.capture); this.capture.connect(context.destination); return true;
  }
  finish() { const wav = toPCM16(this.chunks, this.rate); this.stop(); return wav; }
  stop() {
    this.stream?.getTracks().forEach(track => track.stop()); this.stream = null;
    if (this.capture) { this.capture.port.onmessage = null; this.capture.disconnect(); this.capture = null; }
    this.source?.disconnect(); this.source = null;
    const context = this.context; this.context = null; if (context && context.state !== 'closed') context.close().catch(() => {});
    this.chunks = [];
  }
}
