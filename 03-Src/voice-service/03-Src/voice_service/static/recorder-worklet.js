class PCMRecorder extends AudioWorkletProcessor {
  constructor() {
    super(); this.buffer = new Float32Array(2048); this.offset = 0;
    this.port.onmessage = ({data}) => { if (data === 'flush') { this.flush(); this.port.postMessage({flushed: true}); } };
  }
  flush() { if (this.offset) { const block = this.buffer.slice(0, this.offset); this.port.postMessage({samples: block}, [block.buffer]); this.offset = 0; } }
  process(inputs) {
    const channels = inputs[0];
    if (channels?.length) for (let i = 0; i < channels[0].length; i++) {
      let value = 0; for (const channel of channels) value += channel[i] || 0;
      this.buffer[this.offset++] = value / channels.length;
      if (this.offset === this.buffer.length) this.flush();
    }
    return true;
  }
}
registerProcessor('pcm-recorder', PCMRecorder);
