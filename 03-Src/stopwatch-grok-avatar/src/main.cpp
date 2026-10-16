// SPDX-License-Identifier: AGPL-3.0-or-later

#include <Arduino.h>
#include <M5Unified.h>
#include <Preferences.h>
#include <cstring>

#include "avatar_engine.h"
#include "ble_control.h"
#include "audio_probe.h"
#include "sound_control.h"
#include "speaker_output.h"
#include "network_control.h"
#include "network_setup.h"
#include "connection_announcements.h"
#include "connection_voice.h"
#include "watch_orientation.h"
#include <esp_heap_caps.h>

namespace {

constexpr uint8_t kDefaultBrightness = 150;
constexpr char kFirmwareVersion[] = "v0.11.11-dev";
constexpr uint8_t kMinimumBrightness = 30;
constexpr uint8_t kBrightnessStep = 15;
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
constexpr char kSoundVolumeKey[] = "sound_vol";
constexpr char kInvertedKey[] = "inverted";
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
enum class PanelPage : uint8_t { Settings, Hardware, Bluetooth, Sound, Audio, Network };

AvatarEngine avatar;
Preferences settings;
BLEControl bleControl;
AudioProbe audioProbe(bleControl);
NetworkControl networkControl(bleControl);
bool forgetNetworkConfirm=false;
SoundControl soundControl(bleControl);
ConnectionAnnouncements connectionAnnouncements;
ConnectionAnnouncements::Cue activeConnectionCue = ConnectionAnnouncements::None;
uint32_t connectionSoundStopEpoch = 0;
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
char serialLine[gorksetup::MaxLine]{};
size_t serialUsed=0;
bool serialOverflow=false;
uint32_t serialLastByte=0;
uint8_t brightness = kDefaultBrightness;
uint8_t pendingSoundVolume = 20;
uint32_t soundVolumeChangedAtMs = 0;
bool soundVolumePending = false;
gorkorientation::Direction orientation;
gorkorientation::TripleB orientationGesture;
uint32_t orientationHintUntil = 0, orientationTouchUntil = 0;
bool orientationTouchNeedsRelease = false, orientationSaveFailed = false;
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

void drawOrientationControl() {
  drawDiagnosticLine(154, "倒挂模式", "", TFT_WHITE);
  M5.Display.fillRoundRect(270, 150, 110, 28, 8, TFT_DARKGREY);
  M5.Display.setTextColor(TFT_WHITE, TFT_DARKGREY);
  M5.Display.setTextDatum(middle_center);
  M5.Display.drawString(orientation.inverted() ? "ON" : "OFF", 325, 164);
  M5.Display.setTextDatum(top_left);
}

void drawSettingsFrame() {
  drawPanelFrame("Settings");
  drawDiagnosticLine(102, "Firmware", kFirmwareVersion, TFT_LIGHTGREY);
  drawBatteryLine();
  drawOrientationControl();
  drawBrightnessControls();
  drawDebugControls();
  drawPanelButton(75, 292, 140, "Sound");
  drawPanelButton(245,292,140,"Network");
  drawPanelButton(123, 334, 220, "Bluetooth");
  drawPanelButton(123, 376, 220, "Hardware Check");
  drawPanelButton(170, 418, 126, "Audio test");
}

void drawSoundFrame() {
  drawPanelFrame("Sound");
  drawDiagnosticLine(150,"Volume",String(soundControl.volume())+"%",TFT_WHITE);
  drawDiagnosticLine(174,"Speaker",soundControl.hardwareStatus(),
                     String(soundControl.hardwareStatus())=="playing"?TFT_GREEN:TFT_WHITE);
  drawPanelButton(90,206,80,"-"); drawPanelButton(193,206,80,"Test"); drawPanelButton(296,206,80,"+");
  drawPanelButton(115,270,105,soundControl.volume()?"Mute":"Muted");
  drawPanelButton(246,270,105,"Stop");
  drawPanelButton(170,396,126,"Back");
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
  M5.Power.setVibration(0);
  vibrationStopsAtMs = 0;
}

void startVibration(uint8_t strength = 160, uint16_t durationMs = 45) {
  if (!vibrationReady) return;
  M5.Power.setVibration(strength);
  vibrationStopsAtMs = millis() + durationMs;
}

void updateVibration(uint32_t nowMs) {
  if (reached(nowMs, vibrationStopsAtMs)) stopVibration();
}

void setupVibration() {
  // Keep one owner for the shared IO expander. A second M5IOE1 driver instance
  // can race the codec-power and PA pins used by M5Unified's speaker callback.
  vibrationReady = M5.getBoard() == m5::board_t::board_M5StopWatch;
  if (vibrationReady) M5.Power.setVibration(0);
}

void trigger(ExpressionId expression, uint32_t nowMs,
             uint16_t firstTransitionMs = 0) {
  avatar.show(expression, nowMs, true, firstTransitionMs);
  startVibration();
  Serial.printf("Expression: %s\n", avatar.activeName());
}

bool orientationTouchBlocked(uint32_t nowMs) {
  if (orientationTouchNeedsRelease) {
    if (M5.Touch.getDetail(0).isPressed()) return true;
    orientationTouchNeedsRelease = false;
  }
  return orientationTouchUntil && !reached(nowMs, orientationTouchUntil);
}

bool setInverted(bool inverted, uint32_t nowMs) {
  if (orientation.inverted() == inverted) return true;
  if (!settingsReady || settings.putBool(kInvertedKey, inverted) != 1) {
    orientationSaveFailed = true; orientationHintUntil = nowMs + 1200; avatar.invalidate();
    Serial.println("Orientation preference could not be saved");
    return false;
  }
  orientationSaveFailed = false;
  orientation.setInverted(inverted);
  M5.Display.setRotation(orientation.rotation());
  // M5Unified Touch.update already uses Display.convertRawXY. Never invert
  // touch coordinates again; just ignore the held finger across this change.
  orientationTouchNeedsRelease = true;
  orientationTouchUntil = nowMs + 200;
  gestureAxis = GestureAxis::None; gestureCommitted = false;
  avatar.releaseTouch(); avatar.releaseSwipe();
  avatar.setTiltTarget(0, 0); avatar.setShakeTarget(0, 0, 0);
  imuCalibrationCount = 0; neutralAccelX = neutralAccelY = 0;
  filteredAccelX = filteredAccelY = 0;
  previousAccelX = previousAccelY = previousAccelZ = 0;
  if (shakeReactionActive) avatar.show(avatar.baseExpression(), nowMs, false);
  shakeEnergy = 0; shakeReactionActive = false; shakeQuietStartedMs = 0;
  resetShakeSequence();
  orientationGesture.reset(nowMs);
  M5.Display.fillScreen(TFT_BLACK); avatar.invalidate();
  orientationHintUntil = menuOpen ? 0 : nowMs + 1200;
  startVibration(125, 55);
  if (menuOpen) drawSettingsFrame();
  Serial.println(inverted ? "Orientation: inverted" : "Orientation: normal");
  return true;
}

bool orientationIdle(uint32_t nowMs) {
  return !menuOpen && !menuToggleLatched && !M5.BtnA.isPressed() &&
      !M5.BtnA.wasClicked() && !M5.BtnB.pressedFor(500) &&
      !M5.Touch.getDetail(0).isPressed() && !orientationTouchBlocked(nowMs) &&
      audioProbe.orientationIdle(nowMs) && !soundControl.isPlaying() &&
      avatar.orientationIdle();
}

void handleProductTouch(uint32_t nowMs) {
  if (!M5.Touch.isEnabled() || orientationTouchBlocked(nowMs)) return;
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
  const float screenAccelX = orientation.axis(imu.accel.y);
  const float screenAccelY = orientation.axis(imu.accel.x);
  const float screenAccelZ = imu.accel.z;
  const float screenGyroX = orientation.axis(imu.gyro.y);
  const float screenGyroY = orientation.axis(imu.gyro.x);
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

void formatBleExpressionReceipt(const AvatarEngine& avatar, char* status,
                                size_t capacity) {
  if (!capacity) return;
  snprintf(status, capacity, "OK:%s", avatar.activeProtocolName());
  for (char* cursor = status; *cursor; ++cursor) {
    if (*cursor >= 'a' && *cursor <= 'z') *cursor -= 'a' - 'A';
  }
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
      formatBleExpressionReceipt(avatar, status, sizeof(status));
      bleControl.publishResult(connectionId, status);
    } else {
      bleControl.publishResult(connectionId, "ERR:BAD_CMD");
    }
  }
}

