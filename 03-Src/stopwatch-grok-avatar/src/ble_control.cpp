// SPDX-License-Identifier: AGPL-3.0-or-later

#include "ble_control.h"

#include <Arduino.h>
#include <BLE2902.h>
#include <algorithm>
#include <cstring>

#include <esp_gatt_defs.h>
#include <esp_gap_ble_api.h>

namespace {

bool deadlineReached(uint32_t nowMs, uint32_t deadlineMs) {
  return deadlineMs != 0 && static_cast<int32_t>(nowMs - deadlineMs) >= 0;
}

bool isNonZeroAddress(const uint8_t* address) {
  for (uint8_t index = 0; index < BLEControl::kPeerAddressLength; ++index) {
    if (address[index] != 0) return true;
  }
  return false;
}

}  // namespace

BLEControl::BLEControl()
    : serverCallbacks_(this),
      commandCallbacks_(this),
      securityCallbacks_(this) {}

bool BLEControl::begin(bool enabled, bool hasBoundPeer,
                       const uint8_t* boundPeer) {
  enabled_ = false;
  initialized_ = false;
  advertising_ = false;
  pairingWindow_ = false;
  pairingEndsAtMs_ = 0;
  hasBoundPeer_ = hasBoundPeer && boundPeer != nullptr;
  if (hasBoundPeer_) {
    memcpy(boundPeer_, boundPeer, kPeerAddressLength);
  } else {
    memset(boundPeer_, 0, sizeof(boundPeer_));
  }
  pendingBinding_ = false;
  connected_ = false;
  authorized_ = false;
  disconnectRequested_ = false;
  rejectConnectionRequested_ = false;
  rejectConnectionId_ = 0;
  resetQueues();

  if (!enabled) return true;
  enabled_ = true;
  if (!initializeStack()) {
    enabled_ = false;
    return false;
  }
  if (hasBoundPeer_) startAdvertising();
  return true;
}

bool BLEControl::initializeStack() {
  if (initialized_) return true;

  BLEDevice::init(std::string(kDeviceName));
  BLEDevice::setEncryptionLevel(ESP_BLE_SEC_ENCRYPT);
  BLEDevice::setSecurityCallbacks(&securityCallbacks_);

  security_.setAuthenticationMode(ESP_LE_AUTH_REQ_SC_BOND);
  security_.setCapability(ESP_IO_CAP_NONE);
  security_.setInitEncryptionKey(ESP_BLE_ENC_KEY_MASK | ESP_BLE_ID_KEY_MASK);
  security_.setRespEncryptionKey(ESP_BLE_ENC_KEY_MASK | ESP_BLE_ID_KEY_MASK);
  security_.setKeySize(16);
  uint8_t onlySpecified = ESP_BLE_ONLY_ACCEPT_SPECIFIED_AUTH_ENABLE;
  if (esp_ble_gap_set_security_param(
          ESP_BLE_SM_ONLY_ACCEPT_SPECIFIED_SEC_AUTH, &onlySpecified,
          sizeof(onlySpecified)) != ESP_OK) {
    // Failing closed is important: encrypted attribute permissions without a
    // configured SMP policy are not sufficient for the application's binding
    // promise.
    BLEDevice::deinit(false);
    return false;
  }

  server_ = BLEDevice::createServer();
  if (server_ == nullptr) {
    BLEDevice::deinit(false);
    return false;
  }
  server_->setCallbacks(&serverCallbacks_);

  service_ = server_->createService(kServiceUuid);
  if (service_ == nullptr) {
    BLEDevice::deinit(false);
    return false;
  }

  commandCharacteristic_ = service_->createCharacteristic(
      kCommandUuid, BLECharacteristic::PROPERTY_WRITE);
  statusCharacteristic_ = service_->createCharacteristic(
      kStatusUuid,
      BLECharacteristic::PROPERTY_READ | BLECharacteristic::PROPERTY_NOTIFY);
  if (commandCharacteristic_ == nullptr || statusCharacteristic_ == nullptr) {
    BLEDevice::deinit(false);
    return false;
  }

  commandCharacteristic_->setAccessPermissions(ESP_GATT_PERM_WRITE_ENCRYPTED);
  commandCharacteristic_->setCallbacks(&commandCallbacks_);
  statusCharacteristic_->setAccessPermissions(ESP_GATT_PERM_READ_ENCRYPTED);
  auto* statusDescriptor = new BLE2902();
  statusDescriptor->setAccessPermissions(ESP_GATT_PERM_READ_ENCRYPTED |
                                         ESP_GATT_PERM_WRITE_ENCRYPTED);
  statusCharacteristic_->addDescriptor(statusDescriptor);
  statusCharacteristic_->setValue("READY");

  service_->start();
  BLEAdvertising* advertising = server_->getAdvertising();
  advertising->addServiceUUID(kServiceUuid);
  advertising->setScanResponse(true);
  initialized_ = true;
  return true;
}

