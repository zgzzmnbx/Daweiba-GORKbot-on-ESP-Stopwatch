// SPDX-License-Identifier: AGPL-3.0-or-later

#include <Arduino.h>
#include <M5IOE1.h>
#include <M5Unified.h>
#include <Preferences.h>
#include <cstring>

#include "avatar_engine.h"
#include "ble_control.h"
#include "audio_probe.h"

namespace {

constexpr uint8_t kIoeAddress = 0x4F;
constexpr uint8_t kVibrationPwmRegister = 0x1B;
constexpr uint8_t kDefaultBrightness = 150;
constexpr uint8_t kMinimumBrightness = 30;
constexpr uint8_t kBrightnessStep = 15;
constexpr uint32_t kIoeBusFrequency = M5IOE1_I2C_FREQ_100K;
constexpr uint32_t kDiagnosticRefreshIntervalMs = 100;
constexpr uint32_t kBatteryRefreshIntervalMs = 5000;
constexpr uint32_t kImuInteractionIntervalMs = 20;
constexpr uint32_t kShakeReleaseDelayMs = 650;
constexpr uint32_t kShakeSequenceTimeoutMs = 1500;
constexpr uint32_t kShakeMaximumSwingGapMs = 480;
constexpr uint32_t kShakeMinimumSwingGapMs = 90;
constexpr float kStrongShakeAxisDelta = 0.32f;
constexpr float kStrongShakeJerk = 0.50f;
constexpr uint8_t kRequiredShakeSwings = 4;
constexpr uint16_t kImuCalibrationSamples = 30;
constexpr int16_t kGestureDirectionLockPx = 12;
constexpr int16_t kGestureCommitPx = 52;
constexpr uint16_t kSwipeTransitionMs = 160;
constexpr char kBleEnabledKey[] = "ble";
constexpr char kBleBoundKey[] = "ble_bound";
constexpr char kBlePeerKey[] = "ble_peer";
constexpr uint8_t kBubbleMaxBytes = 72;
constexpr uint8_t kBubbleMaxCharacters = 24;
constexpr uint32_t kTextTransferTimeoutMs = 5000;

struct TextTransfer {
  uint8_t id = 0;
  uint8_t expected = 0;
  uint8_t received = 0;
  uint8_t nextChunk = 0;
  uint32_t updatedAtMs = 0;
  uint8_t data[kBubbleMaxBytes] = {};
};

enum class GestureAxis : uint8_t { None, Horizontal, Vertical };
enum class PanelPage : uint8_t { Settings, Hardware, Bluetooth, Audio };

M5IOE1 ioe;
AvatarEngine avatar;
Preferences settings;
BLEControl bleControl;
AudioProbe audioProbe(bleControl);
TextTransfer textTransfer;
bool vibrationReady = false;
bool settingsReady = false;
bool menuOpen = false;
bool menuToggleLatched = false;
bool debugMode = false;
bool clearBleBindingConfirm = false;
PanelPage panelPage = PanelPage::Settings;
uint32_t vibrationStopsAtMs = 0;
uint32_t lastDiagnosticRefreshMs = 0;
uint32_t lastBatteryRefreshMs = 0;
uint32_t lastImuInteractionMs = 0;
uint32_t shakeQuietStartedMs = 0;
uint16_t imuCalibrationCount = 0;
float filteredAccelX = 0.0f;
float filteredAccelY = 0.0f;
float neutralAccelX = 0.0f;
float neutralAccelY = 0.0f;
float previousAccelX = 0.0f;
float previousAccelY = 0.0f;
float previousAccelZ = 0.0f;
float shakeEnergy = 0.0f;
bool shakeReactionActive = false;
uint8_t shakeSwingCount = 0;
int8_t previousShakeDirection = 0;
uint32_t shakeSequenceStartedMs = 0;
uint32_t lastStrongShakeMs = 0;
String lastDiagnosticEvent = "Waiting for input";
String serialCommand;
uint8_t brightness = kDefaultBrightness;
GestureAxis gestureAxis = GestureAxis::None;
bool gestureCommitted = false;

bool reached(uint32_t now, uint32_t deadline) {
  return deadline != 0 && static_cast<int32_t>(now - deadline) >= 0;
}

void resetShakeSequence() {
  shakeSwingCount = 0;
  previousShakeDirection = 0;
  shakeSequenceStartedMs = 0;
  lastStrongShakeMs = 0;
}

void setFont() {
  M5.Display.setFont(&fonts::efontCN_16);
  M5.Display.setTextSize(1);
  M5.Display.setTextDatum(top_left);
}

void drawDiagnosticLine(int y, const String& label, const String& value,
                        uint16_t color = TFT_WHITE) {
  M5.Display.fillRect(46, y, 374, 22, TFT_BLACK);
  M5.Display.setTextColor(TFT_DARKGREY, TFT_BLACK);
  M5.Display.drawString(label, 46, y);
  M5.Display.setTextColor(color, TFT_BLACK);
  M5.Display.drawString(value, 156, y);
}

void drawPanelFrame(const char* title) {
  M5.Display.fillScreen(TFT_BLACK);
  const int cx = M5.Display.width() / 2;
  const int cy = M5.Display.height() / 2;
  M5.Display.drawCircle(cx, cy, min(cx, cy) - 3, TFT_DARKGREY);
  M5.Display.drawCircle(cx, cy, min(cx, cy) - 12, TFT_NAVY);
  setFont();
  M5.Display.setTextDatum(top_center);
  M5.Display.setTextColor(TFT_CYAN, TFT_BLACK);
  M5.Display.drawString(title, cx, 45);
  M5.Display.setTextColor(TFT_DARKGREY, TFT_BLACK);
  M5.Display.drawString("Hold A+B to return", cx, 72);
  M5.Display.setTextDatum(top_left);
}

void drawPanelButton(int x, int y, int width, const char* label) {
  M5.Display.fillRoundRect(x, y, width, 36, 8, TFT_DARKGREY);
  M5.Display.setTextColor(TFT_WHITE, TFT_DARKGREY);
  M5.Display.setTextDatum(middle_center);
  M5.Display.drawString(label, x + width / 2, y + 18);
  M5.Display.setTextDatum(top_left);
}

void drawBatteryLine() {
  const int voltage = M5.Power.getBatteryVoltage();
  const int level = M5.Power.getBatteryLevel();
  const bool valid = voltage > 2500 && voltage < 4600 && level >= 0 && level <= 100;
  const String value = valid
                           ? String(level) + "%  " + String(voltage / 1000.0f, 2) + "V"
                           : "--";
  drawDiagnosticLine(128, "Battery", value, valid ? TFT_GREEN : TFT_YELLOW);
  lastBatteryRefreshMs = millis();
}

void drawBrightnessControls() {
  drawDiagnosticLine(190, "Brightness",
                     String(brightness * 100 / 255) + "%", TFT_WHITE);
  drawPanelButton(250, 184, 60, "-");
  drawPanelButton(325, 184, 60, "+");
}

void drawDebugControls() {
  drawDiagnosticLine(254, "Debug mode", debugMode ? "ON" : "OFF", TFT_WHITE);
  drawPanelButton(270, 248, 110, debugMode ? "ON" : "OFF");
}

void drawSettingsFrame() {
  drawPanelFrame("Settings");
  drawBatteryLine();
  drawBrightnessControls();
  drawDebugControls();
  drawPanelButton(123, 300, 220, "Bluetooth");
  drawPanelButton(123, 352, 220, "Hardware Check");
  drawPanelButton(170, 404, 126, "Audio test");
}

void drawBluetoothFrame() {
  drawPanelFrame("Bluetooth");
  const uint32_t nowMs = millis();
  drawDiagnosticLine(112, "Control", bleControl.enabled() ? "ON" : "OFF",
                     bleControl.enabled() ? TFT_GREEN : TFT_DARKGREY);
  const char* link = !bleControl.enabled()
                         ? "disabled"
                         : (bleControl.connected() && bleControl.authorized()
                                ? "connected"
                                : (bleControl.connected() ? "pairing" : "waiting"));
  drawDiagnosticLine(146, "Link", link,
                     bleControl.connected() && bleControl.authorized()
                         ? TFT_GREEN
                         : TFT_YELLOW);
  const uint16_t pairSeconds = bleControl.pairingSecondsRemaining(nowMs);
  drawDiagnosticLine(180, "Pair window",
                     pairSeconds > 0 ? String(pairSeconds) + "s" : "closed",
                     pairSeconds > 0 ? TFT_CYAN : TFT_DARKGREY);
  drawDiagnosticLine(214, "Binding", bleControl.hasBoundPeer() ? "saved" : "none",
                     bleControl.hasBoundPeer() ? TFT_GREEN : TFT_YELLOW);
  drawDiagnosticLine(248, "Security",
                     bleControl.enabled() ? "SC + encrypted GATT" : "disabled",
                     bleControl.enabled() ? TFT_LIGHTGREY : TFT_DARKGREY);

  drawPanelButton(70, 286, 130, bleControl.enabled() ? "BLE OFF" : "BLE ON");
  drawPanelButton(220, 286, 130,
                  bleControl.hasBoundPeer()
                      ? "Bound"
                      : (pairSeconds > 0 ? "Pairing" : "Pair"));
  drawPanelButton(123, 340, 220,
                  clearBleBindingConfirm ? "Tap again to clear" : "Clear binding");
  drawPanelButton(170, 396, 126, "Back");
}

void drawDiagnosticFrame() {
  drawPanelFrame("Hardware Check");
  const int cx = M5.Display.width() / 2;
  drawDiagnosticLine(112, "Display",
                     String(M5.Display.width()) + " x " + String(M5.Display.height()),
                     TFT_GREEN);
  drawDiagnosticLine(146, "IMU", "initializing...");
  drawDiagnosticLine(180, "Touch", M5.Touch.isEnabled() ? "enabled" : "not detected");
  drawDiagnosticLine(214, "Vibration", vibrationReady ? "ready" : "not detected");
  drawDiagnosticLine(264, "Last event", lastDiagnosticEvent, TFT_YELLOW);

  M5.Display.setTextDatum(top_center);
  M5.Display.setTextColor(TFT_LIGHTGREY, TFT_BLACK);
  M5.Display.drawString("A: vibrate", cx, 348);
  M5.Display.drawString("B: redraw", cx, 378);
  M5.Display.setTextDatum(top_left);
  drawPanelButton(170, 396, 126, "Back");
}

void setDiagnosticEvent(const String& event) {
  lastDiagnosticEvent = event;
  drawDiagnosticLine(264, "Last event", lastDiagnosticEvent, TFT_YELLOW);
  Serial.println(event);
}

void adjustBrightness(int direction) {
  const int next = std::max<int>(kMinimumBrightness,
                                 std::min<int>(255, brightness + direction * kBrightnessStep));
  if (next == brightness) return;
  brightness = static_cast<uint8_t>(next);
  M5.Display.setBrightness(brightness);
  if (settingsReady) settings.putUChar("brightness", brightness);
  drawBrightnessControls();
  Serial.printf("Brightness: %u\n", brightness);
}

void toggleDebugMode() {
  debugMode = !debugMode;
  avatar.setDebugLabelEnabled(debugMode);
  if (settingsReady) settings.putBool("debug", debugMode);
  drawDebugControls();
  Serial.printf("Debug mode: %s\n", debugMode ? "on" : "off");
}

void stopVibration() {
  if (!vibrationReady) return;
  const uint8_t pwmData[2] = {0, 0x80};
  M5.In_I2C.writeRegister(kIoeAddress, kVibrationPwmRegister, pwmData,
                          sizeof(pwmData), kIoeBusFrequency);
  vibrationStopsAtMs = 0;
}

void startVibration(uint8_t strength = 160, uint16_t durationMs = 45) {
  if (!vibrationReady) return;
  const uint16_t duty12 =
      static_cast<uint16_t>(strength) * 0x0FFF / 0xFF;
  const uint8_t pwmData[2] = {
      static_cast<uint8_t>(duty12 & 0xFF),
      static_cast<uint8_t>(0x80 | ((duty12 >> 8) & 0x0F)),
  };
  if (!M5.In_I2C.writeRegister(kIoeAddress, kVibrationPwmRegister, pwmData,
                               sizeof(pwmData), kIoeBusFrequency)) {
    Serial.println("Vibration PWM write failed");
    return;
  }
  vibrationStopsAtMs = millis() + durationMs;
}

void updateVibration(uint32_t nowMs) {
  if (reached(nowMs, vibrationStopsAtMs)) stopVibration();
}

void setupVibration() {
  const m5ioe1_err_t error =
      ioe.begin(&M5.In_I2C, kIoeAddress, M5IOE1_I2C_FREQ_100K);
  vibrationReady = error == M5IOE1_OK;
  if (vibrationReady) {
    ioe.setPwmFrequency(200);
    // Configure the PWM pin once through the verified driver. Runtime haptics
    // then need only one two-byte register write instead of a write/readback/
    // GPIO-mode sequence that can stall an animation frame.
    vibrationReady =
        ioe.setPwmDuty12bit(M5IOE1_PWM_CH1, 0, false, true) == M5IOE1_OK;
  }
}

void trigger(ExpressionId expression, uint32_t nowMs,
             uint16_t firstTransitionMs = 0) {
  avatar.show(expression, nowMs, true, firstTransitionMs);
  startVibration();
  Serial.printf("Expression: %s\n", avatar.activeName());
}

void handleProductTouch(uint32_t nowMs) {
  if (!M5.Touch.isEnabled()) return;
  const auto touch = M5.Touch.getDetail(0);

  if (touch.wasPressed()) {
    gestureAxis = GestureAxis::None;
    gestureCommitted = false;
  }

  if (touch.wasHold() && gestureAxis == GestureAxis::None &&
      !gestureCommitted) {
    gestureCommitted = true;
    avatar.releaseTouch();
    trigger(ExpressionId::Angry, nowMs);
    return;
  }

  if (touch.isPressed()) {
    const bool moving = touch.isFlicking() || touch.isDragging();
    const int deltaX = moving ? touch.distanceX() : 0;
    const int deltaY = moving ? touch.distanceY() : 0;

    if (gestureAxis == GestureAxis::None &&
        std::max(abs(deltaX), abs(deltaY)) >= kGestureDirectionLockPx) {
      gestureAxis = abs(deltaX) >= abs(deltaY) ? GestureAxis::Horizontal
                                               : GestureAxis::Vertical;
    }

    if (gestureAxis == GestureAxis::Horizontal) {
      avatar.releaseTouch();
      const int8_t direction = deltaX > 0 ? -1 : 1;
      avatar.setSwipeOffset(deltaX, 0.0f,
                            gestureCommitted ? 0 : direction);
      if (!gestureCommitted && abs(deltaX) >= kGestureCommitPx) {
        avatar.commitSwipe(direction, nowMs, kSwipeTransitionMs);
        gestureCommitted = true;
        startVibration(125, 35);
        Serial.printf("Swipe commit: %s dx=%d\n", avatar.activeName(),
                      deltaX);
      }
      return;
    }

    if (gestureAxis == GestureAxis::Vertical) {
      avatar.releaseTouch();
      avatar.setSwipeOffset(0.0f, deltaY, 0);
      if (!gestureCommitted && abs(deltaY) >= kGestureCommitPx) {
        trigger(deltaY > 0 ? ExpressionId::Sleepy
                           : ExpressionId::Surprised,
                nowMs, kSwipeTransitionMs);
        gestureCommitted = true;
        Serial.printf("Vertical swipe commit: %s dy=%d\n",
                      avatar.activeName(), deltaY);
      }
      return;
    }

    if (!gestureCommitted) avatar.setTouchTarget(touch.x, touch.y);
  }

  if (touch.wasReleased()) {
    const bool consumed =
        gestureCommitted || gestureAxis != GestureAxis::None;
    avatar.releaseTouch();
    avatar.releaseSwipe();
    gestureAxis = GestureAxis::None;
    gestureCommitted = false;
    if (consumed) return;
  }

  if (gestureCommitted) {
    return;
  }

  if (touch.wasClicked()) {
    trigger(touch.getClickCount() >= 2 ? ExpressionId::Surprised
                                       : ExpressionId::Happy,
            nowMs);
  }
}

void handleImuInteraction(uint32_t nowMs) {
  if (nowMs - lastImuInteractionMs < kImuInteractionIntervalMs) return;
  lastImuInteractionMs = nowMs;
  if (!M5.Imu.update()) return;

  const auto imu = M5.Imu.getImuData();
  // The official StopWatch demo swaps the BMI270 sensor's raw X/Y values to
  // obtain screen coordinates. Keep all avatar interaction in that same
  // coordinate system: X is screen-left/right and Y is screen-up/down.
  const float screenAccelX = imu.accel.y;
  const float screenAccelY = imu.accel.x;
  const float screenAccelZ = imu.accel.z;
  const float screenGyroX = imu.gyro.y;
  const float screenGyroY = imu.gyro.x;
  constexpr float kFilterAmount = 0.32f;
  if (imuCalibrationCount == 0) {
    filteredAccelX = screenAccelX;
    filteredAccelY = screenAccelY;
    previousAccelX = screenAccelX;
    previousAccelY = screenAccelY;
    previousAccelZ = screenAccelZ;
  } else {
    filteredAccelX += (screenAccelX - filteredAccelX) * kFilterAmount;
    filteredAccelY += (screenAccelY - filteredAccelY) * kFilterAmount;
  }

  if (imuCalibrationCount < kImuCalibrationSamples) {
    neutralAccelX += screenAccelX / kImuCalibrationSamples;
    neutralAccelY += screenAccelY / kImuCalibrationSamples;
    ++imuCalibrationCount;
    if (imuCalibrationCount == kImuCalibrationSamples) {
      Serial.printf("IMU interaction ready: neutral x=%.2f y=%.2f\n",
                    neutralAccelX, neutralAccelY);
    }
  } else {
    // Roughly 0.28 g of tilt reaches full gaze travel. Neutral adaptation is
    // deliberately very slow so eyes keep looking in the chosen direction
    // while the user holds the device at an angle. Gyroscope feed-forward
    // makes the eyes lead during rotation; gravity keeps the final direction.
    neutralAccelX += (filteredAccelX - neutralAccelX) * 0.00015f;
    neutralAccelY += (filteredAccelY - neutralAccelY) * 0.00015f;
    avatar.setTiltTarget(-(filteredAccelX - neutralAccelX) / 0.28f,
                         -(filteredAccelY - neutralAccelY) / 0.28f,
                         -screenGyroY / 180.0f, screenGyroX / 180.0f);
  }

  const float deltaX = screenAccelX - previousAccelX;
  const float deltaY = screenAccelY - previousAccelY;
  const float deltaZ = screenAccelZ - previousAccelZ;
  const float jerk = fabsf(deltaX) + fabsf(deltaY) + fabsf(deltaZ);
  previousAccelX = screenAccelX;
  previousAccelY = screenAccelY;
  previousAccelZ = screenAccelZ;
  shakeEnergy = shakeEnergy * 0.72f + jerk * 0.28f;

  if (imuCalibrationCount < kImuCalibrationSamples) return;

  const float shakeIntensity = std::max(
      0.0f, std::min(1.0f, (shakeEnergy - 0.055f) / 0.48f));
  const float shakeDirectionX =
      std::max(-1.0f, std::min(1.0f, -deltaX / 0.28f));
  const float shakeDirectionY =
      std::max(-1.0f, std::min(1.0f, -deltaY / 0.28f));
  avatar.setShakeTarget(shakeDirectionX, shakeDirectionY, shakeIntensity);

  if (!shakeReactionActive) {
    if (shakeSwingCount > 0 &&
        (nowMs - shakeSequenceStartedMs > kShakeSequenceTimeoutMs ||
         nowMs - lastStrongShakeMs > kShakeMaximumSwingGapMs)) {
      resetShakeSequence();
    }

    if (shakeSwingCount == 0 && jerk >= kStrongShakeJerk) {
      if (fabsf(deltaX) >= kStrongShakeAxisDelta) {
        shakeSwingCount = 1;
        previousShakeDirection = deltaX >= 0.0f ? 1 : -1;
        shakeSequenceStartedMs = nowMs;
        lastStrongShakeMs = nowMs;
        Serial.printf("IMU horizontal swing 1/%u delta=%.2f\n",
                      kRequiredShakeSwings, deltaX);
      }
    } else if (shakeSwingCount > 0) {
      const int8_t direction = deltaX >= 0.0f ? 1 : -1;
      const uint32_t swingGapMs = nowMs - lastStrongShakeMs;
      const bool strongEnough = jerk >= kStrongShakeJerk &&
                                fabsf(deltaX) >= kStrongShakeAxisDelta;
      if (strongEnough && direction != previousShakeDirection &&
          swingGapMs >= kShakeMinimumSwingGapMs &&
          swingGapMs <= kShakeMaximumSwingGapMs) {
        ++shakeSwingCount;
        previousShakeDirection = direction;
        lastStrongShakeMs = nowMs;
        Serial.printf("IMU horizontal swing %u/%u delta=%.2f gap=%lums\n",
                      shakeSwingCount, kRequiredShakeSwings, deltaX,
                      static_cast<unsigned long>(swingGapMs));
      }
    }

    if (shakeSwingCount >= kRequiredShakeSwings) {
      shakeReactionActive = true;
      shakeQuietStartedMs = 0;
      resetShakeSequence();
      avatar.play(ExpressionId::Dizzy, nowMs,
                  AvatarEngine::PlaybackMode::Loop, false, 150);
      startVibration(190, 80);
      Serial.printf("IMU repeated horizontal shake -> DIZZY energy=%.2f\n",
                    shakeEnergy);
    }
    return;
  }

  if (shakeIntensity > 0.10f) {
    shakeQuietStartedMs = 0;
    return;
  }

  if (shakeQuietStartedMs == 0) {
    shakeQuietStartedMs = nowMs;
  } else if (nowMs - shakeQuietStartedMs >= kShakeReleaseDelayMs) {
    shakeReactionActive = false;
    shakeQuietStartedMs = 0;
    resetShakeSequence();
    if (avatar.activeExpression() == ExpressionId::Dizzy) {
      avatar.show(avatar.baseExpression(), nowMs, false, 260);
    }
    Serial.println("IMU shake settled -> BASE");
  }
}

bool dispatchExpressionCommand(const String& command, uint32_t nowMs,
                               const char* source, bool vibrate = true) {
  if (avatar.showFromCommand(command, nowMs)) {
    if (vibrate) startVibration();
    Serial.printf("Command accepted [%s]: %s\n", source, avatar.activeName());
    return true;
  }
  Serial.printf("Unknown command [%s]: %s\n", source, command.c_str());
  return false;
}

void persistBleBindingIfNeeded() {
  uint8_t peer[BLEControl::kPeerAddressLength] = {};
  if (!bleControl.takeNewBinding(peer, sizeof(peer))) return;
  if (settingsReady) {
    settings.putBytes(kBlePeerKey, peer, sizeof(peer));
    settings.putBool(kBleBoundKey, true);
  }
  Serial.println("BLE controller bound after encrypted pairing");
}

bool validBubbleUtf8(const uint8_t* data, uint8_t length) {
  uint8_t characters = 0;
  for (uint8_t index = 0; index < length;) {
    const uint8_t lead = data[index];
    uint8_t width = 0;
    if (lead >= 0x20 && lead <= 0x7E) {
      width = 1;
    } else if (lead >= 0xC2 && lead <= 0xDF) {
      width = 2;
    } else if (lead >= 0xE0 && lead <= 0xEF) {
      width = 3;
    } else {
      return false;
    }
    if (index + width > length) return false;
    for (uint8_t offset = 1; offset < width; ++offset) {
      if ((data[index + offset] & 0xC0) != 0x80) return false;
    }
    if (width == 3 &&
        ((lead == 0xE0 && data[index + 1] < 0xA0) ||
         (lead == 0xED && data[index + 1] >= 0xA0))) {
      return false;
    }
    index += width;
    if (++characters > kBubbleMaxCharacters) return false;
  }
  return characters != 0;
}

void handleBleTextPacket(const uint8_t* packet, uint8_t length,
                         uint32_t nowMs, char* status, size_t statusCapacity) {
  if (textTransfer.expected != 0 &&
      nowMs - textTransfer.updatedAtMs > kTextTransferTimeoutMs) {
    textTransfer = {};
  }
  const uint8_t operation = packet[0];
  if (operation == BLEControl::kTextClear && length == 1) {
    textTransfer = {};
    avatar.clearBubbleText();
    snprintf(status, statusCapacity, "OK:CLEAR");
    return;
  }
  if (operation == BLEControl::kTextBegin && length == 3 && packet[1] != 0 &&
      packet[2] > 0 && packet[2] <= kBubbleMaxBytes) {
    textTransfer = {};
    textTransfer.id = packet[1];
    textTransfer.expected = packet[2];
    textTransfer.updatedAtMs = nowMs;
    snprintf(status, statusCapacity, "OK:BEGIN:%u", packet[1]);
    return;
  }
  if (textTransfer.expected == 0 || length < 2 ||
      packet[1] != textTransfer.id) {
    snprintf(status, statusCapacity, "ERR:TEXT_STATE");
    return;
  }
  if (operation == BLEControl::kTextChunk && length >= 4 &&
      packet[2] == textTransfer.nextChunk &&
      textTransfer.received + length - 3 <= textTransfer.expected) {
    memcpy(textTransfer.data + textTransfer.received, packet + 3, length - 3);
    textTransfer.received += length - 3;
    textTransfer.updatedAtMs = nowMs;
    snprintf(status, statusCapacity, "OK:PART:%u:%u", packet[1], packet[2]);
    ++textTransfer.nextChunk;
    return;
  }
  if (operation == BLEControl::kTextCommit && length == 2 &&
      textTransfer.received == textTransfer.expected) {
    if (!validBubbleUtf8(textTransfer.data, textTransfer.expected)) {
      textTransfer = {};
      snprintf(status, statusCapacity, "ERR:TEXT_UTF8");
      return;
    }
    avatar.setBubbleText(reinterpret_cast<const char*>(textTransfer.data),
                         textTransfer.expected, nowMs);
    snprintf(status, statusCapacity, "OK:TEXT:%u", packet[1]);
    textTransfer = {};
    return;
  }
  textTransfer = {};
  snprintf(status, statusCapacity, "ERR:TEXT_SEQ");
}

void processBleCommands(uint32_t nowMs) {
  char command[BLEControl::kMaxCommandLength + 1] = {};
  uint16_t connectionId = 0;
  uint8_t payloadLength = 0;
  while (bleControl.takeCommand(command, sizeof(command), &connectionId,
                                &payloadLength)) {
    if (menuOpen) {
      textTransfer = {};
      bleControl.publishResult(connectionId, "ERR:BUSY");
      Serial.println("BLE command rejected: settings menu is open");
      continue;
    }

    if (payloadLength > 0 &&
        static_cast<uint8_t>(command[0]) >= BLEControl::kTextBegin) {
      char status[BLEControl::kMaxStatusLength + 1] = {};
      handleBleTextPacket(reinterpret_cast<const uint8_t*>(command),
                          payloadLength, nowMs, status, sizeof(status));
      bleControl.publishResult(connectionId, status);
      continue;
    }

    const bool accepted =
        dispatchExpressionCommand(String(command), nowMs, "BLE");
    if (accepted) {
      char status[BLEControl::kMaxStatusLength + 1] = {};
      snprintf(status, sizeof(status), "OK:%s", avatar.activeName());
      bleControl.publishResult(connectionId, status);
    } else {
      bleControl.publishResult(connectionId, "ERR:BAD_CMD");
    }
  }
}

void handleSerialCommands(uint32_t nowMs) {
  while (Serial.available() > 0) {
    const char character = static_cast<char>(Serial.read());
    if (character == '\n' || character == '\r') {
      if (serialCommand.length() == 0) continue;
      if (menuOpen) {
        Serial.println("USB command rejected: settings menu is open");
      } else {
        dispatchExpressionCommand(serialCommand, nowMs, "USB");
      }
      serialCommand = "";
    } else if (serialCommand.length() < 32) {
      serialCommand += character;
    }
  }
}

void refreshDiagnosticSensors() {
  if (M5.Imu.update()) {
    const auto imu = M5.Imu.getImuData();
    char values[64];
    snprintf(values, sizeof(values), "H %.2f  V %.2f  Z %.2f", imu.accel.y,
             imu.accel.x, imu.accel.z);
    drawDiagnosticLine(146, "IMU", values, TFT_GREEN);
  } else {
    drawDiagnosticLine(146, "IMU", "no data", TFT_RED);
  }

  if (M5.Touch.getCount() > 0) {
    const auto touch = M5.Touch.getDetail(0);
    drawDiagnosticLine(180, "Touch",
                       "x " + String(touch.x) + "  y " + String(touch.y),
                       TFT_GREEN);
  } else {
    drawDiagnosticLine(180, "Touch",
                       M5.Touch.isEnabled() ? "enabled" : "not detected",
                       M5.Touch.isEnabled() ? TFT_GREEN : TFT_RED);
  }
}

void setMenuOpen(bool enabled) {
  audioProbe.leave();
  menuOpen = enabled;
  stopVibration();
  if (menuOpen) {
    serialCommand = "";
    panelPage = PanelPage::Settings;
    drawSettingsFrame();
    Serial.println("Settings mode entered");
  } else {
    avatar.invalidate();
    Serial.println("Expression mode entered");
  }
}

void handleSettingsInput(uint32_t nowMs) {
  const auto touch = M5.Touch.getDetail(0);
  if (touch.wasPressed()) {
    if (touch.y >= 178 && touch.y < 225) {
      if (touch.x >= 245 && touch.x < 315) adjustBrightness(-1);
      if (touch.x >= 320 && touch.x < 390) adjustBrightness(1);
    } else if (touch.y >= 242 && touch.y < 290 &&
               touch.x >= 250 && touch.x < 390) {
      toggleDebugMode();
    } else if (touch.y >= 294 && touch.y < 340 &&
               touch.x >= 110 && touch.x < 356) {
      panelPage = PanelPage::Bluetooth;
      clearBleBindingConfirm = false;
      drawBluetoothFrame();
    } else if (touch.y >= 346 && touch.y < 394 &&
               touch.x >= 110 && touch.x < 356) {
      panelPage = PanelPage::Hardware;
      drawDiagnosticFrame();
    } else if (touch.y >= 400 && touch.y < 440 &&
               touch.x >= 160 && touch.x < 306) {
      panelPage = PanelPage::Audio;
      drawPanelFrame("BLE Audio v0.7.0-P0");
      drawPanelButton(170, 396, 126, "Back");
      audioProbe.enter();
      return;
    }
  }
  if (nowMs - lastBatteryRefreshMs >= kBatteryRefreshIntervalMs) {
    drawBatteryLine();
  }
}

void handleBluetoothInput(uint32_t nowMs) {
  const auto touch = M5.Touch.getDetail(0);
  if (!touch.wasPressed()) return;

  if (touch.y >= 390 && touch.y < 440 && touch.x >= 160 && touch.x < 306) {
    panelPage = PanelPage::Settings;
    clearBleBindingConfirm = false;
    drawSettingsFrame();
    return;
  }

  if (touch.y >= 280 && touch.y < 332 && touch.x >= 55 && touch.x < 205) {
    const bool nextEnabled = !bleControl.enabled();
    if (bleControl.setEnabled(nextEnabled, nowMs)) {
      if (settingsReady) settings.putBool(kBleEnabledKey, nextEnabled);
      clearBleBindingConfirm = false;
      Serial.printf("BLE control: %s\n", nextEnabled ? "on" : "off");
    } else {
      Serial.println("BLE control could not start; kept OFF");
    }
    drawBluetoothFrame();
    return;
  }

  if (touch.y >= 280 && touch.y < 332 && touch.x >= 210 && touch.x < 375) {
    if (!bleControl.hasBoundPeer()) {
      if (bleControl.openPairingWindow(nowMs)) {
        Serial.println("BLE pairing window opened for 120 seconds");
      } else {
        Serial.println("BLE pairing requires BLE control ON");
      }
    }
    drawBluetoothFrame();
    return;
  }

  if (touch.y >= 334 && touch.y < 384 && touch.x >= 110 && touch.x < 356) {
    if (bleControl.hasBoundPeer()) {
      if (clearBleBindingConfirm) {
        bleControl.clearBinding();
        if (settingsReady) {
          settings.putBool(kBleBoundKey, false);
          settings.remove(kBlePeerKey);
        }
        clearBleBindingConfirm = false;
        Serial.println("BLE binding cleared");
      } else {
        clearBleBindingConfirm = true;
        Serial.println("BLE binding clear awaiting second touch");
      }
      drawBluetoothFrame();
    }
  }
}

void handleDiagnosticInput(uint32_t nowMs) {
  if (M5.BtnA.wasClicked()) {
    setDiagnosticEvent("Button A clicked");
    startVibration(180, 70);
  }
  if (M5.BtnB.wasClicked()) {
    lastDiagnosticEvent = "Button B clicked";
    drawDiagnosticFrame();
    Serial.println(lastDiagnosticEvent);
  }

  const auto touch = M5.Touch.getDetail(0);
  if (touch.wasPressed()) {
    if (touch.y >= 390 && touch.y < 440 &&
        touch.x >= 160 && touch.x < 306) {
      panelPage = PanelPage::Settings;
      drawSettingsFrame();
      return;
    }
    setDiagnosticEvent("Touch " + String(touch.x) + "," + String(touch.y));
  }

  if (nowMs - lastDiagnosticRefreshMs >= kDiagnosticRefreshIntervalMs) {
    lastDiagnosticRefreshMs = nowMs;
    refreshDiagnosticSensors();
  }
}

void handleMenuToggle() {
  const bool bothHeld = M5.BtnA.pressedFor(1000) && M5.BtnB.pressedFor(1000);
  if (bothHeld && !menuToggleLatched) {
    menuToggleLatched = true;
    setMenuOpen(!menuOpen);
  } else if (!M5.BtnA.isPressed() && !M5.BtnB.isPressed()) {
    menuToggleLatched = false;
  }
}

}  // namespace

