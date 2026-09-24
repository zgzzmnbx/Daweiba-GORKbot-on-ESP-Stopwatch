# Gork Robot Console v0.12.5-dev

The console's “始终置顶” switch controls whether the floating avatar stays above other windows. It is on by default for existing users and saved with the avatar's window state. Restart the Electron shell to load the new IPC bridge; the browser-only page cannot change this setting.

The console now has four pages: Dialogue, Character, StopWatch and Settings.
Workbench ownership is separate from the single active voice session, so a
released voice session does not disable local character preview or Watch control.
Manual character requests and short bubbles are delivered through the existing
restricted backend; the desktop avatar returns one-shot expressions to idle.
The voice project's foreground managed entry handles pipe EOF and cleans up
its inference worker; models and credentials stay in that separate project.

Web and desktop use the same Canvas renderer and the Watch's pinned Grok bot
catalog (27 poses, 23 sequences), without the old beige panel/green ring.
Run `python tools/export_desktop_avatar.py --check` from the project root to
check generated copies. Restart from the root launcher to load changed files;
the older packaged v0.8.0 directory is not updated by source changes.

Windows x64 Electron desktop shell for the Gork companion at `http://127.0.0.1:8766`.

From the project root, double-click `start-gork-console.cmd`. The launcher installs the pinned Electron dependency on first use, then starts the GUI without keeping a command window open. Reopening the launcher activates the existing single instance instead of initializing another desktop shell. The shell reuses a verified existing project backend or starts its own instance with the project Python environment; on exit it stops only the instance it owns.

The shell provides one application instance, tray, resizable transparent avatar, shared backend state and a full console window. It reuses a verified external companion or starts the project-owned one with `--no-browser`. The packaged build resolves its companion from `resources/project` and stops only its own child process.

Security defaults: renderer sandbox, context isolation, no Node integration, a small preload IPC allowlist, exact-origin navigation, audio-only media permission for the trusted loopback console, and no credentials in this directory.

Validation:

```powershell
npm test
npm start -- --smoke-test
```

The smoke tests prove both source and packaged Electron processes can start on this Windows machine; the packaged probe also starts and stops its own backend on an isolated port. Tray interaction, actual microphone permission, multiple monitors and long-run behavior still require manual acceptance.