void BLEControl::update(uint32_t nowMs) {
  if (!initialized_) return;

  if (pairingWindow_ && deadlineReached(nowMs, pairingEndsAtMs_)) {
    pairingWindow_ = false;
    pairingEndsAtMs_ = 0;
    if (!hasBoundPeer_) {
      stopAdvertising();
      if (connected_ && !authorized_) disconnectRequested_ = true;
    }
  }

  if (disconnectRequested_ && connected_ && server_ != nullptr) {
    server_->disconnect(connectionId_);
    disconnectRequested_ = false;
  }

  if (rejectConnectionRequested_ && server_ != nullptr) {
    server_->disconnect(rejectConnectionId_);
    rejectConnectionRequested_ = false;
    rejectConnectionId_ = 0;
  }

  if (!connected_ && enabled_ &&
      (hasBoundPeer_ || pairingWindowOpen(nowMs))) {
    startAdvertising();
  }

  StatusEvent event;
  while (popStatus(&event)) {
    notifyStatus(event);
  }

  bool overflowPending = false;
  uint16_t overflowConnectionId = 0;
  portENTER_CRITICAL(&queueMux_);
  if (overflowStatusPending_) {
    overflowPending = true;
    overflowConnectionId = overflowStatusConnectionId_;
    overflowStatusPending_ = false;
  }
  portEXIT_CRITICAL(&queueMux_);
  if (overflowPending) {
    StatusEvent full;
    full.connectionId = overflowConnectionId;
    full.length = 8;
    memcpy(full.value, "ERR:FULL", full.length + 1);
    notifyStatus(full);
  }
}

bool BLEControl::setEnabled(bool enabled, uint32_t nowMs) {
  if (!enabled) {
    enabled_ = false;
    pairingWindow_ = false;
    pairingEndsAtMs_ = 0;
    stopAdvertising();
    resetQueues();
    if (connected_) disconnectRequested_ = true;
    return true;
  }

  enabled_ = true;
  if (!initializeStack()) {
    enabled_ = false;
    return false;
  }
  if (hasBoundPeer_) {
    startAdvertising();
  } else if (pairingWindowOpen(nowMs)) {
    startAdvertising();
  }
  return true;
}

bool BLEControl::openPairingWindow(uint32_t nowMs) {
  if (!enabled_ || hasBoundPeer_) return false;
  if (!initializeStack()) return false;
  pairingWindow_ = true;
  pairingEndsAtMs_ = nowMs + kPairWindowMs;
  startAdvertising();
  return true;
}

void BLEControl::clearBinding() {
  pairingWindow_ = false;
  pairingEndsAtMs_ = 0;
  stopAdvertising();
  resetQueues();
  if (connected_) disconnectRequested_ = true;

  if (initialized_) {
    const int bondCount = esp_ble_get_bond_device_num();
    if (bondCount > 0) {
      constexpr int kMaxBondsToClear = 8;
      esp_ble_bond_dev_t bonds[kMaxBondsToClear] = {};
      int listed = std::min(bondCount, kMaxBondsToClear);
      if (esp_ble_get_bond_device_list(&listed, bonds) == ESP_OK) {
        for (int index = 0; index < listed; ++index) {
          esp_ble_remove_bond_device(bonds[index].bd_addr);
        }
      }
    }
  }

  hasBoundPeer_ = false;
  pendingBinding_ = false;
  memset(boundPeer_, 0, sizeof(boundPeer_));
  memset(pendingPeer_, 0, sizeof(pendingPeer_));
}