void setup() {
  auto config = M5.config();
  config.serial_baudrate = 115200;
  M5.begin(config);
  // M5.begin configures the official pins/callbacks. Audio is not left active
  // at boot and is started only by the explicit diagnostic session/gesture.
  M5.Mic.end();
  M5.Speaker.end();
  Serial.begin(115200);

  M5.Display.setRotation(0);
  settingsReady = settings.begin("gorkbot", false);
  bool bleEnabled = false;
  bool bleBound = false;
  uint8_t blePeer[BLEControl::kPeerAddressLength] = {};
  if (settingsReady) {
    brightness = settings.getUChar("brightness", kDefaultBrightness);
    debugMode = settings.getBool("debug", false);
    bleEnabled = settings.getBool(kBleEnabledKey, false);
    bleBound = settings.getBool(kBleBoundKey, false);
    if (bleBound && settings.getBytes(kBlePeerKey, blePeer, sizeof(blePeer)) !=
                        sizeof(blePeer)) {
      bleBound = false;
      settings.putBool(kBleBoundKey, false);
    }
  }
  brightness = std::max<uint8_t>(kMinimumBrightness, brightness);
  M5.Display.setBrightness(brightness);
  M5.Touch.setHoldThresh(650);
  M5.Touch.setFlickThresh(10);
  setupVibration();

  if (!avatar.begin()) {
    M5.Display.fillScreen(TFT_BLACK);
    M5.Display.setTextColor(TFT_RED, TFT_BLACK);
    M5.Display.setTextDatum(middle_center);
    M5.Display.drawString("Avatar buffer failed", M5.Display.width() / 2,
                          M5.Display.height() / 2);
    Serial.println("Avatar sprite allocation failed");
  }
  avatar.setDebugLabelEnabled(debugMode);

  bleControl.setAudioProbe(&audioProbe);
  if (!bleControl.begin(bleEnabled, bleBound, blePeer)) {
    Serial.println("BLE control failed to initialize; kept OFF");
    if (settingsReady) settings.putBool(kBleEnabledKey, false);
  }

  Serial.println("Expression device started");
  Serial.println(
      "Commands: idle listening thinking happy excited curious confused "
      "angry surprised sad sleepy dizzy happy-work");
  Serial.println("Playback test: once|loop|pingpong <expression>");
  Serial.println("Hold A+B for settings, Bluetooth, and hardware diagnostics");
}

