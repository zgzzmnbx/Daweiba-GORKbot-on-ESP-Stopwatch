# Connection speech — Qwen fixed cues

User-authorized on 2026-10-05, generated with the project's existing Beijing
DashScope Qwen3-TTS-Flash endpoint and **Ethan** voice. Only two constant phrases
were submitted: `Wi-Fi 已连接。` and `蓝牙已连接。` No recordings, questions,
credentials, or network settings are stored here or embedded in the firmware.

`wifi.wav` (1.600 s) and `ble.wav` (1.120 s) are the provider output resampled
by the existing voice service to 16 kHz, mono PCM16. `source.json` records their
origin and conversion parameters. `src/connection_voice.h` embeds these samples
with the same bounded speech enhancement used by the PC Watch path: at most
3× gain, peak at most 30000; the device uses Unity codec gain, not BuiltInLoud.
No phonemes or leading/trailing samples are cut.

Regenerate the header from the saved WAVs without a cloud request:

```powershell
& Codex-Temp/voice-runtime/.venv/Scripts/python.exe tools/generate_connection_voice.py
```

`--generate` only requests a missing WAV and requires authorization for those
specific cloud texts. It never retries automatically. Existing WAVs are reused.
The firmware plays from flash and makes no TTS request on a connection event.
These are locally generated speech assets for this project, not upstream human
recordings; no public publication or redistribution was performed this round.