bool BLEControl::takeCommand(char* out, size_t outCapacity,
                             uint16_t* connectionId,
                             uint8_t* payloadLength) {
  if (out == nullptr || outCapacity == 0) return false;

  portENTER_CRITICAL(&queueMux_);
  if (commandCount_ == 0) {
    portEXIT_CRITICAL(&queueMux_);
    return false;
  }
  const CommandEvent& event = commandQueue_[commandHead_];
  if (outCapacity < static_cast<size_t>(event.length) + 1) {
    portEXIT_CRITICAL(&queueMux_);
    return false;
  }
  memcpy(out, event.value, event.length + 1);
  if (connectionId != nullptr) *connectionId = event.connectionId;
  if (payloadLength != nullptr) *payloadLength = event.length;
  commandHead_ = (commandHead_ + 1) % kCommandQueueCapacity;
  --commandCount_;
  portEXIT_CRITICAL(&queueMux_);
  return true;
}

void BLEControl::publishResult(uint16_t connectionId, const char* status) {
  if (!enabled_ || !initialized_ || !connected_ || !authorized_ ||
      connectionId != connectionId_ || statusCharacteristic_ == nullptr ||
      status == nullptr) {
    return;
  }
  char value[kMaxStatusLength + 1] = {};
  const size_t length = std::min(strlen(status),
                                 static_cast<size_t>(kMaxStatusLength));
  memcpy(value, status, length);
  statusCharacteristic_->setValue(reinterpret_cast<uint8_t*>(value), length);
  statusCharacteristic_->notify();
}

bool BLEControl::takeNewBinding(uint8_t* outPeer, size_t outCapacity) {
  if (outPeer == nullptr || outCapacity < kPeerAddressLength) return false;
  portENTER_CRITICAL(&queueMux_);
  if (!pendingBinding_) {
    portEXIT_CRITICAL(&queueMux_);
    return false;
  }
  memcpy(outPeer, pendingPeer_, kPeerAddressLength);
  pendingBinding_ = false;
  portEXIT_CRITICAL(&queueMux_);
  return true;
}

bool BLEControl::pairingWindowOpen(uint32_t nowMs) const {
  return pairingWindow_ && !deadlineReached(nowMs, pairingEndsAtMs_);
}

uint16_t BLEControl::pairingSecondsRemaining(uint32_t nowMs) const {
  if (!pairingWindowOpen(nowMs)) return 0;
  const uint32_t remainingMs = pairingEndsAtMs_ - nowMs;
  return static_cast<uint16_t>((remainingMs + 999) / 1000);
}

void BLEControl::startAdvertising() {
  if (!initialized_ || advertising_ || server_ == nullptr) return;
  server_->getAdvertising()->start();
  advertising_ = true;
}

void BLEControl::stopAdvertising() {
  if (!initialized_ || !advertising_ || server_ == nullptr) return;
  server_->getAdvertising()->stop();
  advertising_ = false;
}

void BLEControl::requestDisconnect() {
  if (connected_) disconnectRequested_ = true;
}

bool BLEControl::addressMatches(const uint8_t* address) const {
  return address != nullptr && hasBoundPeer_ &&
         memcmp(boundPeer_, address, kPeerAddressLength) == 0;
}

bool BLEControl::currentPeerAllowed() const {
  if (!enabled_) return false;
  if (!hasBoundPeer_) return pairingWindow_;
  // The first authenticated connection may report an identity address that
  // differs from the connection address (for example with a resolvable
  // private address).  Once that connection has authenticated, keep the
  // current link usable; future links still require the stored peer address.
  return addressMatches(connectedPeer_) || (connected_ && authorized_);
}