void handleSerialCommands(uint32_t nowMs) {
  if(serialUsed && nowMs-serialLastByte>2000){memset(serialLine,0,sizeof(serialLine));serialUsed=0;serialOverflow=false;}
  while (Serial.available() > 0) {
    const char character = static_cast<char>(Serial.read());
    serialLastByte=nowMs;
    if (character == '\n' || character == '\r') {
      if (!serialUsed && !serialOverflow) continue;
      if(serialOverflow){Serial.println("USB command rejected: too long");}
      else if(serialUsed>=5 && !memcmp(serialLine,"GWUSB",5)){
        gorksetup::Packet packet;
        if(!gorksetup::parse(serialLine,serialUsed,packet)){
          Serial.printf("GWUSB1 %08lx {\"error\":\"invalid request\"}\n",static_cast<unsigned long>(packet.request));
        }else if(packet.op==gorksetup::Op::Set){
          const bool idle=!audioProbe.busy()&&!soundControl.isPlaying();
          const bool saved=idle&&networkControl.configureUsb(packet.data,packet.size);
          Serial.printf("GWUSB1 %08lx {\"accepted\":%s}\n",static_cast<unsigned long>(packet.request),saved?"true":"false");
        }else{
          const auto status=networkControl.publicStatus();
          Serial.printf("GWUSB1 %08lx {\"device\":\"StopWatch-Gork\",\"protocol\":1,\"firmware\":\"%s\",\"network\":%s}\n",static_cast<unsigned long>(packet.request),kFirmwareVersion,status.c_str());
        }
        gorksetup::wipe(&packet,sizeof(packet));
      }else if(serialUsed>32){Serial.println("USB command rejected: too long");}
      else if (menuOpen) {
        Serial.println("USB command rejected: settings menu is open");
      } else {
        dispatchExpressionCommand(String(serialLine), nowMs, "USB");
      }
      memset(serialLine,0,sizeof(serialLine));serialUsed=0;serialOverflow=false;
    } else if (serialUsed+1 < sizeof(serialLine)) {
      serialLine[serialUsed++]=character;
    } else {
      serialOverflow=true;
    }
  }
}

