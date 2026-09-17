# Grok study geometry provenance

- Source repository: `https://github.com/blessonism/grok-icon-study`
- Locked source commit: `647e9bd7c60290c42a738fad586589b3f36a4680`
- Copied source file: `replica/geometry-data.js`
- Local copy: `assets/source-grok-study/geometry-data.js`
- Imported on: `2026-09-16`
- Intended scope: private, non-commercial, local study and avatar prototype use

The JavaScript file is retained as a source-layer reference and is not loaded
by the firmware. The deterministic converter reads only the declared geometry
objects and emits fixed C++ arrays into the renderer asset layer. It rejects
unsupported path commands, malformed paths, missing geometry, and unexpected
source counts so that a changed source cannot silently alter the firmware.

The source layer is kept separate from the generic animation engine. Any later
redistribution or broader use must be reviewed against the upstream repository
and applicable rights before release.