bool BLEControl::validCommandBytes(const uint8_t* data, size_t length) const {
  if (data == nullptr || length == 0 || length > kMaxCommandLength) {
    return false;
  }
  for (size_t index = 0; index < length; ++index) {
    const uint8_t character = data[index];
    if (character == ' ') {
      if (index == 0 || index + 1 == length || data[index - 1] == ' ') {
        return false;
      }
      continue;
    }
    if (character == '-') continue;
    if (character < 'a' || character > 'z') return false;
  }
  return true;
}

void BLEControl::enqueueCommand(uint16_t connectionId, const uint8_t* data,
                                size_t length) {
  if (data == nullptr || length > kMaxCommandLength) return;
  portENTER_CRITICAL(&queueMux_);
  if (commandCount_ >= kCommandQueueCapacity) {
    if (!overflowStatusPending_) {
      overflowStatusPending_ = true;
      overflowStatusConnectionId_ = connectionId;
    }
    portEXIT_CRITICAL(&queueMux_);
    return;
  }
  CommandEvent& event = commandQueue_[commandTail_];
  event.connectionId = connectionId;
  event.length = static_cast<uint8_t>(length);
  memcpy(event.value, data, length);
  event.value[length] = '\0';
  commandTail_ = (commandTail_ + 1) % kCommandQueueCapacity;
  ++commandCount_;
  portEXIT_CRITICAL(&queueMux_);
}

void BLEControl::enqueueStatus(uint16_t connectionId, const char* status) {
  if (status == nullptr) return;
  portENTER_CRITICAL(&queueMux_);
  if (statusCount_ >= kStatusQueueCapacity) {
    overflowStatusPending_ = true;
    overflowStatusConnectionId_ = connectionId;
    portEXIT_CRITICAL(&queueMux_);
    return;
  }
  StatusEvent& event = statusQueue_[statusTail_];
  event.connectionId = connectionId;
  event.length = static_cast<uint8_t>(std::min(
      strlen(status), static_cast<size_t>(kMaxStatusLength)));
  memcpy(event.value, status, event.length);
  event.value[event.length] = '\0';
  statusTail_ = (statusTail_ + 1) % kStatusQueueCapacity;
  ++statusCount_;
  portEXIT_CRITICAL(&queueMux_);
}

bool BLEControl::popStatus(StatusEvent* event) {
  if (event == nullptr) return false;
  portENTER_CRITICAL(&queueMux_);
  if (statusCount_ == 0) {
    portEXIT_CRITICAL(&queueMux_);
    return false;
  }
  *event = statusQueue_[statusHead_];
  statusHead_ = (statusHead_ + 1) % kStatusQueueCapacity;
  --statusCount_;
  portEXIT_CRITICAL(&queueMux_);
  return true;
}

void BLEControl::notifyStatus(const StatusEvent& event) {
  if (!enabled_ || !initialized_ || !connected_ || !authorized_ ||
      event.connectionId != connectionId_ || statusCharacteristic_ == nullptr) {
    return;
  }
  statusCharacteristic_->setValue(
      reinterpret_cast<uint8_t*>(const_cast<char*>(event.value)),
      event.length);
  statusCharacteristic_->notify();
}

void BLEControl::resetQueues() {
  portENTER_CRITICAL(&queueMux_);
  commandHead_ = 0;
  commandTail_ = 0;
  commandCount_ = 0;
  statusHead_ = 0;
  statusTail_ = 0;
  statusCount_ = 0;
  overflowStatusPending_ = false;
  overflowStatusConnectionId_ = 0;
  portEXIT_CRITICAL(&queueMux_);
}

