"""Check v0.2.0 source, build, and delivery invariants without a device."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "03-Src" / "stopwatch-grok-avatar"
OUTPUT = ROOT / "04-output" / "v0.2.0"
EVIDENCE = OUTPUT / "evidence"
PREVIEWS = OUTPUT / "previews"

EXPECTED_EXPRESSIONS = (
    "Idle",
    "Listening",
    "Thinking",
    "Happy",
    "Excited",
    "Curious",
    "Confused",
    "Angry",
    "Surprised",
    "Sad",
    "Sleepy",
    "Dizzy",
)
EXPECTED_SOURCE_GROUPS = (8, 10, 14, 2, 17, 7, 23, 4)
EXPECTED_DEPENDENCIES = (
    "M5Unified = https://github.com/m5stack/M5Unified.git#774d920cd6851a5231748b56ece1b073645f313f",
    "M5GFX = https://github.com/m5stack/M5GFX.git#93b480bb349749202c8a2a953065c8ae95f58320",
    "M5PM1 = https://github.com/m5stack/M5PM1.git#be9a5456c007c333e7ac963f33bfde1ffa5d82ee",
    "M5IOE1 = https://github.com/m5stack/M5IOE1.git#846eec7d05e25c09013be2acdb8804487f48a62e",
)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def require(condition: bool, message: str, failures: list[str]) -> None:
    if not condition:
        failures.append(message)


def mapping_values(text: str, name: str) -> tuple[int, ...]:
    match = re.search(
        rf"constexpr\s+uint8_t\s+{re.escape(name)}\[\]\s*=\s*\{{(.*?)\}};",
        text,
        re.DOTALL,
    )
    if not match:
        raise ValueError(f"missing {name}")
    body = re.sub(r"//.*", "", match.group(1))
    return tuple(int(value) for value in re.findall(r"\b\d+\b", body))


def tracked_text_files() -> list[Path]:
    result = subprocess.run(
        ["git", "-C", str(SOURCE), "ls-files", "-co", "--exclude-standard"],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    suffixes = {".c", ".cc", ".cpp", ".h", ".hpp", ".ini", ".js", ".json", ".md", ".py"}
    return [
        SOURCE / line
        for line in result.stdout.splitlines()
        if Path(line).suffix.lower() in suffixes
    ]


def main() -> int:
    failures: list[str] = []
    avatar_header = read(SOURCE / "src" / "avatar_engine.h")
    avatar_cpp = read(SOURCE / "src" / "avatar_engine.cpp")
    main_cpp = read(SOURCE / "src" / "main.cpp")
    renderer_header = read(SOURCE / "src" / "grok_renderer.h")
    renderer_cpp = read(SOURCE / "src" / "grok_renderer.cpp")
    platformio = read(SOURCE / "platformio.ini")

    enum_match = re.search(
        r"enum\s+class\s+ExpressionId\s*:\s*uint8_t\s*\{(.*?)\};",
        avatar_header,
        re.DOTALL,
    )
    enum_values = tuple(re.findall(r"\b(Idle|Listening|Thinking|Happy|Excited|Curious|Confused|Angry|Surprised|Sad|Sleepy|Dizzy)\b", enum_match.group(1))) if enum_match else ()
    require(enum_values == EXPECTED_EXPRESSIONS, "T07: ExpressionId catalog is incomplete or reordered", failures)

    try:
        expression_map = mapping_values(renderer_cpp, "kEyeGroupMap")
        source_map = mapping_values(renderer_cpp, "kSourceEyeGroupMap")
    except ValueError as exc:
        failures.append(f"T05: {exc}")
        expression_map = ()
        source_map = ()
    require(len(expression_map) == 12 and set(expression_map) == set(range(8)), "T05: 12 expressions do not cover exactly 8 implemented eye groups", failures)
    require(all(0 <= value < 8 for value in expression_map), "T05: expression map contains an out-of-range implemented group", failures)
    require(source_map == EXPECTED_SOURCE_GROUPS, "T05: source eye group map drifted", failures)
    require("kImplementedEyeGroups = 8" in renderer_header, "T05: eight-group renderer invariant is missing", failures)

    for marker in (
        "M5.Touch.getDetail",
        "M5.Imu.getImuData",
        "M5.BtnA",
        "M5.BtnB",
        "startVibration",
        "Serial.available",
        "Serial.read",
        "Serial.printf",
    ):
        require(marker in main_cpp, f"T07: hardware/serial entry missing: {marker}", failures)
    for marker in (
        "constexpr uint32_t kFrameIntervalUs = 16667",
        "constexpr uint32_t kMetricsReportIntervalMs = 5000",
        "M5.Display.startWrite()",
        "M5.Display.endWrite()",
        "clearDirtyRect",
        "mergeRects(previousGrokBounds_, grokBounds)",
        "grokRenderer_.draw(grokFrame)",
        "geometryPointCount",
        "maximumGrokDirtyArea_",
        "fullScreenFallback",
        "[grok perf]",
        "recordRenderMetrics",
    ):
        require(marker in avatar_cpp, f"T07: renderer invariant missing: {marker}", failures)
    require("delay(1)" in main_cpp and "delay(2)" not in main_cpp, "T07: main loop delay changed beyond the existing 1 ms yield", failures)

    require(not re.search(r"\b(new|malloc|calloc|realloc|free)\s*[(<]", renderer_cpp), "T07: dynamic allocation found in Grok renderer", failures)
    require("std::vector" not in renderer_cpp and "std::vector" not in read(SOURCE / "src" / "grok_geometry.cpp"), "T07: vector allocation found in firmware geometry path", failures)
    render_body = avatar_cpp[avatar_cpp.find("void AvatarEngine::render"):]
    require("if (requiresFullClear_)" in render_body, "T07: full clear is not guarded by the existing invalidation flag", failures)

    required_config = (
        "platform = espressif32 @ 6.12.0",
        "board = esp32s3box",
        "board_build.partitions = default_16MB.csv",
        "board_upload.flash_size = 16MB",
        "board_upload.maximum_size = 16777216",
    ) + EXPECTED_DEPENDENCIES
    for marker in required_config:
        require(marker in platformio, f"T10: platformio.ini drifted: {marker}", failures)

    manifest_path = SOURCE / "assets" / "source-grok-study" / "grok_geometry_manifest.json"
    manifest = json.loads(read(manifest_path))
    require(manifest["counts"] == {"eyeGroups": 25, "palette": 11, "shapes": 18}, "T01/T03: source count manifest drifted", failures)
    require(manifest["source"]["commit"] == "647e9bd7c60290c42a738fad586589b3f36a4680", "T10: Grok source commit drifted", failures)

    preview_files = sorted(PREVIEWS.glob("status-*.svg"))
    require(len(preview_files) == 12, "T06: expected exactly 12 status SVG previews", failures)
    for path in preview_files:
        content = read(path)
        require('width="466"' in content and 'height="466"' in content, f"T06: preview dimensions invalid: {path.name}", failures)
        require("<polygon" in content and "#F7F8F4" in content and "#050608" in content, f"T06: preview geometry/colors invalid: {path.name}", failures)
    require((PREVIEWS / "index.html").is_file(), "T06: preview index missing", failures)
    transition_names = ("transition-idle-happy.svg", "transition-idle-thinking.svg", "transition-idle-dizzy.svg")
    require(all((PREVIEWS / name).is_file() for name in transition_names), "T06: keyframe comparison preview missing", failures)
    for name in transition_names:
        transition_content = read(PREVIEWS / name)
        require('width="1398"' in transition_content and 'height="466"' in transition_content, f"T06: keyframe dimensions invalid: {name}", failures)
        require("#F7F8F4" in transition_content and "#050608" in transition_content, f"T06: keyframe geometry/colors invalid: {name}", failures)
    index_content = read(PREVIEWS / "index.html")
    for label in ("idle → happy", "idle → thinking", "idle → dizzy"):
        require(label in index_content, f"T06: keyframe link missing: {label}", failures)

    forbidden_patterns = (
        r"(?i)BEGIN\s+(?:RSA|OPENSSH|EC)\s+PRIVATE KEY",
        r"(?i)(?:api[_-]?key|access[_-]?token|client[_-]?secret)\s*[:=]",
        r"(?i)(?:C:|D:)[\\/]Users[\\/]",
        r"(?i)(?:C:|D:)[\\/]Codex-Temp[\\/]",
    )
    for path in tracked_text_files():
        content = read(path)
        for pattern in forbidden_patterns:
            require(not re.search(pattern, content), f"T11: sensitive or machine-specific path pattern in {path.relative_to(SOURCE)}", failures)
    require(not any(path.suffix.lower() in {".bin", ".elf", ".map"} for path in tracked_text_files()), "T11: binary build artifact entered source tracking", failures)

    checked_evidence = "\n".join(read(path) for path in EVIDENCE.glob("*.log"))
    require(not re.search(r"(?i)\b(?:write_flash|erase_flash|merge_bin)\b", checked_evidence), "T12: forbidden device-write command found in evidence logs", failures)

    if failures:
        for failure in failures:
            print(f"FAIL: {failure}")
        return 1
    print("v0.2.0 invariants: PASS")
    print("T05 expression map:", ",".join(str(value) for value in expression_map))
    print("T05 source map:", ",".join(str(value) for value in source_map))
    print("T06 status previews:", len(preview_files), "+ index.html + 3 keyframe comparisons")
    print("T07 hardware/dirty-rect/timing/static-allocation checks: PASS")
    print("T10 locked platform/dependencies: PASS")
    print("T11 sensitive-source scan: PASS")
    print("T12 device write commands: NOT RUN")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
