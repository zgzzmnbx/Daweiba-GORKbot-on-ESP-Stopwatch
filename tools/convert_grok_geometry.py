"""Convert the locked Grok study geometry into deterministic C++ assets.

The source file is JavaScript because that is how the reference repository
stores the extracted geometry. This converter deliberately accepts only the
small, known source shape: one JSON object assigned to ``window.GROK_GEO``.
SVG paths are limited to uppercase absolute M/L/C/Z commands and cubic curves
are sampled at a fixed count before ear-clipping into fixed triangles.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence


SOURCE_REPOSITORY = "https://github.com/blessonism/grok-icon-study"
SOURCE_COMMIT = "647e9bd7c60290c42a738fad586589b3f36a4680"
SOURCE_FILE = "replica/geometry-data.js"
CURVE_SAMPLES = 8
GEOMETRY_SCALE = 100
EXPECTED_EYE_GROUPS = 25
EXPECTED_SHAPES = 18
EXPECTED_PALETTE = 11

Number = float
Point = tuple[Number, Number]
IntPoint = tuple[int, int]
Triangle = tuple[int, int, int]


@dataclass(frozen=True)
class PolygonData:
    points: tuple[IntPoint, ...]
    triangles: tuple[Triangle, ...]
    center: IntPoint
    min_x: int
    max_x: int
    min_y: int
    max_y: int


@dataclass(frozen=True)
class GeometryModel:
    source_sha256: str
    view_box: dict[str, Number]
    body: PolygonData
    eyes: tuple[tuple[PolygonData, PolygonData], ...]
    shape_names: tuple[str, ...]
    palette_names: tuple[str, ...]


def _number(value: Any, label: str) -> Number:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be a number")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{label} must be finite")
    return result


def _point(value: Any, label: str) -> Point:
    if not isinstance(value, list) or len(value) != 2:
        raise ValueError(f"{label} must be [x, y]")
    return (_number(value[0], f"{label}.x"), _number(value[1], f"{label}.y"))


def _read_json_assignment(text: str, marker: str) -> tuple[Any, int]:
    try:
        start = text.index(marker) + len(marker)
    except ValueError as exc:
        raise ValueError(f"missing assignment marker: {marker}") from exc
    decoder = json.JSONDecoder()
    try:
        value, consumed = decoder.raw_decode(text[start:].lstrip())
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON after assignment marker: {marker}") from exc
    return value, consumed


def load_source(path: Path) -> tuple[dict[str, Any], str]:
    text = path.read_text(encoding="utf-8")
    root, _ = _read_json_assignment(text, "window.GROK_GEO =")
    if not isinstance(root, dict):
        raise ValueError("window.GROK_GEO must contain an object")
    return root, hashlib.sha256(text.encode("utf-8")).hexdigest()


def validate_root(root: dict[str, Any]) -> None:
    required = {"Re", "viewBox", "blobPath", "starPath", "palette", "eyes", "shapes"}
    missing = sorted(required - root.keys())
    if missing:
        raise ValueError("missing geometry fields: " + ", ".join(missing))
    if not isinstance(root["viewBox"], dict):
        raise ValueError("viewBox must be an object")
    for key in ("minX", "minY", "width", "height"):
        _number(root["viewBox"].get(key), f"viewBox.{key}")
    if not isinstance(root["blobPath"], str) or not root["blobPath"]:
        raise ValueError("blobPath must be a non-empty string")
    if not isinstance(root["starPath"], str) or not root["starPath"]:
        raise ValueError("starPath must be a non-empty string")
    if not isinstance(root["palette"], dict) or len(root["palette"]) != EXPECTED_PALETTE:
        raise ValueError(f"palette count must be {EXPECTED_PALETTE}")
    if not isinstance(root["shapes"], dict) or len(root["shapes"]) != EXPECTED_SHAPES:
        raise ValueError(f"shape count must be {EXPECTED_SHAPES}")
    for name, shape in root["shapes"].items():
        if not isinstance(name, str) or not isinstance(shape, dict) or not isinstance(shape.get("path"), str):
            raise ValueError(f"shape {name!r} must contain a path")
    eyes = root["eyes"]
    if not isinstance(eyes, list) or len(eyes) != EXPECTED_EYE_GROUPS:
        raise ValueError(f"eye group count must be {EXPECTED_EYE_GROUPS}")
    for group_index, group in enumerate(eyes):
        if not isinstance(group, list) or len(group) != 2:
            raise ValueError(f"eyes[{group_index}] must contain left and right polygons")
        for side_index, polygon in enumerate(group):
            if not isinstance(polygon, list) or len(polygon) < 3:
                raise ValueError(f"eyes[{group_index}][{side_index}] must be a polygon")
            for point_index, value in enumerate(polygon):
                _point(value, f"eyes[{group_index}][{side_index}][{point_index}]")


_NUMBER_PATTERN = re.compile(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?")


def _read_path_token(path: str, cursor: int) -> tuple[str | float, int]:
    while cursor < len(path) and path[cursor] in " \t\r\n,":
        cursor += 1
    if cursor >= len(path):
        raise ValueError("unexpected end of path")
    command = path[cursor]
    if command in "MLCZ":
        return command, cursor + 1
    match = _NUMBER_PATTERN.match(path, cursor)
    if match:
        return float(match.group(0)), match.end()
    raise ValueError(f"unsupported or malformed path token at offset {cursor}")


def parse_path(path: str, curve_samples: int = CURVE_SAMPLES) -> tuple[Point, ...]:
    """Parse one closed absolute M/L/C/Z path into a sampled polygon."""

    if not isinstance(path, str) or not path.strip():
        raise ValueError("path must be a non-empty string")
    if curve_samples < 1:
        raise ValueError("curve_samples must be positive")
    tokens: list[str | float] = []
    cursor = 0
    while True:
        while cursor < len(path) and path[cursor] in " \t\r\n,":
            cursor += 1
        if cursor >= len(path):
            break
        token, cursor = _read_path_token(path, cursor)
        tokens.append(token)

    points: list[Point] = []
    index = 0
    current: Point | None = None
    start: Point | None = None
    closed = False

    def read_numbers(count: int) -> list[float]:
        nonlocal index
        values: list[float] = []
        for _ in range(count):
            if index >= len(tokens) or isinstance(tokens[index], str):
                raise ValueError("path command has too few numeric parameters")
            values.append(float(tokens[index]))
            index += 1
        return values

    while index < len(tokens):
        command = tokens[index]
        if not isinstance(command, str):
            raise ValueError("implicit path commands are not accepted")
        index += 1
        if command == "M":
            if current is not None or start is not None:
                raise ValueError("path must contain exactly one move command")
            x, y = read_numbers(2)
            current = (x, y)
            start = current
            points.append(current)
        elif command == "L":
            if current is None:
                raise ValueError("line command before move command")
            x, y = read_numbers(2)
            current = (x, y)
            points.append(current)
        elif command == "C":
            if current is None:
                raise ValueError("curve command before move command")
            c1x, c1y, c2x, c2y, endx, endy = read_numbers(6)
            p0 = current
            p1 = (c1x, c1y)
            p2 = (c2x, c2y)
            p3 = (endx, endy)
            for step in range(1, curve_samples + 1):
                t = step / curve_samples
                u = 1.0 - t
                points.append(
                    (
                        u**3 * p0[0] + 3 * u**2 * t * p1[0] + 3 * u * t**2 * p2[0] + t**3 * p3[0],
                        u**3 * p0[1] + 3 * u**2 * t * p1[1] + 3 * u * t**2 * p2[1] + t**3 * p3[1],
                    )
                )
            current = p3
        elif command == "Z":
            if current is None or start is None:
                raise ValueError("close command before move command")
            if index != len(tokens):
                raise ValueError("tokens after close command are not accepted")
            closed = True
            current = start
        else:
            raise ValueError(f"unsupported path command: {command}")

    if not closed or len(points) < 3:
        raise ValueError("path must be a closed polygon")
    if points[-1] == points[0]:
        points.pop()
    return tuple(points)


def _signed_area(points: Sequence[Point]) -> float:
    return 0.5 * sum(
        points[index][0] * points[(index + 1) % len(points)][1]
        - points[(index + 1) % len(points)][0] * points[index][1]
        for index in range(len(points))
    )


def _cross(a: Point, b: Point, c: Point) -> float:
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _point_in_triangle(point: Point, a: Point, b: Point, c: Point) -> bool:
    epsilon = 1e-8
    return (
        _cross(a, b, point) >= -epsilon
        and _cross(b, c, point) >= -epsilon
        and _cross(c, a, point) >= -epsilon
    )


def triangulate(points: Sequence[Point]) -> tuple[tuple[Point, ...], tuple[Triangle, ...]]:
    """Return CCW points and an ear-clipped triangle index list."""

    if len(points) < 3 or abs(_signed_area(points)) < 1e-9:
        raise ValueError("polygon must have non-zero area and at least three points")
    working = list(points if _signed_area(points) > 0 else reversed(points))
    indices = list(range(len(working)))
    triangles: list[Triangle] = []
    guard = 0
    while len(indices) > 3:
        guard += 1
        if guard > len(points) * len(points):
            raise ValueError("ear clipping could not find a valid triangulation")
        found = False
        for offset in range(len(indices)):
            previous = indices[offset - 1]
            current = indices[offset]
            following = indices[(offset + 1) % len(indices)]
            if _cross(working[previous], working[current], working[following]) <= 1e-8:
                continue
            if any(
                candidate not in (previous, current, following)
                and _point_in_triangle(
                    working[candidate], working[previous], working[current], working[following]
                )
                for candidate in indices
            ):
                continue
            triangles.append((previous, current, following))
            indices.pop(offset)
            found = True
            break
        if not found:
            raise ValueError("ear clipping encountered a degenerate polygon")
    triangles.append((indices[0], indices[1], indices[2]))
    return tuple(working), tuple(triangles)


def _scaled_points(points: Iterable[Point]) -> tuple[IntPoint, ...]:
    result: list[IntPoint] = []
    for x, y in points:
        scaled = (int(round(x * GEOMETRY_SCALE)), int(round(y * GEOMETRY_SCALE)))
        if not all(-32768 <= value <= 32767 for value in scaled):
            raise ValueError("geometry point exceeds int16 range")
        result.append(scaled)
    return tuple(result)


def _polygon_from_points(points: Sequence[Point]) -> PolygonData:
    triangulated_points, triangles = triangulate(points)
    scaled = _scaled_points(triangulated_points)
    center = (
        int(round(sum(point[0] for point in scaled) / len(scaled))),
        int(round(sum(point[1] for point in scaled) / len(scaled))),
    )
    return PolygonData(
        scaled,
        triangles,
        center,
        min(point[0] for point in scaled),
        max(point[0] for point in scaled),
        min(point[1] for point in scaled),
        max(point[1] for point in scaled),
    )


def build_model(root: dict[str, Any], source_sha256: str) -> GeometryModel:
    validate_root(root)
    view_box = {
        key: _number(root["viewBox"][key], f"viewBox.{key}")
        for key in ("minX", "minY", "width", "height")
    }
    body = _polygon_from_points(parse_path(root["blobPath"]))
    eyes: list[tuple[PolygonData, PolygonData]] = []
    for group in root["eyes"]:
        eyes.append(
            (
                _polygon_from_points(tuple(_point(value, "eye point") for value in group[0])),
                _polygon_from_points(tuple(_point(value, "eye point") for value in group[1])),
            )
        )
    return GeometryModel(
        source_sha256=source_sha256,
        view_box=view_box,
        body=body,
        eyes=tuple(eyes),
        shape_names=tuple(root["shapes"].keys()),
        palette_names=tuple(root["palette"].keys()),
    )


def _cpp_polygon(name: str, polygon: PolygonData) -> list[str]:
    lines = [f"const Point {name}Points[] = {{"]
    lines.extend(f"    {{{x}, {y}}}," for x, y in polygon.points)
    lines.append("};")
    lines.append(f"const Triangle {name}Triangles[] = {{")
    lines.extend(f"    {{{a}, {b}, {c}}}," for a, b, c in polygon.triangles)
    lines.append("};")
    lines.extend(
        [
            f"const int16_t {name}CenterX = {polygon.center[0]};",
            f"const int16_t {name}CenterY = {polygon.center[1]};",
            f"const int16_t {name}MinX = {polygon.min_x};",
            f"const int16_t {name}MaxX = {polygon.max_x};",
            f"const int16_t {name}MinY = {polygon.min_y};",
            f"const int16_t {name}MaxY = {polygon.max_y};",
        ]
    )
    return lines


def _polygon_expression(name: str) -> str:
    return (
        "{"
        f"{name}Points, static_cast<uint16_t>(sizeof({name}Points) / sizeof(Point)), "
        f"{name}Triangles, static_cast<uint16_t>(sizeof({name}Triangles) / sizeof(Triangle)), "
        f"{name}CenterX, {name}CenterY, {name}MinX, {name}MaxX, {name}MinY, {name}MaxY"
        "}"
    )


def render_header(model: GeometryModel) -> str:
    return """#pragma once