void BLEControl::ServerCallbacks::onConnect(
    BLEServer* /*server*/, esp_ble_gatts_cb_param_t* param) {
  if (owner_ == nullptr || param == nullptr) return;
  if (owner_->connected_) {
    owner_->rejectConnectionRequested_ = true;
    owner_->rejectConnectionId_ = param->connect.conn_id;
    return;
  }
  owner_->connected_ = true;
  owner_->authorized_ = false;
  owner_->disconnectRequested_ = false;
  owner_->advertising_ = false;
  owner_->connectionId_ = param->connect.conn_id;
  memcpy(owner_->connectedPeer_, param->connect.remote_bda,
         BLEControl::kPeerAddressLength);
  if (!owner_->currentPeerAllowed()) owner_->disconnectRequested_ = true;
}

void BLEControl::ServerCallbacks::onDisconnect(
    BLEServer* /*server*/, esp_ble_gatts_cb_param_t* param) {
  if (owner_ == nullptr || param == nullptr ||
      param->disconnect.conn_id != owner_->connectionId_) {
    return;
  }
  owner_->connected_ = false;
  owner_->authorized_ = false;
  owner_->disconnectRequested_ = false;
  owner_->connectionId_ = 0;
  owner_->resetQueues();
}

void BLEControl::CommandCallbacks::onWrite(
    BLECharacteristic* /*characteristic*/, esp_ble_gatts_cb_param_t* param) {
  if (owner_ == nullptr || param == nullptr) return;
  const uint16_t connectionId = param->write.conn_id;
  if (!owner_->enabled_ || !owner_->initialized_ || !owner_->connected_ ||
      connectionId != owner_->connectionId_ || !owner_->authorized_ ||
      !owner_->currentPeerAllowed()) {
    owner_->enqueueStatus(connectionId, "ERR:AUTH");
    return;
  }
  if (param->write.len > BLEControl::kMaxCommandLength) {
    owner_->enqueueStatus(connectionId, "ERR:BAD_LEN");
    return;
  }
  const bool textPacket = param->write.len > 0 &&
      param->write.value[0] >= BLEControl::kTextBegin &&
      param->write.value[0] <= BLEControl::kTextClear;
  if (!textPacket &&
      !owner_->validCommandBytes(param->write.value, param->write.len)) {
    owner_->enqueueStatus(connectionId, "ERR:BAD_CMD");
    return;
  }
  owner_->enqueueCommand(connectionId, param->write.value, param->write.len);
}

uint32_t BLEControl::SecurityCallbacks::onPassKeyRequest() { return 0; }

void BLEControl::SecurityCallbacks::onPassKeyNotify(uint32_t /*passKey*/) {}

bool BLEControl::SecurityCallbacks::onSecurityRequest() {
  return owner_ != nullptr && owner_->currentPeerAllowed();
}

void BLEControl::SecurityCallbacks::onAuthenticationComplete(
    esp_ble_auth_cmpl_t result) {
  if (owner_ == nullptr || !owner_->connected_ ||
      !owner_->currentPeerAllowed()) {
    if (owner_ != nullptr) owner_->requestDisconnect();
    return;
  }
  if (!result.success) {
    owner_->requestDisconnect();
    return;
  }

  if (owner_->hasBoundPeer_) {
    if (!owner_->addressMatches(result.bd_addr) &&
        !owner_->addressMatches(owner_->connectedPeer_)) {
      owner_->requestDisconnect();
      return;
    }
    owner_->authorized_ = true;
    return;
  }

  // A device can only become the bound controller after a locally opened
  // pairing window and a successful encrypted authentication.
  if (!owner_->pairingWindow_) {
    owner_->requestDisconnect();
    return;
  }
  const uint8_t* peer = isNonZeroAddress(result.bd_addr)
                            ? result.bd_addr
                            : owner_->connectedPeer_;
  memcpy(owner_->boundPeer_, peer, BLEControl::kPeerAddressLength);
  memcpy(owner_->pendingPeer_, peer, BLEControl::kPeerAddressLength);
  owner_->hasBoundPeer_ = true;
  owner_->pendingBinding_ = true;
  owner_->pairingWindow_ = false;
  owner_->pairingEndsAtMs_ = 0;
  owner_->authorized_ = true;
}

bool BLEControl::SecurityCallbacks::onConfirmPIN(uint32_t /*pin*/) {
  return true;
}
