"""Render offline SVG previews using the same converted Grok geometry."""

from __future__ import annotations

import html
import math
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from convert_grok_geometry import GeometryModel, load_source, build_model  # noqa: E402


PREVIEW_SIZE = 466
SAFE_RADIUS = PREVIEW_SIZE / 2 - 12
DESIGN_SCALE = PREVIEW_SIZE / 1000.0
BODY_SOURCE_SCALE = 3.55
EYE_WIDTH_SCALE = 0.82
EYE_HEIGHT_SCALE = 0.64
EYE_GROUP_MAP = (0, 1, 2, 3, 4, 5, 6, 7, 3, 7, 7, 2)
SOURCE_EYE_GROUP_MAP = (8, 10, 14, 2, 17, 7, 23, 4)
STATE_NAMES = (
    "idle",
    "listening",
    "thinking",
    "happy",
    "excited",
    "curious",
    "confused",
    "angry",
    "surprised",
    "sad",
    "sleepy",
    "dizzy",
)


@dataclass(frozen=True)
class EyePose:
    x: float
    y: float
    width: float
    height: float
    angle: float = 0.0
    upper_lid: float = 0.0
    upper_lid_tilt: float = 0.0
    lower_lid: float = 0.0
    brow_y: float = -230.0
    brow_tilt: float = 0.0
    brow_opacity: float = 0.0


@dataclass(frozen=True)
class StatePreview:
    name: str
    eye_group: int
    left: EyePose
    right: EyePose
    body_scale: float = 1.0
    face_x: float = 0.0
    face_y: float = 0.0
    head_roll: float = 0.0
    blink: float = 1.0


def state_previews() -> tuple[StatePreview, ...]:
    return (
        StatePreview("idle", 0, EyePose(-225, -15, 155, 360), EyePose(225, -15, 155, 360)),
        StatePreview("listening", 1, EyePose(-220, -18, 160, 325, -1), EyePose(220, -18, 160, 325, 1), face_y=-9, head_roll=0),
        StatePreview("thinking", 2, EyePose(-220, -30, 178, 305, -5), EyePose(220, -34, 150, 250, 8), face_y=-12, head_roll=4),
        StatePreview("happy", 3, EyePose(-225, 5, 180, 285), EyePose(225, 5, 180, 285), body_scale=1.02, face_y=4),
        StatePreview("excited", 4, EyePose(-220, 18, 205, 112, -3), EyePose(220, 18, 205, 112, 3), body_scale=1.06, face_y=10),
        StatePreview("curious", 5, EyePose(-220, -16, 160, 320, -2), EyePose(220, -16, 160, 320, 2), face_y=-6, head_roll=2),
        StatePreview("confused", 6, EyePose(-220, -12, 188, 290, 9), EyePose(220, -26, 145, 250, -7), face_y=-5, head_roll=-5),
        StatePreview("angry", 7, EyePose(-220, -18, 205, 245, 0, 0.15, 0.45, 0, -190, 17, 0.72), EyePose(220, -18, 205, 245, 0, 0.15, -0.45, 0, -190, -17, 0.72), face_y=4),
        StatePreview("surprised", 3, EyePose(-225, 5, 205, 92), EyePose(225, 5, 205, 92), body_scale=1.04, face_y=2),
        StatePreview("sad", 7, EyePose(-220, -5, 180, 275, 0, 0.08, -0.20, 0, -210, -12, 0.55), EyePose(220, -5, 180, 275, 0, 0.08, 0.20, 0, -210, 12, 0.55), face_y=4),
        StatePreview("sleepy", 7, EyePose(-215, 18, 245, 165, 0, 0.28), EyePose(215, 18, 245, 165, 0, 0.28), body_scale=0.99, face_y=18, blink=0.88),
        StatePreview("dizzy", 2, EyePose(-210, -10, 270, 270), EyePose(210, 4, 244, 244), body_scale=1.02, face_y=-5, head_roll=-4),
    )


