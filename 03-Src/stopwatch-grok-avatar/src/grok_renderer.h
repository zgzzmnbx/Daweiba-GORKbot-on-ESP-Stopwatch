// SPDX-License-Identifier: AGPL-3.0-or-later

#pragma once

#include <M5Unified.h>

#include "grok_geometry.h"

class GrokRenderer {
 public:
  struct EyeState {
    float x;
    float y;
    float width;
    float height;
    float upperLid;
    float upperLidTilt;
    float lowerLid;
    float browY;
    float browTilt;
    float browOpacity;
    float angle;
  };

  struct Frame {
    int16_t centerX;
    int16_t centerY;
    float bodyScale;
    float blink;
    float headRoll;
    uint8_t expressionIndex;
    EyeState leftEye;
    EyeState rightEye;
  };

  struct Bounds {
    Bounds() = default;
    Bounds(int16_t rectX, int16_t rectY, int16_t rectWidth,
           int16_t rectHeight, bool isValid)
        : x(rectX), y(rectY), width(rectWidth), height(rectHeight),
          valid(isValid) {}

    int16_t x = 0;
    int16_t y = 0;
    int16_t width = 0;
    int16_t height = 0;
    bool valid = false;
  };

  static constexpr uint8_t kImplementedEyeGroups = 8;

  Bounds bounds(const Frame& frame) const;
  Bounds boundsForEye(const Frame& frame, bool left) const;
  void drawBody() const;
  void draw(const Frame& frame) const;

  static uint8_t eyeGroupForExpression(uint8_t expressionIndex);
  static uint16_t geometryPointCount(uint8_t expressionIndex);

 private:
  struct ScreenPoint {
    int16_t x;
    int16_t y;
  };

  static int32_t scaledDelta(int32_t sourceDelta, int32_t scaleQ16);
  static ScreenPoint transformBodyPoint(const grok_geometry::Point& point,
                                        int32_t scaleQ16, int32_t cosQ15,
                                        int32_t sinQ15, int16_t centerX,
                                        int16_t centerY);
  static ScreenPoint transformEyePoint(const grok_geometry::Point& point,
                                       const grok_geometry::Polygon& polygon,
                                       int32_t scaleXQ16, int32_t scaleYQ16,
                                       int32_t cosQ15, int32_t sinQ15,
                                       int16_t eyeCenterX, int16_t eyeCenterY);
  static void drawPolygon(const grok_geometry::Polygon& polygon,
                          const EyeState& eye, float blink, int16_t centerX,
                          int16_t centerY);
  static void drawEyeLids(const EyeState& eye, float blink, int16_t centerX,
                          int16_t centerY);
  static void drawBrow(const EyeState& eye, int16_t centerX,
                       int16_t centerY);
};
