"""Unit and negative tests for the deterministic Grok geometry converter."""

from __future__ import annotations

import sys
import unittest
from copy import deepcopy
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from convert_grok_geometry import (  # noqa: E402
    CURVE_SAMPLES,
    EXPECTED_EYE_GROUPS,
    EXPECTED_PALETTE,
    EXPECTED_SHAPES,
    build_model,
    load_source,
    parse_path,
    triangulate,
    validate_root,
)


SOURCE = ROOT / "03-Src" / "stopwatch-grok-avatar" / "assets" / "source-grok-study" / "geometry-data.js"


def polygon_area(points: tuple[tuple[float, float], ...]) -> float:
    return abs(
        0.5
        * sum(
            points[index][0] * points[(index + 1) % len(points)][1]
            - points[(index + 1) % len(points)][0] * points[index][1]
            for index in range(len(points))
        )
    )


class GrokGeometryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.root, cls.sha256 = load_source(SOURCE)
        cls.model = build_model(cls.root, cls.sha256)

    def test_source_counts(self) -> None:
        self.assertEqual(len(self.model.eyes), EXPECTED_EYE_GROUPS)
        self.assertEqual(len(self.model.shape_names), EXPECTED_SHAPES)
        self.assertEqual(len(self.model.palette_names), EXPECTED_PALETTE)

    def test_path_parser_samples_curves_and_closes(self) -> None:
        points = parse_path("M0 0C0 10 10 10 10 0Z")
        self.assertEqual(len(points), 1 + CURVE_SAMPLES)
        self.assertEqual(points[0], (0.0, 0.0))
        self.assertEqual(points[-1], (10.0, 0.0))

    def test_all_polygons_triangulate_without_area_loss(self) -> None:
        source_body = parse_path(self.root["blobPath"])
        points, triangles = triangulate(source_body)
        source_area = polygon_area(points)
        triangle_area = sum(
            polygon_area((points[a], points[b], points[c])) for a, b, c in triangles
        )
        self.assertAlmostEqual(source_area, triangle_area, places=3)
        for group in self.root["eyes"]:
            for polygon in group:
                source_points = tuple(tuple(point) for point in polygon)
                points, triangles = triangulate(source_points)
                source_area = polygon_area(points)
                triangle_area = sum(
                    polygon_area((points[a], points[b], points[c])) for a, b, c in triangles
                )
                self.assertAlmostEqual(source_area, triangle_area, places=2)

    def test_unsupported_lowercase_command_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            parse_path("M0 0c0 10 10 10 10 0Z")

    def test_missing_geometry_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            validate_root({})

    def test_missing_eye_groups_are_rejected(self) -> None:
        root = deepcopy(self.root)
        root.pop("eyes")
        with self.assertRaises(ValueError):
            validate_root(root)

    def test_geometry_outside_fixed_point_range_is_rejected(self) -> None:
        root = deepcopy(self.root)
        root["blobPath"] = "M0 0L400 0L0 400Z"
        with self.assertRaises(ValueError):
            build_model(root, self.sha256)

    def test_fixed_point_output_stays_in_int16_range(self) -> None:
        self.assertTrue(
            all(
                -32768 <= value <= 32767
                for point in self.model.body.points
                for value in point
            )
        )
        self.assertTrue(all(-32768 <= value <= 32767 for group in self.model.eyes for polygon in group for point in polygon.points for value in point))


if __name__ == "__main__":
    unittest.main(verbosity=2)
