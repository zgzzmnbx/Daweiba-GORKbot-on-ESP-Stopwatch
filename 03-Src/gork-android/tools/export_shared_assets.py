"""Copy the reviewed shared avatar files from the desktop source tree."""
from __future__ import annotations

import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "03-Src" / "stopwatch-voice-companion" / "static"
TARGET = Path(__file__).resolve().parents[1] / "app" / "src" / "main" / "assets" / "shared"
FILES = (
    "avatar-presets.js", "avatar-engine.js", "gork-appearance.js",
    "gork-catalog.js", "gork-avatar.js",
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if not args.check:
        TARGET.mkdir(parents=True, exist_ok=True)
    differences = []
    for name in FILES:
        content = (SOURCE / name).read_bytes()
        target = TARGET / name
        if args.check:
            if not target.is_file() or target.read_bytes() != content:
                differences.append(name)
        else:
            if not target.is_file() or target.read_bytes() != content:
                target.write_bytes(content)
    if differences:
        print("Shared avatar assets differ: " + ", ".join(differences))
        return 1
    print("Shared avatar assets checked" if args.check else "Shared avatar assets exported")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