def _lerp(start: float, end: float, amount: float) -> float:
    return start + (end - start) * amount


def _blend_eye(start: EyePose, end: EyePose, amount: float) -> EyePose:
    return EyePose(
        x=_lerp(start.x, end.x, amount),
        y=_lerp(start.y, end.y, amount),
        width=_lerp(start.width, end.width, amount),
        height=_lerp(start.height, end.height, amount),
        angle=_lerp(start.angle, end.angle, amount),
        upper_lid=_lerp(start.upper_lid, end.upper_lid, amount),
        upper_lid_tilt=_lerp(start.upper_lid_tilt, end.upper_lid_tilt, amount),
        lower_lid=_lerp(start.lower_lid, end.lower_lid, amount),
        brow_y=_lerp(start.brow_y, end.brow_y, amount),
        brow_tilt=_lerp(start.brow_tilt, end.brow_tilt, amount),
        brow_opacity=_lerp(start.brow_opacity, end.brow_opacity, amount),
    )


def _blend_state(start: StatePreview, end: StatePreview, amount: float) -> StatePreview:
    return StatePreview(
        name=f"{end.name} · mid",
        eye_group=end.eye_group,
        left=_blend_eye(start.left, end.left, amount),
        right=_blend_eye(start.right, end.right, amount),
        body_scale=_lerp(start.body_scale, end.body_scale, amount),
        face_x=_lerp(start.face_x, end.face_x, amount),
        face_y=_lerp(start.face_y, end.face_y, amount),
        head_roll=_lerp(start.head_roll, end.head_roll, amount),
        blink=_lerp(start.blink, end.blink, amount),
    )


def _rotate(x: float, y: float, angle: float) -> tuple[float, float]:
    radians = angle * math.pi / 180.0
    cosine = math.cos(radians)
    sine = math.sin(radians)
    return x * cosine - y * sine, x * sine + y * cosine


def _body_outline_points(
    model: GeometryModel, polygon_name: str, scale: float, roll: float,
    cx: float, cy: float
) -> list[tuple[float, float]]:
    polygon = getattr(model, polygon_name)
    points = []
    for point in polygon.points:
        local_x = (point[0] - polygon.center[0]) / 100.0 * BODY_SOURCE_SCALE * DESIGN_SCALE * scale
        local_y = (point[1] - polygon.center[1]) / 100.0 * BODY_SOURCE_SCALE * DESIGN_SCALE * scale
        rotated_x, rotated_y = _rotate(local_x, local_y, roll)
        points.append((cx + rotated_x, cy + rotated_y))
    return points


def _eye_outline_points(
    polygon, eye: EyePose, body_scale: float, blink: float, cx: float, cy: float
) -> list[tuple[float, float]]:
    source_width = max(1, polygon.max_x - polygon.min_x)
    source_height = max(1, polygon.max_y - polygon.min_y)
    target_width = eye.width * body_scale * DESIGN_SCALE * EYE_WIDTH_SCALE
    target_height = eye.height * body_scale * DESIGN_SCALE * EYE_HEIGHT_SCALE * blink
    eye_cx = cx + eye.x * body_scale * DESIGN_SCALE
    eye_cy = cy + eye.y * body_scale * DESIGN_SCALE
    points = []
    for point in polygon.points:
        local_x = (point[0] - polygon.center[0]) / source_width * target_width
        local_y = (point[1] - polygon.center[1]) / source_height * target_height
        rotated_x, rotated_y = _rotate(local_x, local_y, eye.angle)
        points.append((eye_cx + rotated_x, eye_cy + rotated_y))
    return points


def _polygon(points: list[tuple[float, float]], fill: str) -> str:
    coordinates = " ".join(f"{x:.2f},{y:.2f}" for x, y in points)
    return f'<polygon points="{coordinates}" fill="{fill}" />'


