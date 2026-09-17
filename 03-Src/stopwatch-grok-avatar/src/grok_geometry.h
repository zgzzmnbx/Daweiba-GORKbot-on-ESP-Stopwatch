#pragma once

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
