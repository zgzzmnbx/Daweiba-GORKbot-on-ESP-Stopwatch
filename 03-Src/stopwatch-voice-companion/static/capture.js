class Capture extends AudioWorkletProcessor {
  process(inputs, outputs) {
    const channels = inputs[0];
    if (channels?.length) {
      const mono = new Float32Array(channels[0].length);
      for (const channel of channels) for (let i = 0; i < mono.length; i++) mono[i] += channel[i] / channels.length;
      this.port.postMessage(mono, [mono.buffer]);
    }
    // Output remains silent: the microphone never feeds back into the speaker.
    for (const output of outputs) for (const channel of output) channel.fill(0);
    return true;
  }
}
registerProcessor('capture', Capture);