def _state_points(model: GeometryModel, state: StatePreview) -> list[tuple[float, float]]:
    cx = PREVIEW_SIZE / 2 + state.face_x * DESIGN_SCALE
    cy = PREVIEW_SIZE / 2 + state.face_y * DESIGN_SCALE
    group = model.eyes[SOURCE_EYE_GROUP_MAP[state.eye_group]]
    points = _body_outline_points(model, "body", state.body_scale, state.head_roll, cx, cy)
    points.extend(_eye_outline_points(group[0], state.left, state.body_scale, state.blink, cx, cy))
    points.extend(_eye_outline_points(group[1], state.right, state.body_scale, state.blink, cx, cy))
    for eye in (state.left, state.right):
        eye_cx = cx + eye.x * state.body_scale * DESIGN_SCALE
        eye_cy = cy + eye.y * state.body_scale * DESIGN_SCALE
        width = eye.width * state.body_scale * DESIGN_SCALE * EYE_WIDTH_SCALE
        height = eye.height * state.body_scale * DESIGN_SCALE * EYE_HEIGHT_SCALE * state.blink
        left = eye_cx - width / 2 - 3
        right = eye_cx + width / 2 + 3
        if eye.upper_lid > 0.01:
            cover = height * min(1.0, eye.upper_lid)
            top = eye_cy - height / 2 - 3
            points.extend(((left, top), (right, top), (right, top + cover + 4), (left, top + cover + 4)))
        if eye.lower_lid > 0.01:
            cover = height * min(1.0, eye.lower_lid)
            top = eye_cy + height / 2 - cover
            points.extend(((left, top), (right, top), (right, top + cover + 4), (left, top + cover + 4)))
        if eye.brow_opacity > 0.01:
            radians = eye.brow_tilt * math.pi / 180.0
            half_length = width * 0.44
            brow_x = eye_cx
            brow_y = cy + (eye.y + eye.brow_y) * state.body_scale * DESIGN_SCALE
            dx = math.cos(radians) * half_length
            dy = math.sin(radians) * half_length
            points.extend(((brow_x - dx, brow_y - dy), (brow_x + dx, brow_y + dy)))
    return points


def validate_state_geometry(model: GeometryModel, state: StatePreview) -> tuple[float, float, float, float, float]:
    points = _state_points(model, state)
    min_x = min(point[0] for point in points)
    max_x = max(point[0] for point in points)
    min_y = min(point[1] for point in points)
    max_y = max(point[1] for point in points)
    canvas_center = PREVIEW_SIZE / 2
    max_radius = max(
        math.hypot(point[0] - canvas_center, point[1] - canvas_center)
        for point in points
    )
    if min_x < 0 or max_x > PREVIEW_SIZE or min_y < 0 or max_y > PREVIEW_SIZE:
        raise ValueError(f"{state.name} leaves the {PREVIEW_SIZE}x{PREVIEW_SIZE} canvas")
    if max_radius > SAFE_RADIUS:
        raise ValueError(f"{state.name} crosses the safe circle: radius={max_radius:.2f}")
    return min_x, max_x, min_y, max_y, max_radius


