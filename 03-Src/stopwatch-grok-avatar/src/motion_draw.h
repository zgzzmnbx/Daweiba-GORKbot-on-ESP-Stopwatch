// SPDX-License-Identifier: AGPL-3.0-only
#pragma once
#include "motion_scene.h"
#include "grok_renderer.h"

class MotionDraw {
 public:
  GrokRenderer::Bounds bounds(const MotionPose& pose);
  void draw(const MotionPose& pose);
 private:
  void paint(const MotionPose& pose,bool measuring);
};
