# KK — M5Stack StopWatch Avatar

[English](README.md) | [简体中文](README.zh-CN.md)

[![Build firmware](https://github.com/Trentct/m5stack-stopwatch-avatar/actions/workflows/build.yml/badge.svg)](https://github.com/Trentct/m5stack-stopwatch-avatar/actions/workflows/build.yml)
[![License: AGPL v3](https://img.shields.io/badge/License-AGPL_v3-blue.svg)](LICENSE)

Meet **KK** — a tiny expressive face living inside the M5Stack StopWatch.

KK is a procedural avatar built for the M5Stack StopWatch's circular AMOLED display. Its eyes, eyelids, brows, keyframes and transitions are drawn in real time with C++, without image-frame animation. The pure-black visual system is optimized for the 466 × 466 circular screen, partial updates and direct interaction.

> Community project. Not affiliated with or endorsed by M5Stack.

## v0.7.0-P0 BLE audio probe (built, NOT flashed)

An opt-in `Settings → Audio test` page exercises the official StopWatch
microphone/speaker using half-duplex PCM16. The PC bench arms one capture;
hold A to record, release to finish, B to stop. Audio never starts from the
avatar page. The separate encrypted audio GATT service has bounded PSRAM,
connection/session/transfer isolation, physical cancellation, and a heartbeat
lease. `../../tools/stopwatch_audio.py` supports tone, WAV playback, explicit
WAV recording, and BLE round-trip echo. This is a credit-one transport probe,
not a real-time stream or integrated speech assistant. The PC voice workbench
remains v0.6.0 and uses PC audio. Hardware sound quality, throughput, security,
and product regression acceptance are pending; the device still runs v0.5.0.

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