#include <cstddef>
#include <cstdint>

namespace grok_geometry {

constexpr int16_t kGeometryScale = 100;

struct Point {
  int16_t x;
  int16_t y;
};

struct Triangle {
  uint16_t a;
  uint16_t b;
  uint16_t c;
};

struct Polygon {
  const Point* points;
  uint16_t pointCount;
  const Triangle* triangles;
  uint16_t triangleCount;
  int16_t centerX;
  int16_t centerY;
  int16_t minX;
  int16_t maxX;
  int16_t minY;
  int16_t maxY;
};

struct EyeGroup {
  Polygon left;
  Polygon right;
};

extern const uint16_t kSourceEyeGroupCount;
extern const uint16_t kSourceShapeCount;
extern const uint16_t kSourcePaletteCount;
extern const char kSourceRepository[];
extern const char kSourceCommit[];
extern const char kSourceSha256[];
extern const char* const kSourceShapeNames[];
extern const char* const kSourcePaletteNames[];

extern const Polygon kBody;
extern const EyeGroup kEyeGroups[];

}  // namespace grok_geometry
"""


def render_cpp(model: GeometryModel) -> str:
    lines = [
        '#include "grok_geometry.h"',
        "",
        "namespace grok_geometry {",
        "",
        f"const uint16_t kSourceEyeGroupCount = {len(model.eyes)};",
        f"const uint16_t kSourceShapeCount = {len(model.shape_names)};",
        f"const uint16_t kSourcePaletteCount = {len(model.palette_names)};",
        f'const char kSourceRepository[] = "{SOURCE_REPOSITORY}";',
        f'const char kSourceCommit[] = "{SOURCE_COMMIT}";',
        f'const char kSourceSha256[] = "{model.source_sha256}";',
        "",
        "const char* const kSourceShapeNames[] = {",
    ]
    lines.extend(f'    "{name}",' for name in model.shape_names)
    lines.extend(["};", "", "const char* const kSourcePaletteNames[] = {"])
    lines.extend(f'    "{name}",' for name in model.palette_names)
    lines.extend(["};", ""])

    lines.extend(_cpp_polygon("kBody", model.body))
    lines.append("")
    lines.append(f"const Polygon kBody = {_polygon_expression('kBody')};")
    lines.append("")

    for index, (left, right) in enumerate(model.eyes):
        lines.extend(_cpp_polygon(f"kEye{index}Left", left))
        lines.append("")
        lines.extend(_cpp_polygon(f"kEye{index}Right", right))
        lines.append("")

    lines.append("const EyeGroup kEyeGroups[] = {")
    for index in range(len(model.eyes)):
        lines.append(
            f"    {{ {_polygon_expression(f'kEye{index}Left')}, {_polygon_expression(f'kEye{index}Right')} }},"
        )
    lines.extend(["};", "", "}  // namespace grok_geometry", ""])
    return "\n".join(lines)


def render_manifest(model: GeometryModel) -> str:
    def polygon_manifest(polygon: PolygonData) -> dict[str, int]:
        return {"vertices": len(polygon.points), "triangles": len(polygon.triangles)}

    manifest = {
        "converter": {
            "curveSamplesPerCubicSegment": CURVE_SAMPLES,
            "geometryScale": GEOMETRY_SCALE,
            "pathCommands": "MLCZ absolute uppercase only",
            "triangulation": "ear clipping",
        },
        "counts": {
            "eyeGroups": len(model.eyes),
            "palette": len(model.palette_names),
            "shapes": len(model.shape_names),
        },
        "source": {
            "file": SOURCE_FILE,
            "repository": SOURCE_REPOSITORY,
            "sha256": model.source_sha256,
            "commit": SOURCE_COMMIT,
        },
        "viewBox": model.view_box,
        "body": polygon_manifest(model.body),
        "eyes": [
            {
                "index": index,
                "left": polygon_manifest(left),
                "right": polygon_manifest(right),
            }
            for index, (left, right) in enumerate(model.eyes)
        ],
        "shapeNames": list(model.shape_names),
        "paletteNames": list(model.palette_names),
    }
    return json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def write_outputs(model: GeometryModel, header_path: Path, cpp_path: Path, manifest_path: Path) -> None:
    for path in (header_path, cpp_path, manifest_path):
        path.parent.mkdir(parents=True, exist_ok=True)
    header_path.write_text(render_header(model), encoding="utf-8", newline="\n")
    cpp_path.write_text(render_cpp(model), encoding="utf-8", newline="\n")
    manifest_path.write_text(render_manifest(model), encoding="utf-8", newline="\n")


def _check_outputs(model: GeometryModel, header_path: Path, cpp_path: Path, manifest_path: Path) -> int:
    with tempfile.TemporaryDirectory(prefix="grok-geometry-check-") as directory:
        temporary = Path(directory)
        expected = {
            header_path: render_header(model),
            cpp_path: render_cpp(model),
            manifest_path: render_manifest(model),
        }
        for path, content in expected.items():
            if not path.is_file() or path.read_text(encoding="utf-8") != content:
                print(f"OUTDATED: {path}")
                return 1
        _ = temporary
    print("deterministic outputs: PASS")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--header", type=Path, required=True)
    parser.add_argument("--cpp", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    root, source_sha256 = load_source(args.source)
    model = build_model(root, source_sha256)
    if args.check:
        return _check_outputs(model, args.header, args.cpp, args.manifest)
    write_outputs(model, args.header, args.cpp, args.manifest)
    print(
        "generated geometry: "
        f"body={len(model.body.points)} vertices/{len(model.body.triangles)} triangles, "
        f"eyes={len(model.eyes)} groups, source_sha256={model.source_sha256}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