def _render_state_shapes(
    model: GeometryModel, state: StatePreview, offset_x: float = 0.0
) -> list[str]:
    cx = offset_x + PREVIEW_SIZE / 2 + state.face_x * DESIGN_SCALE
    cy = PREVIEW_SIZE / 2 + state.face_y * DESIGN_SCALE
    parts: list[str] = []
    parts.append(
        _polygon(
            _body_outline_points(model, "body", state.body_scale, state.head_roll, cx, cy),
            "#F7F8F4",
        )
    )
    group = model.eyes[SOURCE_EYE_GROUP_MAP[state.eye_group]]
    parts.append(
        _polygon(
            _eye_outline_points(group[0], state.left, state.body_scale, state.blink, cx, cy),
            "#050608",
        )
    )
    parts.append(
        _polygon(
            _eye_outline_points(group[1], state.right, state.body_scale, state.blink, cx, cy),
            "#050608",
        )
    )
    for eye in (state.left, state.right):
        eye_cx = cx + eye.x * state.body_scale * DESIGN_SCALE
        eye_cy = cy + eye.y * state.body_scale * DESIGN_SCALE
        width = eye.width * state.body_scale * DESIGN_SCALE * EYE_WIDTH_SCALE
        height = eye.height * state.body_scale * DESIGN_SCALE * EYE_HEIGHT_SCALE * state.blink
        if eye.upper_lid > 0.01:
            cover = height * min(1.0, eye.upper_lid)
            parts.append(f'<rect x="{eye_cx - width / 2 - 3:.2f}" y="{eye_cy - height / 2 - 3:.2f}" width="{width + 6:.2f}" height="{cover + 4:.2f}" fill="#F7F8F4" />')
        if eye.lower_lid > 0.01:
            cover = height * min(1.0, eye.lower_lid)
            parts.append(f'<rect x="{eye_cx - width / 2 - 3:.2f}" y="{eye_cy + height / 2 - cover:.2f}" width="{width + 6:.2f}" height="{cover + 4:.2f}" fill="#F7F8F4" />')
        if eye.brow_opacity > 0.01:
            radians = eye.brow_tilt * math.pi / 180.0
            half_length = width * 0.44
            brow_x = eye_cx
            brow_y = cy + (eye.y + eye.brow_y) * state.body_scale * DESIGN_SCALE
            dx = math.cos(radians) * half_length
            dy = math.sin(radians) * half_length
            parts.append(f'<line x1="{brow_x - dx:.2f}" y1="{brow_y - dy:.2f}" x2="{brow_x + dx:.2f}" y2="{brow_y + dy:.2f}" stroke="#15171B" stroke-width="{max(2, height * 0.04):.2f}" stroke-linecap="round" />')
    return parts


def render_svg(model: GeometryModel, state: StatePreview) -> str:
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{PREVIEW_SIZE}" height="{PREVIEW_SIZE}" viewBox="0 0 {PREVIEW_SIZE} {PREVIEW_SIZE}">',
        '<rect width="100%" height="100%" fill="#080b10" />',
        '<g shape-rendering="geometricPrecision">',
    ]
    parts.extend(_render_state_shapes(model, state))
    parts.extend(
        [
            "</g>",
            f'<title>{html.escape(state.name)} — implemented eye group {state.eye_group} — source eye group {SOURCE_EYE_GROUP_MAP[state.eye_group]}</title>',
            "</svg>",
        ]
    )
    return "\n".join(parts) + "\n"


def render_transition_svg(
    model: GeometryModel, states: tuple[StatePreview, StatePreview, StatePreview]
) -> str:
    width = PREVIEW_SIZE * len(states)
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{PREVIEW_SIZE}" viewBox="0 0 {width} {PREVIEW_SIZE}">',
        '<rect width="100%" height="100%" fill="#080b10" />',
        '<g shape-rendering="geometricPrecision">',
    ]
    for index, state in enumerate(states):
        offset_x = index * PREVIEW_SIZE
        parts.extend(_render_state_shapes(model, state, offset_x))
        parts.append(
            f'<text x="{offset_x + 18}" y="{PREVIEW_SIZE - 16}" fill="#9da8b6" font-family="system-ui, sans-serif" font-size="14">{html.escape(state.name)}</text>'
        )
    parts.extend(["</g>", "</svg>"])
    return "\n".join(parts) + "\n"