void renderAvatarWithAudioHint(uint32_t nowMs) {
  static uint32_t lastAudioHint=0;
  static bool hintVisible=false;
  static uint8_t lastHintKind=0;
  const uint8_t left=audioProbe.recordSecondsLeft(nowMs);
  const bool preparing=audioProbe.preparing(nowMs);
  const bool directionHint=orientationHintUntil&&!reached(nowMs,orientationHintUntil);
  const bool showHint=left||preparing||audioProbe.busy()||directionHint;
  const uint8_t hintKind=left?1:preparing?2:audioProbe.busy()?3:4;
  // Restore the avatar once when an actual hint ends. Idle frames must not
  // paint a blank black rectangle over the avatar's partial refresh.
  if(!showHint&&hintVisible){avatar.invalidate();hintVisible=false;}
  avatar.update(nowMs);
  if(!showHint||(hintVisible&&hintKind==lastHintKind&&nowMs-lastAudioHint<200))return;
  lastAudioHint=nowMs;
  lastHintKind=hintKind;
  char hint[72];
  if(left)snprintf(hint,sizeof(hint),"REC %us / click A to send / B cancel",left);
  else if(preparing)snprintf(hint,sizeof(hint),"Preparing / click A to cancel");
  else if(!audioProbe.busy()&&directionHint)snprintf(hint,sizeof(hint),orientationSaveFailed?"Orientation save failed":orientation.inverted()?"Inverted 180 deg":"Normal orientation");
  else snprintf(hint,sizeof(hint),"%.54s",audioProbe.message());
  M5.Display.setTextDatum(middle_center);
  M5.Display.setTextColor(left?TFT_RED:TFT_LIGHTGREY,TFT_BLACK);
  M5.Display.fillRect(60,420,346,20,TFT_BLACK);
  M5.Display.drawString(hint,233,430);
  M5.Display.setTextDatum(top_left);
  hintVisible=true;
}

