# KK — M5Stack StopWatch Avatar

[English](README.md) | [简体中文](README.zh-CN.md)

[![Build firmware](https://github.com/Trentct/m5stack-stopwatch-avatar/actions/workflows/build.yml/badge.svg)](https://github.com/Trentct/m5stack-stopwatch-avatar/actions/workflows/build.yml)
[![License: AGPL v3](https://img.shields.io/badge/License-AGPL_v3-blue.svg)](LICENSE)

Meet **KK** — a tiny expressive face living inside the M5Stack StopWatch.

KK is a procedural avatar built for the M5Stack StopWatch's circular AMOLED display. Its eyes, eyelids, brows, keyframes and transitions are drawn in real time with C++, without image-frame animation. The pure-black visual system is optimized for the 466 × 466 circular screen, partial updates and direct interaction.

> Community project. Not affiliated with or endorsed by M5Stack.

## v0.9.0-dev Opus BLE candidate (source/build only)

The audio endpoint accepts length-prefixed Opus packets after an opt-in HELLO capability exchange, decodes to mono PCM in PSRAM, then uses the same avatar-page speaker path. Legacy clients still receive the four-byte PCM capabilities. The encrypted GATT, bounded packet ACKs, cancellation and 10-second playback limit remain. The v0.9.0 image was written only to app0 and independently verified. On one 5.592 s sample, Opus transfer took 3.66 s versus 32.22 s for PCM on the same device. The user confirmed a complete, audible Opus sentence on the avatar page; detailed timbre comparison is still open.

## v0.8.8-dev avatar-page audio

The BLE audio receiver also stays active on the normal avatar page, without drawing the diagnostic audio UI over the avatar. Playback may coexist with avatar animation and text bubbles. Recording remains restricted to Settings → Audio test. Built-in sound playback and dynamic BLE audio are mutually excluded; opening Settings, losing authorization, or cancelling audio stops the active transfer. On 2026-09-24, the v0.8.8 image was written only to app0 and independently verified. A complete short sentence played twice on the avatar page; the user confirmed clear, complete audible speech on the second run. Transfer took about 17.5 seconds for 89.6 KB of PCM; remaining hardware checks are recorded under `04-output/v0.12.9/`.

## v0.8.7-dev BLE bonded-peer reconnect candidate (source/build only)

On an existing bond, a Windows central can reconnect with a resolvable private
address that differs from the stored identity. The BLE server now waits for
encryption/authentication before checking the bound identity. GATT writes still
require authorization; a new bond still requires the local Pair window. The
v0.8.7 image was subsequently flashed and its GATT reconnect path checked on
hardware; v0.8.8 remains a source/build candidate.

## v0.8.6-dev built-in codec loudness boost (flashed, loudness accepted)

The v0.8.5 PCM peak is already 30,000/32,767, so another direct 3x PCM
multiply would clip. For the six short built-in sounds only, v0.8.6 changes
ES8311 REG32 from `0xBF` (0 dB) to `0xD2` (+9.5 dB, nominal 2.99x voltage
gain). Streamed BLE PCM and recorded-audio playback remain at 0 dB.
The Settings landing page also displays `v0.8.6-dev` as the firmware version.

All 75 Python, 5 browser and 5 Electron tests pass. PlatformIO builds at RAM
63,928 bytes (19.5%) and Flash 1,625,497 bytes (24.8%). The 1,625,856-byte
application was flashed app-only at 0x10000 and an independent verify_flash
passed. Because the source tones are already near full scale, high-volume
output may clip or saturate; physical testing must begin at 20–30% and
increase gradually.

The user subsequently confirmed on the physical device that the sound now has
a normal usable loudness. This closes the maximum-loudness issue, but does not
yet cover per-sound distortion/noise, thermal or long-duration testing.

## v0.8.5-dev 3x built-in sound amplitude (flashed; still too quiet)

The six deterministic built-in PCM16 sounds previously peaked at 10,000,
leaving 3.2767x headroom below the signed 16-bit limit. Their generator now
uses a 30,000 peak: exactly 3x digital amplitude, approximately +9.54 dB,
without PCM clipping. The ES8311 remains at 0 dB, so dynamic speech, BLE PCM
and recorded-audio playback are not globally boosted.

All 73 Python, 5 browser and 5 Electron tests pass. PlatformIO builds at RAM
63,928 bytes (19.5%) and Flash 1,625,089 bytes (24.8%). The 1,625,456-byte
application was flashed app-only at 0x10000 and an independent verify_flash
passed. Actual loudness, distortion, noise and thermal behavior require a
staged physical listening test beginning at 30–40% volume.

## v0.8.4-dev official ES8311 setup fix (flashed, audible output confirmed)

The source embeds six deterministic 16 kHz PCM16 mono CC0 tones and adds a
separate encrypted sound-control GATT service. Short 9-byte commands provide
capabilities, catalog version, play, stop, 0–100 volume and status with request
IDs, directed notifications and an eight-entry terminal dedupe cache.
`Settings → Sound` exposes volume, mute, explicit preview and stop; NVS writes
are delayed. Static sounds, microphone and dynamic PCM remain half-duplex and
mutually exclusive. B stops active sound before expression browsing.

The v0.8.3 local test still displayed `playing` without audible output after
both M5IOE1 G10 and ESP32 GPIO14 were enabled. The official factory project
uses esp_codec_dev 1.5.4 to configure 44.1 kHz, 16-bit Philips I2S, the DAC
reference, mute state and output volume. The pinned M5Unified callback writes
only a subset of those ES8311 registers. v0.8.4 applies the complete official
sequence, verifies the critical registers, then enables both PA gates.

PlatformIO builds successfully at RAM 63,928 bytes (19.5%) and Flash 1,625,873
bytes (24.8%). The v0.8.4 application was flashed app-only at 0x10000 and an
independent verify_flash passed. The local Sound/Test is now audibly playing,
confirming that the incomplete codec setup caused the previous silent output.
The reported 100% volume is still low, so gain and full sound-control acceptance
remain pending.

## v0.7.2-P0 BLE audio probe (flashed, runtime acceptance pending)

Update 2026-09-21: authorized app-only flash at 0x10000 and independent
verify_flash succeeded; hardware reset sent. Capture/playback retest pending.
The following not-flashed statement records the earlier development snapshot.

Fixes stale-loop-clock capture timeout underflow; adds distinct driver/queue/
timeout errors E9–E13 and preserves failures across cleanup/disconnect.
The device still runs v0.7.0-P0 and has reported code 5 on capture.
Actual microphone/speaker acceptance remains pending after an authorized update.

An opt-in `Settings → Audio test` page exercises the official StopWatch
microphone/speaker using half-duplex PCM16. The PC bench arms one capture;
hold A to record, release to finish, B to stop. Audio never starts from the
avatar page. The separate encrypted audio GATT service has bounded PSRAM,
connection/session/transfer isolation, physical cancellation, and a heartbeat
lease. `../../tools/stopwatch_audio.py` supports tone, WAV playback, explicit
WAV recording, and BLE round-trip echo. This is a credit-one transport probe,
not a real-time stream. The PC voice workbench has evolved into the v0.8.0-dev
Gork console while retaining this diagnostic protocol. Hardware sound quality, throughput, security,
and product regression acceptance are pending. The v0.7.0-P0 application was
flashed at 0x10000 on 2026-09-21 with independent readback verification; normal
boot and on-device audio still require observation.

## Highlights

- 12 procedural expressions: `idle`, `listening`, `thinking`, `happy`, `excited`, `curious`, `confused`, `angry`, `surprised`, `sad`, `sleepy` and `dizzy`;
- 60 fps target rendering with dynamic dirty rectangles to reduce AMOLED transfer work;
- tap, double tap, long press, continuous touch tracking, and horizontal/vertical swipes;
- accelerometer and gyroscope fusion for tilt tracking, with the eyes leading and the head following;
- four strong alternating horizontal shakes trigger a looping spiral-eyed dizzy reaction;
- A/B buttons browse expressions, with vibration feedback;
- hold A+B to enter `Settings`, then open `Bluetooth` or `Hardware Check`;
- semantic serial commands provide a stable input boundary for future voice recognition or external control.

## v0.2.0 Grok renderer

The v0.2.0 branch keeps KK's input, animation timeline, 60 fps scheduler and
dirty-rectangle flow, while replacing the face drawing layer with a fixed-point
Grok geometry renderer. The source study is retained under
`assets/source-grok-study/`; the firmware consumes generated C++ constants, not
JavaScript at runtime.

- one white blob body and black eye cutouts, transformed from a 1000 × 1000 design space;
- 12 expression states mapped to 8 implemented eye groups and 25 retained source groups;
- fixed-point generated geometry with deterministic ear-clipped triangles;
- no image sequence frames or per-frame heap allocation;
- five-second serial metrics include FPS, render time, geometry point count, maximum dirty area and full-screen fallback status.

## v0.2.1 Grok bot renderer (built, device acceptance pending)

The v0.2.1 branch uses the user's exported Bible Strong Avatar Lab Studio project as the data snapshot. `tools/generate_grok_bot_catalog.py` converts its 27 Grok bot expression presets and 23 animations into deterministic C++ tables. The firmware draws a black circular body with individually sized, positioned and rotated white eyes; the website's React/SVG runtime is not embedded. The StopWatch input, power, vibration, IMU and local-refresh implementation remains from the verified KK hardware base.

The 23 animations can be browsed with A/B or addressed by serial name. The hardware-facing `sleepy`/`dizzy` aliases map to the source `drowsy`/`playful` sequences. Source data: `assets/source-grok-bot/`; contact sheet: project-level `04-output/v0.2.1/previews/`.

In v0.2.2, only `idle` persists by default. Every other sequence plays once and returns to `idle`. Serial `loop <name>` and `pingpong <name>` remain explicit continuous-play overrides; `once <name>` returns to `idle` after completion. The app image has been flashed and verified, but runtime return-to-idle acceptance is pending a normal boot.

In v0.2.3, hold A+B for one second to open `Settings` (the former hardware-check screen). Tap `-` or `+` on the Brightness row to change display brightness in steps of 15 between 30 and 255. The value is stored in ESP32 NVS and restored after restart. The hardware diagnostics remain on the same screen. This version is built but not yet flashed or hardware-accepted.

In v0.2.4, the `Settings` home page also shows an estimated battery percentage/voltage and a persistent `Debug mode` switch. The hardware diagnostics now live on a `Hardware Check` subpage. Debug mode adds a tiny white animation name at the bottom of the avatar screen; when off, no label is drawn. This combined brightness/battery/debug image was flashed and read back, but has not yet been hardware-accepted.

In v0.2.5, the debug animation name moves to the top of the black avatar body. This app-only update has been flashed and read back; on-device visual acceptance is pending.

## v0.3.0 BLE expression control (paired, core G4 path verified)

v0.3.0 adds an optional `GorkBot-SW` BLE GATT peripheral. BLE is OFF by default;
the user enables it in `Settings → Bluetooth` and opens a local 120-second `Pair`
window. Only the controller that completes encrypted binding may write commands
afterwards. The command characteristic accepts encrypted write-with-response only;
the status characteristic provides encrypted reads and notifications. USB serial,
buttons, touch and IMU remain available.

BLE callbacks perform only bounded ASCII validation and queueing. Expression
semantics, menu-busy rejection, vibration and receipts are handled by the main
loop. The Windows client is `tools/ble-expression-console.py`, launched by
`tools/start-ble-expression-console.cmd` in an isolated Bleak environment. The
Arduino BLE security probe, formal firmware build and mock GATT client tests pass;
The v0.3.0 app image has been flashed to the authorized target at 0x10000 and
passed esptool readback verification. After the local Pair action,
`BleakClient(pair=True)` discovered the service, subscribed to status
notifications, received receipts for all 23 standard expressions, and
reconnected once. Unbound-controller rejection, ten-cycle reconnect,
latency/FPS and long-run stability remain G4 follow-up checks.

## v0.4.0 happy-work derivative (included in v0.5.0 upload)

`happy-work` is a firmware-local 24th callable expression. It references the
unchanged four-keyframe `happy` eye sequence and adds a procedural monochrome
paper, pen, gloved hand, and progressing ink stroke in the lower safe area of
the circular screen. The 23 source sequences and generated catalog remain
untouched. Default playback returns to `idle`; explicit `loop happy-work` and
`pingpong happy-work` continue. USB serial and BLE consoles accept the new
hyphenated name (19 bytes in the longest command). Local tests and PlatformIO
build pass. The v0.5.0 app upload includes this expression; visual quality,
residue-free transitions, and FPS still require physical acceptance.

## v0.5.0 BLE chat bubble (uploaded, readback verified)

The Windows BLE console accepts `:say <text>` and `:clear`. `:say` transfers up
to 24 printable BMP Unicode characters (72 UTF-8 bytes maximum) in sequenced,
acknowledged GATT packets of no more than 20 bytes each. The device validates
and commits the complete text in its main loop. A two-line bubble is rendered
above the avatar with the bundled 16 px Chinese font and clears automatically
after about 10 seconds. This retains the original BLE service, bonding policy,
expression control, and v0.4.0 `happy-work`. Emoji are not supported. The new
firmware builds and client tests pass. The app-only upload and independent
flash readback verification pass; Chinese glyph appearance, clipping, residue,
and frame rate still need physical QA.

The local build and data tests pass. v0.2.1 has been uploaded as an app-only update and verified by flash readback. A user photo shows the black body and white eyes; 23 serial sequence entries respond and the optimized idle renderer reaches 60 FPS. Full animation, input and long-run hardware acceptance remains pending.

## Interaction map

| Input | Result |
| --- | --- |
| Tap | `happy` |
| Double tap | `surprised` |
| Hold and move | Eyes and head continuously follow the touch point |
| Long press | `angry` |
| Swipe left / right | Preview and switch to the adjacent expression |
| Swipe up / down | `surprised` / `sleepy` |
| Slowly tilt the device | Gaze continuously follows the tilt direction |
| Four strong alternating horizontal shakes | Loop `dizzy`, then recover after the device settles |
| A / B | Previous / next expression |
| Hold A+B | Enter / exit `Settings`, then open `Bluetooth` or `Hardware Check` |

`idle`, `listening` and `thinking` are persistent base states. Other reactions return to the previously active base state when their animation finishes instead of always returning to idle.

## Hardware

- [M5Stack StopWatch Dev Kit (C152)](https://docs.m5stack.com/en/core/StopWatch)
- ESP32-S3R8, 16 MB Flash, 8 MB PSRAM
- 1.75-inch 466 × 466 circular AMOLED touch display
- BMI270 six-axis IMU
- CST820B touch controller
- Two programmable buttons and an internal vibration motor

See [Hardware baseline](docs/HARDWARE_BASELINE.md) for interfaces, addresses and the current verification boundary.

## Build

Requirements:

- [PlatformIO Core](https://platformio.org/) 6.1.18
- USB-C data cable
- M5Stack StopWatch

The library commits used by the verified build are pinned in [`platformio.ini`](platformio.ini).

```sh
pio run -e m5stack-stopwatch
```

From the project root, the offline desktop preview can be regenerated with:

```sh
python tools/render_grok_previews.py
```

The resulting 12 state SVGs, three keyframe comparisons and `index.html` are
written to `04-output/v0.2.0/previews/`.

## Upload and monitor

The v0.2.0 image was written to the authorized target on 2026-09-16 after a
read-only port/MAC/chip/Flash and recovery-image preflight. PlatformIO used
`COM5` for this run and wrote the existing `default_16MB.csv` layout at
`0x0000`, `0x8000`, `0xe000` and `0x10000`; all four regions passed post-write
`verify_flash`. `COM5` remains a connection snapshot, not a permanent setting.

The write did not use full-chip erase, eFuse, secure boot or flash encryption.
True display, touch, button, vibration, IMU, serial-performance and long-run
hardware acceptance remains pending; code/build success is not a substitute for
those observations. See the project-level G3/G4 evidence for the exact command
and readback record.

```sh
pio device monitor --baud 115200
```

The monitor accepts expression names such as `happy`, `thinking`, `celebrate` or `playful` (`dizzy` remains an alias). Playback testing also supports:

```text
once <expression>
loop <expression>
pingpong <expression>
```

## Repository map

| Path | Purpose |
| --- | --- |
| `src/avatar_engine.*` | Expression catalogue, timelines, easing, drawing and interaction physics |
| `src/main.cpp` | Device setup, touch/IMU/buttons, vibration, diagnostics and serial commands |
| `docs/HARDWARE_BASELINE.md` | Hardware capabilities and verification boundary |
| `docs/ENGINEERING_NOTES.md` | Rendering experiments, measurements and implementation decisions |
| `docs/ROADMAP.md` | Planned work and intentionally unsupported features |

## Known limitations

- The microphone and offline speech recognition are not connected yet. Serial commands only simulate semantic voice events.
- Audio playback, RTC, deep sleep, wake-up strategy and external expansion ports are not integrated.
- Battery life has not been optimized for long-term always-on use.
- Subjective motion and gesture tuning may vary with how the device is held.
- The v0.2.1 Grok bot catalog has passed deterministic conversion, desktop preview and local compilation checks; touch, IMU, buttons, vibration, display quality and performance still require real-device G4 verification.

## Inspiration and provenance

This project uses the user's Grok bot export from [Bible Strong Avatar Lab](https://github.com/smontlouis/bible-strong-avatar-lab) as v0.2.1 visual and animation data. The embedded C++ runtime is separate from the upstream web application and does not bundle its React/TypeScript engine; the exported avatar JSON **is** bundled under `assets/source-grok-bot/`.

The concise relationship is: **Grok bot data retained and attributed; renderer rebuilt for StopWatch hardware.**

Hardware initialization, pin mapping and IMU screen-axis handling reference M5Stack's official [StopWatch User Demo](https://github.com/m5stack/M5StopWatch-UserDemo). See [Third-party notices](THIRD_PARTY_NOTICES.md) for details.

## Contributing

Issues and pull requests are welcome. Please read [CONTRIBUTING.md](CONTRIBUTING.md) and run `pio run` before submitting a change. Hardware-dependent claims should include real-device evidence when possible.

## License

This project is licensed under the [GNU Affero General Public License v3.0 or later](LICENSE).
