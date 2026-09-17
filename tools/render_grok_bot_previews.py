"""Create deterministic 466px design checks from the pinned Grok bot data.

These images approximate the firmware's 2D projection; the website remains
the visual reference and real-device photos remain the hardware evidence.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

from PIL import Image, ImageDraw

from generate_grok_bot_catalog import ROOT, SEQUENCES, SOURCE


OUTPUT = ROOT / "04-output/v0.2.1/previews"
SIZE = 466
SCALE = 430.0 / 240.0


def draw_eye(draw: ImageDraw.ImageDraw, expression: dict, suffix: str, side: int) -> None:
    width = expression[f"width{suffix}"] * SCALE
    height = expression[f"height{suffix}"] * SCALE
    x = SIZE / 2 + (side * expression["spacing"] / 2 + expression[f"positionX{suffix}"]) * SCALE
    y = SIZE / 2 + expression[f"positionY{suffix}"] * SCALE
    angle = math.radians(expression["leftAngle" if side < 0 else "rightAngle"] + expression["headZ"])
    if height >= width:
        axis = angle + math.pi / 2
        half_length = (height - width) / 2
        thickness = width
    else:
        axis = angle
        half_length = (width - height) / 2
        thickness = height
    dx, dy = math.cos(axis) * half_length, math.sin(axis) * half_length
    first, second = (x - dx, y - dy), (x + dx, y + dy)
    radius = thickness / 2
    draw.line((first, second), fill="white", width=max(1, round(thickness)))
    for cx, cy in (first, second):
        draw.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), fill="white")


def main() -> None:
    data = json.loads(SOURCE.read_text(encoding="utf-8"))
    expressions = {item["id"]: item for item in data["expressions"]}
    sequences = {item["id"]: item for item in data["sequences"]}
    OUTPUT.mkdir(parents=True, exist_ok=True)
    board = Image.new("RGB", (466 * 5, 510 * 5), "#151922")
    board_draw = ImageDraw.Draw(board)
    for index, name in enumerate(SEQUENCES):
        expression = expressions[sequences[name]["steps"][0]["expressionId"]]
        image = Image.new("RGB", (SIZE, SIZE), "#151922")
        draw = ImageDraw.Draw(image)
        draw.ellipse((17, 17, SIZE - 18, SIZE - 18), fill="black")
        draw_eye(draw, expression, "Left", -1)
        draw_eye(draw, expression, "Right", 1)
        image.save(OUTPUT / f"{index:02d}-{name}.png")
        row, col = divmod(index, 5)
        board.paste(image, (col * 466, row * 510))
        board_draw.text((col * 466 + 20, row * 510 + 469), name, fill="white")
    board.save(OUTPUT / "Grok-bot-23-sequences-contact-sheet.png")
    print(f"Rendered {len(SEQUENCES)} first-step previews to {OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