void loop() {
  M5.update();
  const uint32_t nowMs = millis();
  updateVibration(nowMs);
  handleMenuToggle();
  bleControl.update(nowMs);
  persistBleBindingIfNeeded();
  handleSerialCommands(nowMs);
  processBleCommands(nowMs);
  audioProbe.update(nowMs);

  if (menuOpen) {
    if (panelPage == PanelPage::Settings) {
      handleSettingsInput(nowMs);
    } else if (panelPage == PanelPage::Bluetooth) {
      handleBluetoothInput(nowMs);
    } else if (panelPage == PanelPage::Audio) {
      const auto touch = M5.Touch.getDetail(0);
      if (touch.wasPressed() && touch.y >= 390 && touch.y < 440 &&
          touch.x >= 160 && touch.x < 306) {
        audioProbe.leave();
        panelPage = PanelPage::Settings;
        drawSettingsFrame();
      }
    } else {
      handleDiagnosticInput(nowMs);
    }
  } else {
    if (M5.BtnA.wasClicked()) {
      avatar.previous(nowMs);
      startVibration(125, 35);
    }
    if (M5.BtnB.wasClicked()) {
      avatar.next(nowMs);
      startVibration(125, 35);
    }
    handleProductTouch(nowMs);
    handleImuInteraction(nowMs);
    avatar.update(nowMs);
  }

  // A short cooperative yield keeps input responsive without quantizing the
  // 60 fps renderer onto a coarse 5 ms loop cadence.
  delay(1);
}
