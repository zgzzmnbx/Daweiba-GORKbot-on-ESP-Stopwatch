# Upstream provenance

> This file records the exact source baseline for the personal v0.2.0 development branch.

## KK firmware baseline

- Repository: <https://github.com/Trentct/m5stack-stopwatch-avatar>
- Locked commit: `204963257cb4dc2f3d7501eff900897bac55ef82`
- Local branch: `kk-grok-v0.2.0`
- Imported: 2026-09-16
- Role: M5Stack StopWatch initialization, 466 x 466 rendering cadence, dirty-rectangle animation, state machine, touch, IMU, buttons, vibration, diagnostics, and serial commands.
- License: AGPL-3.0-or-later; see `LICENSE`.

## Grok geometry reference

- Repository: <https://github.com/blessonism/grok-icon-study>
- Locked commit: `647e9bd7c60290c42a738fad586589b3f36a4680`
- Imported source file: `replica/geometry-data.js`
- Role: personal, non-commercial visual study input for blob geometry, eyes, palette, and shape metadata; converted data is kept in a separate asset layer.
- The source file is copied under `assets/source-grok-study/` with its own `SOURCE.md`; it is not mixed into the hardware engine baseline.

## Local change boundary

Allowed in this branch:

- Add the deterministic Grok source-data converter, generated C++ constants, desktop preview generator, tests, and documentation.
- Add the Grok renderer as an isolated layer and connect it to the existing `AvatarEngine` state, interaction, timing, and dirty-rectangle flow.
- Preserve the upstream hardware initialization and input/diagnostic behavior unless a build-compatible adapter is required and documented.

Out of scope:

- Flashing, erasing, partition changes, eFuse, secure boot, flash encryption, Wi-Fi, audio/voice, cloud services, public release, and changes to the recovery images.
- Copying `.pio/`, firmware binaries, full Flash backups, credentials, serial logs, or machine-specific absolute paths into the source repository.

## Recovery baseline

The read-only recovery images remain outside this nested repository in the project `04-output/backups/` and the protected Documents backup. Their hashes are recorded only in the project-level evidence and G3 report.

## Reproduce the import baseline

```powershell
git clone https://github.com/Trentct/m5stack-stopwatch-avatar.git 03-Src/stopwatch-grok-avatar
git -C 03-Src/stopwatch-grok-avatar checkout 204963257cb4dc2f3d7501eff900897bac55ef82
git -C 03-Src/stopwatch-grok-avatar switch -c kk-grok-v0.2.0
git -C 03-Src/stopwatch-grok-avatar rev-parse HEAD
```
