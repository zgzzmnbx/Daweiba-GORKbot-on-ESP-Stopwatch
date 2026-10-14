// SPDX-License-Identifier: AGPL-3.0-or-later
// Retained production registration fragment before the v0.11.2 fix.
{
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

  if (audioProbe_ && !audioProbe_->attach(server_)) {
    BLEDevice::deinit(false);
    return false;
  }
  if (soundControl_ && !soundControl_->attach(server_)) {
    BLEDevice::deinit(false);
    return false;
  }
  service_->start();
  BLEAdvertising* advertising = server_->getAdvertising();
  advertising->addServiceUUID(kServiceUuid);
  advertising->setScanResponse(true);
  initialized_ = true;
  return true;
}