def render_index(output_dir: Path, states: tuple[StatePreview, ...]) -> str:
    cards = []
    for index, state in enumerate(states, start=1):
        filename = f"status-{index:02d}-{state.name}.svg"
        cards.append(
            "<article>"
            f"<img src='{filename}' alt='{html.escape(state.name)}'>"
            f"<h2>{index:02d} · {html.escape(state.name)}</h2>"
            f"<p>implemented eye group {state.eye_group} · source eye group {SOURCE_EYE_GROUP_MAP[state.eye_group]} · expression {index - 1}</p>"
            "</article>"
        )
    return """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>Grok avatar v0.2.0 previews</title>
<style>
  :root { color-scheme: dark; background: #080b10; color: #e9edf2; font: 15px/1.4 system-ui, sans-serif; }
  body { margin: 0; padding: 28px; }
  h1 { margin: 0 0 8px; font-size: 24px; }
  .note { color: #9da8b6; margin: 0 0 24px; }
  .grid { display: grid; grid-template-columns: repeat(4, minmax(180px, 1fr)); gap: 18px; max-width: 1100px; }
  article { background: #111720; border: 1px solid #253140; border-radius: 14px; padding: 12px; }
  img { display: block; width: 100%; aspect-ratio: 1; border-radius: 10px; background: #080b10; }
  h2 { margin: 10px 0 2px; font-size: 16px; }
  p { margin: 0; color: #8e9aa8; font-size: 12px; }
  .transitions { display: grid; grid-template-columns: repeat(3, minmax(240px, 1fr)); gap: 18px; max-width: 1100px; }
  figure { margin: 0; background: #111720; border: 1px solid #253140; border-radius: 14px; padding: 12px; }
  .transitions img { aspect-ratio: 3 / 1; }
  figcaption { margin-top: 8px; color: #e9edf2; font-size: 14px; }
</style></head><body>
<h1>Grok avatar geometry review · v0.2.0</h1>
<p class="note">Offline previews from the locked source geometry. White body, black eyes, 466 × 466 render space.</p>
<main class="grid">""" + "\n".join(cards) + """</main>
<h1 style="margin-top:32px">Keyframe comparisons</h1>
<section class="transitions">
  <figure><img src="transition-idle-happy.svg" alt="idle to happy keyframes"><figcaption>idle → happy</figcaption></figure>
  <figure><img src="transition-idle-thinking.svg" alt="idle to thinking keyframes"><figcaption>idle → thinking</figcaption></figure>
  <figure><img src="transition-idle-dizzy.svg" alt="idle to dizzy keyframes"><figcaption>idle → dizzy</figcaption></figure>
</section>
</body></html>
"""


def main() -> int:
    source = ROOT / "03-Src" / "stopwatch-grok-avatar" / "assets" / "source-grok-study" / "geometry-data.js"
    output_dir = ROOT / "04-output" / "v0.2.0" / "previews"
    root, sha256 = load_source(source)
    model = build_model(root, sha256)
    states = state_previews()
    output_dir.mkdir(parents=True, exist_ok=True)
    for state in states:
        min_x, max_x, min_y, max_y, max_radius = validate_state_geometry(model, state)
        print(
            f"bounds {state.name}: x={min_x:.1f}..{max_x:.1f} "
            f"y={min_y:.1f}..{max_y:.1f} radius={max_radius:.1f}/{SAFE_RADIUS:.1f} PASS"
        )
    for index, state in enumerate(states, start=1):
        filename = output_dir / f"status-{index:02d}-{state.name}.svg"
        filename.write_text(render_svg(model, state), encoding="utf-8", newline="\n")
    transition_groups = {
        "transition-idle-happy.svg": (states[0], _blend_state(states[0], states[3], 0.5), states[3]),
        "transition-idle-thinking.svg": (states[0], _blend_state(states[0], states[2], 0.5), states[2]),
        "transition-idle-dizzy.svg": (states[0], _blend_state(states[0], states[11], 0.5), states[11]),
    }
    for filename, transition in transition_groups.items():
        (output_dir / filename).write_text(
            render_transition_svg(model, transition), encoding="utf-8", newline="\n"
        )
    (output_dir / "index.html").write_text(render_index(output_dir, states), encoding="utf-8", newline="\n")
    print(f"rendered {len(states)} previews to {output_dir}")
    print("implemented eye groups:", ", ".join(str(value) for value in EYE_GROUP_MAP))
    print("source eye groups:", ", ".join(str(value) for value in SOURCE_EYE_GROUP_MAP))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
