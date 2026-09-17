// SPDX-License-Identifier: AGPL-3.0-or-later

#include "grok_renderer.h"

#include <algorithm>
#include <cmath>

namespace {

constexpr float kPi = 3.14159265358979323846f;
constexpr uint16_t kBotColor = TFT_BLACK;
constexpr uint16_t kEyeColor = TFT_WHITE;
constexpr int kBodyInset = 17;

GrokRenderer::Bounds eyeBounds(const GrokRenderer::EyeState& eye,
                               int centerX, int centerY) {
  const float radians = eye.angle * kPi / 180.0f;
  const float halfWidth = fabsf(cosf(radians)) * eye.width * 0.5f +
                          fabsf(sinf(radians)) * eye.height * 0.5f;
  const float halfHeight = fabsf(sinf(radians)) * eye.width * 0.5f +
                           fabsf(cosf(radians)) * eye.height * 0.5f;
  const int left = floorf(centerX + eye.x - halfWidth) - 5;
  const int top = floorf(centerY + eye.y - halfHeight) - 5;
  const int right = ceilf(centerX + eye.x + halfWidth) + 5;
  const int bottom = ceilf(centerY + eye.y + halfHeight) + 5;
  return {static_cast<int16_t>(left), static_cast<int16_t>(top),
          static_cast<int16_t>(right - left),
          static_cast<int16_t>(bottom - top), true};
}

void drawEye(const GrokRenderer::EyeState& eye, int centerX, int centerY,
             float blink) {
  const float width = std::max(3.0f, eye.width);
  const float height = std::max(3.0f, eye.height * blink);
  const float radians = eye.angle * kPi / 180.0f;
  const float axisLength = fabsf(height - width) * 0.5f;
  const float axisAngle = height >= width ? radians + kPi * 0.5f : radians;
  const float dx = cosf(axisAngle) * axisLength;
  const float dy = sinf(axisAngle) * axisLength;
  const int x = lroundf(centerX + eye.x);
  const int y = lroundf(centerY + eye.y);
  const float radius = std::min(width, height) * 0.5f;
  if (axisLength < 0.5f) {
    M5.Display.fillCircle(x, y, lroundf(radius), kEyeColor);
    return;
  }
  M5.Display.drawWideLine(lroundf(x - dx), lroundf(y - dy),
                          lroundf(x + dx), lroundf(y + dy), radius, kEyeColor);
}

}  // namespace

uint8_t GrokRenderer::eyeGroupForExpression(uint8_t expressionIndex) {
  return expressionIndex;
}

uint16_t GrokRenderer::geometryPointCount(uint8_t) {
  return 66;  // 32-point eye contours plus the circular body outline.
}

void GrokRenderer::drawBody() const {
  const int radius = std::min(M5.Display.width(), M5.Display.height()) / 2 -
                     kBodyInset;
  M5.Display.fillCircle(M5.Display.width() / 2, M5.Display.height() / 2,
                        radius, kBotColor);
}

GrokRenderer::Bounds GrokRenderer::bounds(const Frame& frame) const {
  const Bounds left = eyeBounds(frame.leftEye, frame.centerX, frame.centerY);
  const Bounds right = eyeBounds(frame.rightEye, frame.centerX, frame.centerY);
  const int x0 = std::max(0, std::min<int>(left.x, right.x));
  const int y0 = std::max(0, std::min<int>(left.y, right.y));
  const int x1 = std::min(M5.Display.width(),
                          std::max<int>(left.x + left.width,
                                        right.x + right.width));
  const int y1 = std::min(M5.Display.height(),
                          std::max<int>(left.y + left.height,
                                        right.y + right.height));
  return {static_cast<int16_t>(x0), static_cast<int16_t>(y0),
          static_cast<int16_t>(std::max(0, x1 - x0)),
          static_cast<int16_t>(std::max(0, y1 - y0)), true};
}

GrokRenderer::Bounds GrokRenderer::boundsForEye(const Frame& frame,
                                                 bool left) const {
  const Bounds raw = eyeBounds(left ? frame.leftEye : frame.rightEye,
                               frame.centerX, frame.centerY);
  const int x0 = std::max(0, static_cast<int>(raw.x));
  const int y0 = std::max(0, static_cast<int>(raw.y));
  const int x1 = std::min(M5.Display.width(),
                          static_cast<int>(raw.x + raw.width));
  const int y1 = std::min(M5.Display.height(),
                          static_cast<int>(raw.y + raw.height));
  return {static_cast<int16_t>(x0), static_cast<int16_t>(y0),
          static_cast<int16_t>(std::max(0, x1 - x0)),
          static_cast<int16_t>(std::max(0, y1 - y0)), true};
}

void GrokRenderer::draw(const Frame& frame) const {
  drawEye(frame.leftEye, frame.centerX, frame.centerY, frame.blink);
  drawEye(frame.rightEye, frame.centerX, frame.centerY, frame.blink);
}
