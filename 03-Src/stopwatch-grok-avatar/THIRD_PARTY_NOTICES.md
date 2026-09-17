# Third-party notices

## Grok Icon Study geometry reference

- Project: [blessonism/grok-icon-study](https://github.com/blessonism/grok-icon-study)
- Locked source commit: `647e9bd7c60290c42a738fad586589b3f36a4680`
- Imported file: `replica/geometry-data.js`, copied to `assets/source-grok-study/geometry-data.js`
- Use: private, non-commercial, local visual study and v0.2.0 avatar prototype
- Relationship: source geometry and palette metadata only; the deterministic converter emits fixed C++ data, while the generic animation engine remains independent.
- License note: no license file was present in the checked-out reference at the locked commit. This v0.2.0 branch does not claim public redistribution rights and is not a public release.

See `assets/source-grok-study/SOURCE.md` for the conversion boundary and
source hash.

## Bible Strong Avatar Lab

- Project: [smontlouis/bible-strong-avatar-lab](https://github.com/smontlouis/bible-strong-avatar-lab)
- Locked source commit: `79fe9ba06e4874b11394b8e8a3f2c493c9d197ba`
- License: GNU Affero General Public License v3.0
- Imported data: the user's Studio export is preserved verbatim at `assets/source-grok-bot/avatar-studio-project.json`; the v0.2.1 firmware catalog is generated from its Grok bot character, 27 expression presets and 23 sequences.
- Relationship: data and visual reference for the Grok bot renderer, with a separate embedded C++ implementation of the StopWatch playback and hardware control.

This repository does not bundle the upstream TypeScript/React or web runtime. It **does** bundle the user-exported avatar data and generated C++ tables; preserve this notice and the AGPL license when redistributing them.

## M5Stack StopWatch User Demo

- Project: [m5stack/M5StopWatch-UserDemo](https://github.com/m5stack/M5StopWatch-UserDemo)
- License: MIT
- Use: official hardware configuration, pin/address reference and BMI270 screen-axis orientation.
- Copyright: M5Stack Technology CO LTD.

## M5Stack libraries

The firmware downloads these libraries at their pinned commits through PlatformIO:

| Library | Commit | License |
| --- | --- | --- |
| [M5Unified](https://github.com/m5stack/M5Unified) | `774d920cd6851a5231748b56ece1b073645f313f` | MIT, Copyright (c) 2021 M5Stack |
| [M5GFX](https://github.com/m5stack/M5GFX) | `93b480bb349749202c8a2a953065c8ae95f58320` | MIT, Copyright (c) 2021 M5Stack |
| [M5PM1](https://github.com/m5stack/M5PM1) | `be9a5456c007c333e7ac963f33bfde1ffa5d82ee` | MIT, Copyright (c) 2025 M5Stack Technology CO LTD |
| [M5IOE1](https://github.com/m5stack/M5IOE1) | `846eec7d05e25c09013be2acdb8804487f48a62e` | MIT, Copyright (c) 2026 M5Stack Technology CO LTD |

The complete license text for each dependency is included in its downloaded package. Their MIT copyright and permission notices must be preserved when redistributing substantial portions or a bundle that includes those libraries.