void refreshDiagnosticSensors() {
  if (M5.Imu.update()) {
    const auto imu = M5.Imu.getImuData();
    char values[64];
    snprintf(values, sizeof(values), "H %.2f  V %.2f  Z %.2f", orientation.axis(imu.accel.y),
             orientation.axis(imu.accel.x), imu.accel.z);
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
  orientationGesture.reset(millis()); orientationHintUntil = 0;
  menuOpen = enabled;
  stopVibration();
  if (menuOpen) {
    memset(serialLine,0,sizeof(serialLine));serialUsed=0;serialOverflow=false;
    panelPage = PanelPage::Settings;
    drawSettingsFrame();
    Serial.println("Settings mode entered");
  } else {
    audioProbe.enter(false);
    avatar.invalidate();
    Serial.println("Expression mode entered");
  }
}

void drawNetworkFrame(){
  drawPanelFrame("Network");
  drawDiagnosticLine(102,"State",networkControl.state(),TFT_WHITE);
  drawDiagnosticLine(140,"IP",networkControl.address(),TFT_LIGHTGREY);
  drawDiagnosticLine(178,"Power source",networkControl.source(),TFT_YELLOW);
  const char* modes[]={"Auto WiFi first","BLE only","WiFi only"};
  const char* power[]={"Power: Auto (unknown/eco)","Power: Performance","Power: Eco"};
  drawPanelButton(70,212,326,modes[networkControl.policy()]);
  drawPanelButton(70,256,326,power[networkControl.power()]);
  drawPanelButton(105,300,256,"Reconnect");
  drawPanelButton(105,344,256,forgetNetworkConfirm?"Confirm forget hotspot":"Forget hotspot");
  drawPanelButton(170,396,126,"Back");
}
void handleNetworkInput(uint32_t now){
  const auto touch=M5.Touch.getDetail(0);
  if(touch.wasPressed()){
    if(touch.y>=212&&touch.y<254)networkControl.options((networkControl.policy()+1)%3,networkControl.power());
    else if(touch.y>=256&&touch.y<298)networkControl.options(networkControl.policy(),(networkControl.power()+1)%3);
    else if(touch.y>=300&&touch.y<342)networkControl.reconnect();
    else if(touch.y>=344&&touch.y<386){if(forgetNetworkConfirm){networkControl.forget();forgetNetworkConfirm=false;}else forgetNetworkConfirm=true;}
    else if(touch.y>=396&&touch.y<438){panelPage=PanelPage::Settings;drawSettingsFrame();return;}
    drawNetworkFrame();
  }
  static uint32_t last=0;if(now-last>=1000){last=now;drawNetworkFrame();}
}

void processNetworkCommands(uint32_t now){
  auto* p=networkControl.take();if(!p)return;
  if(!networkControl.ready()||p->session==0||p->session!=networkControl.session()){heap_caps_free(p);return;}
  char result[80]="OK";bool failed=false;
  if(p->kind==0){auto status=networkControl.publicStatus();networkControl.reply(*p,status.c_str());}
  else if(p->kind==6){
    if(p->size==0){auto status=networkControl.publicStatus();networkControl.reply(*p,status.c_str());}
    else if(p->data[0]==1&&p->size==3){if(audioProbe.busy()){networkControl.reply(*p,"audio busy",true);}else{bool ok=networkControl.options(p->data[1],p->data[2]);networkControl.reply(*p,ok?"{}":"invalid options",!ok);}}
    else if(p->data[0]==2&&p->size==1){audioProbe.cancelLocal();networkControl.reply(*p,"{}");}
    else if(p->data[0]==3&&p->size==2){networkControl.delegate(p->data[1]!=0,true);networkControl.reply(*p,"{}");}
    else networkControl.reply(*p,"invalid control",true);
  }
  else if(menuOpen){networkControl.reply(*p,"settings open",true);}
  else if(p->kind==1&&p->size>0&&p->size<=32&&!memchr(p->data,0,p->size)){
    char command[33]{};memcpy(command,p->data,p->size);bool ok=dispatchExpressionCommand(String(command),now,"WiFi");networkControl.reply(*p,ok?"OK:APPLIED":"invalid expression",!ok);
  }
  else if(p->kind==2&&p->size<=72&&p->size&&validBubbleUtf8(p->data,p->size)){
    avatar.setBubbleText(reinterpret_cast<const char*>(p->data),p->size,now);networkControl.reply(*p,"OK:TEXT");
  }
  else if(p->kind==3&&p->size==0){avatar.clearBubbleText();networkControl.reply(*p,"OK:CLEAR");}
  else if(p->kind==4&&p->size==2){
    if(p->data[0]==0){soundControl.stopNow();networkControl.reply(*p,"OK:STOPPED");}
    else if(p->data[0]==1&&!audioProbe.busy()){bool ok=soundControl.preview(p->data[1]);networkControl.reply(*p,ok?"OK:ACCEPTED":"sound unavailable",!ok);}
    else if(p->data[0]==2){soundControl.setLocalVolume(p->data[1]);networkControl.reply(*p,"OK:VOLUME");}
    else networkControl.reply(*p,"audio busy",true);
  }
  else if(p->kind==5){audioProbe.networkInput(p->data,p->size,networkControl.link());networkControl.reply(*p,"accepted");}
  else networkControl.reply(*p,"invalid request",true);
  memset(p,0,sizeof(*p));heap_caps_free(p);
}

void handleSettingsInput(uint32_t nowMs) {
  if (orientationTouchBlocked(nowMs)) return;
  const auto touch = M5.Touch.getDetail(0);
  if (touch.wasPressed()) {
    if (touch.y >= 150 && touch.y < 178 && touch.x >= 250 && touch.x < 390) {
      if (!setInverted(!orientation.inverted(), nowMs)) drawDiagnosticLine(154, "倒挂模式", "保存失败", TFT_RED);
      return;
    } else if (touch.y >= 178 && touch.y < 225) {
      if (touch.x >= 245 && touch.x < 315) adjustBrightness(-1);
      if (touch.x >= 320 && touch.x < 390) adjustBrightness(1);
    } else if (touch.y >= 242 && touch.y < 290 &&
               touch.x >= 250 && touch.x < 390) {
      toggleDebugMode();
    } else if (touch.y >= 288 && touch.y < 330 &&
               touch.x >= 75 && touch.x < 390) {
      if(touch.x>=240){panelPage=PanelPage::Network;forgetNetworkConfirm=false;drawNetworkFrame();}
      else {panelPage = PanelPage::Sound;drawSoundFrame();}
    } else if (touch.y >= 330 && touch.y < 372 &&
               touch.x >= 110 && touch.x < 356) {
      panelPage = PanelPage::Bluetooth;
      clearBleBindingConfirm = false;
      drawBluetoothFrame();
    } else if (touch.y >= 372 && touch.y < 414 &&
               touch.x >= 110 && touch.x < 356) {
      panelPage = PanelPage::Hardware;
      drawDiagnosticFrame();
    } else if (touch.y >= 414 && touch.y < 454 &&
               touch.x >= 160 && touch.x < 306) {
      panelPage = PanelPage::Audio;
      drawPanelFrame("BLE Audio v0.7.2-P0");
      drawPanelButton(170, 396, 126, "Back");
      audioProbe.enter();
      return;
    }
  }
  if (nowMs - lastBatteryRefreshMs >= kBatteryRefreshIntervalMs) {
    drawBatteryLine();
  }
}

void handleSoundInput() {
  const auto touch=M5.Touch.getDetail(0); if(!touch.wasPressed())return;
  if(touch.y>=390 && touch.y<440){soundControl.stopNow();if(settingsReady&&soundVolumePending){settings.putUChar(kSoundVolumeKey,pendingSoundVolume);soundVolumePending=false;}panelPage=PanelPage::Settings;drawSettingsFrame();return;}
  if(touch.y>=196 && touch.y<256){
    if(touch.x<175)soundControl.setLocalVolume(soundControl.volume()>=5?soundControl.volume()-5:0);
    else if(touch.x>285)soundControl.setLocalVolume(std::min<int>(100,soundControl.volume()+5));
    else soundControl.preview(2);
    drawSoundFrame(); return;
  }
  if(touch.y>=255 && touch.y<330){if(touch.x<233)soundControl.toggleMute();else soundControl.stopNow();drawSoundFrame();}
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
  stopStopWatchSpeaker();
  Serial.begin(115200);

  settingsReady = settings.begin("gorkbot", false);
  bool bleEnabled = false;
  bool bleBound = false;
  uint8_t soundVolume = 20;
  uint8_t blePeer[BLEControl::kPeerAddressLength] = {};
  if (settingsReady) {
    brightness = settings.getUChar("brightness", kDefaultBrightness);
    debugMode = settings.getBool("debug", false);
    orientation.setInverted(settings.getBool(kInvertedKey, false));
    bleEnabled = settings.getBool(kBleEnabledKey, false);
    bleBound = settings.getBool(kBleBoundKey, false);
    soundVolume = settings.getUChar(kSoundVolumeKey, 20);
    if (bleBound && settings.getBytes(kBlePeerKey, blePeer, sizeof(blePeer)) !=
                        sizeof(blePeer)) {
      bleBound = false;
      settings.putBool(kBleBoundKey, false);
    }
  }
  M5.Display.setRotation(orientation.rotation());
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
  bleControl.setSoundControl(&soundControl);
  audioProbe.setSoundControl(&soundControl);
  networkControl.begin();
  bleControl.setNetworkControl(&networkControl);
  audioProbe.setNetworkControl(&networkControl);
  soundControl.setInitialVolume(soundVolume);
  if (!bleControl.begin(bleEnabled, bleBound, blePeer)) {
    Serial.println("BLE control failed to initialize; kept OFF");
    if (settingsReady) settings.putBool(kBleEnabledKey, false);
  }
  audioProbe.enter(false);

  Serial.println("Expression device started");
  Serial.println(kFirmwareVersion);
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
  networkControl.update(nowMs,audioProbe.busy());
  processNetworkCommands(nowMs);
  const bool orientationWasIdle = orientationIdle(nowMs);
  audioProbe.update(nowMs);
  const bool connectionAudioBlocked = (menuOpen && panelPage == PanelPage::Audio) ||
      audioProbe.busy() || audioProbe.preparing(nowMs);
  soundControl.update(nowMs, connectionAudioBlocked);
  const bool wifiJoined = networkControl.wifiJoined();
  const bool bleTrusted = bleControl.audioPeerAllowed(bleControl.connectionId());
  // Drop an announcement whose link vanished; do not stop another audio owner.
  if (soundControl.isAnnouncing() &&
      ((activeConnectionCue == ConnectionAnnouncements::Wifi && !wifiJoined) ||
       (activeConnectionCue == ConnectionAnnouncements::Ble && !bleTrusted))) {
    soundControl.stopNow();
  }
  const bool cancelConnectionCue = soundControl.stopEpoch() != connectionSoundStopEpoch ||
      M5.BtnA.wasClicked() || M5.BtnB.wasPressed() || menuToggleLatched;
  connectionSoundStopEpoch = soundControl.stopEpoch();
  const auto cue = connectionAnnouncements.update(nowMs, wifiJoined, bleTrusted,
      bleControl.linkEpoch(), connectionAudioBlocked, !soundControl.volume(),
      soundControl.isPlaying(), cancelConnectionCue);
  if (cue != ConnectionAnnouncements::None) {
    using namespace gork_connection_voice;
    const auto* pcm = cue == ConnectionAnnouncements::Wifi ? kWifi : kBle;
    const size_t samples = cue == ConnectionAnnouncements::Wifi ? sizeof(kWifi)/sizeof(*kWifi) : sizeof(kBle)/sizeof(*kBle);
    if (soundControl.announce(pcm, samples)) activeConnectionCue = cue;
  }
  uint8_t changedVolume = 0;
  if (soundControl.takeVolumeChanged(&changedVolume)) {
    pendingSoundVolume=changedVolume; soundVolumeChangedAtMs=nowMs; soundVolumePending=true;
  }
  if(settingsReady&&soundVolumePending&&nowMs-soundVolumeChangedAtMs>=800){settings.putUChar(kSoundVolumeKey,pendingSoundVolume);soundVolumePending=false;}

  if (menuOpen) {
    orientationGesture.reset(nowMs);
    if (panelPage == PanelPage::Settings) {
      handleSettingsInput(nowMs);
    } else if (panelPage == PanelPage::Bluetooth) {
      handleBluetoothInput(nowMs);
    } else if (panelPage == PanelPage::Sound) {
      handleSoundInput();
    } else if(panelPage==PanelPage::Network){
      handleNetworkInput(nowMs);
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
    if (M5.BtnA.wasClicked()&&!audioProbe.takeAConsumed()&&!menuToggleLatched) {
      avatar.previous(nowMs);
      startVibration(125, 35);
    }
    const bool bClicked = M5.BtnB.wasClicked() && !menuToggleLatched;
    const bool bConsumed = bClicked && (soundControl.takeButtonBConsumed() | audioProbe.takeBConsumed());
    const auto direction = orientationGesture.update(nowMs,
        orientationWasIdle && orientationIdle(nowMs),
        bClicked, !bConsumed);
    if (direction.flip) setInverted(!orientation.inverted(), nowMs);
    for (uint8_t i = 0; i < direction.browse; ++i) {
      avatar.next(nowMs); startVibration(125, 35);
    }
    handleProductTouch(nowMs);
    handleImuInteraction(nowMs);
    renderAvatarWithAudioHint(nowMs);
  }

  // A short cooperative yield keeps input responsive without quantizing the
  // 60 fps renderer onto a coarse 5 ms loop cadence.
  delay(1);
}
