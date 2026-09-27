package com.daweiba.gork

import android.annotation.SuppressLint
import android.app.Activity
import android.bluetooth.BluetoothAdapter
import android.bluetooth.BluetoothDevice
import android.bluetooth.BluetoothGatt
import android.bluetooth.BluetoothGattCallback
import android.bluetooth.BluetoothGattCharacteristic
import android.bluetooth.BluetoothGattDescriptor
import android.bluetooth.BluetoothManager
import android.bluetooth.BluetoothStatusCodes
import android.bluetooth.le.ScanCallback
import android.bluetooth.le.ScanFilter
import android.bluetooth.le.ScanResult
import android.bluetooth.le.ScanSettings
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.os.Build
import android.os.Handler
import android.os.Looper
import android.os.ParcelUuid
import org.json.JSONArray
import org.json.JSONObject
import java.nio.charset.StandardCharsets
import java.util.UUID

/** One GATT owner. All state transitions and writes run on the main looper. */
@SuppressLint("MissingPermission")
class WatchBleController(private val activity: Activity) {
    private val handler = Handler(Looper.getMainLooper())
    private val adapter get() = (activity.getSystemService(Context.BLUETOOTH_SERVICE) as BluetoothManager).adapter
    private val candidates = linkedMapOf<String, BluetoothDevice>()
    private var scanCallback: ScanCallback? = null
    private var scanDone: ((Boolean, String, JSONArray?) -> Unit)? = null
    private var bondReceiver: BroadcastReceiver? = null
    private var gatt: BluetoothGatt? = null
    private var connectionEpoch = 0
    private var state = "DISCONNECTED"
    private var connectDone: ((Boolean, String, JSONObject?) -> Unit)? = null
    private val notifications = ArrayDeque<BluetoothGattCharacteristic>()
    private var task: Task? = null
    private var textId = 1
    private var soundId = 1
    private var audioPacketBytes = 20
    private var audioTransferId = 0xf00d
    private var audio: AudioTask? = null

    private data class AudioTask(
        val connection: Int,
        val clip: WavPcm16.Clip,
        val done: (Boolean, String, JSONObject?) -> Unit,
        var transfer: Int = 0xf00d,
        var session: Long = 0,
        var stage: String = "HELLO",
        var offset: Int = 0,
        var nextOffset: Int = 0,
        var writeDone: Boolean = false,
        var receipt: WatchProtocol.AudioPacket? = null,
        var serial: Int = 0,
    )

    private data class Task(
        val epoch: Int,
        val kind: String,
        val packets: List<WatchProtocol.ExpectedPacket>,
        val soundRequest: Int,
        val done: (Boolean, String, JSONObject?) -> Unit,
        var index: Int = 0,
    )

    fun snapshot(): JSONObject = JSONObject().put("device", state).put("ready", state == "READY")
        .put("audio", audio?.let {
            JSONObject().put("stage", it.stage).put("confirmedBytes", it.offset).put("totalBytes", it.clip.pcm.size)
        } ?: JSONObject.NULL)

    fun scan(done: (Boolean, String, JSONArray?) -> Unit) {
        if (state == "READY" || state == "CONNECTING" || state == "BONDING") {
            done(false, "DEVICE_BUSY", null); return
        }
        if (adapter?.isEnabled != true) { done(false, "BLUETOOTH_OFF", null); return }
        scanDone?.invoke(false, "SCAN_CANCELLED", null)
        stopScan()
        candidates.clear()
        val scanner = adapter.bluetoothLeScanner ?: run { done(false, "SCAN_UNAVAILABLE", null); return }
        state = "SCANNING"
        scanDone = done
        val callback = object : ScanCallback() {
            override fun onScanResult(callbackType: Int, result: ScanResult) {
                handler.post {
                    val device = result.device
                    val name = result.scanRecord?.deviceName ?: try { device.name } catch (_: SecurityException) { null }
                    if (name == "GorkBot-SW" || result.scanRecord?.serviceUuids?.any {
                            it.uuid == WatchProtocol.expressionService
                        } == true) candidates[device.address] = device
                }
            }
            override fun onScanFailed(errorCode: Int) {
                handler.post { finishScan(false, "SCAN_FAILED_$errorCode") }
            }
        }
        scanCallback = callback
        try {
            scanner.startScan(
                listOf(ScanFilter.Builder().setServiceUuid(ParcelUuid(WatchProtocol.expressionService)).build()),
                ScanSettings.Builder().setScanMode(ScanSettings.SCAN_MODE_LOW_LATENCY).build(), callback
            )
        } catch (_: Exception) { finishScan(false, "SCAN_FAILED"); return }
        handler.postDelayed({ if (scanCallback === callback) finishScan(true, "OK") }, 8000)
    }

    private fun finishScan(ok: Boolean, code: String) {
        val done = scanDone ?: return
        stopScan()
        state = "DISCONNECTED"
        val devices = JSONArray()
        if (ok) candidates.forEach { (address, device) ->
            val name = try { device.name } catch (_: SecurityException) { null }
            devices.put(JSONObject().put("address", address).put("name", name ?: "GorkBot-SW"))
        }
        done(ok, code, if (ok) devices else null)
    }

    private fun stopScan() {
        scanCallback?.let { callback -> try { adapter?.bluetoothLeScanner?.stopScan(callback) } catch (_: Exception) {} }
        scanCallback = null
        scanDone = null
    }

    fun connect(address: String, done: (Boolean, String, JSONObject?) -> Unit) {
        val device = candidates[address]
        if (device == null) { done(false, "TARGET_NOT_SCANNED", null); return }
        close("DISCONNECTED")
        connectDone = done
        if (adapter?.isEnabled != true) { close("BLUETOOTH_OFF"); return }
        val epoch = ++connectionEpoch
        val alreadyBonded = try { device.bondState == BluetoothDevice.BOND_BONDED }
            catch (_: SecurityException) { close("PERMISSION_DENIED"); return }
        if (alreadyBonded) {
            openGatt(device, epoch)
            return
        }
        state = "BONDING"
        val receiver = object : BroadcastReceiver() {
            override fun onReceive(context: Context, intent: Intent) {
                val peer = if (Build.VERSION.SDK_INT >= 33)
                    intent.getParcelableExtra(BluetoothDevice.EXTRA_DEVICE, BluetoothDevice::class.java)
                else @Suppress("DEPRECATION") intent.getParcelableExtra(BluetoothDevice.EXTRA_DEVICE)
                if (peer?.address != device.address || epoch != connectionEpoch) return
                when (intent.getIntExtra(BluetoothDevice.EXTRA_BOND_STATE, BluetoothDevice.BOND_NONE)) {
                    BluetoothDevice.BOND_BONDED -> if (device.bondState == BluetoothDevice.BOND_BONDED) {
                        clearBondReceiver(); openGatt(device, epoch)
                    }
                    BluetoothDevice.BOND_NONE -> { clearBondReceiver(); close("PAIRING_FAILED") }
                }
            }
        }
        bondReceiver = receiver
        val filter = IntentFilter(BluetoothDevice.ACTION_BOND_STATE_CHANGED)
        if (Build.VERSION.SDK_INT >= 33) activity.registerReceiver(receiver, filter, Context.RECEIVER_EXPORTED)
        else @Suppress("DEPRECATION") activity.registerReceiver(receiver, filter)
        try {
            if (!device.createBond()) close("PAIRING_FAILED")
        } catch (_: Exception) { close("PAIRING_FAILED") }
        handler.postDelayed({ if (epoch == connectionEpoch && state == "BONDING") close("PAIRING_TIMEOUT") }, 45_000)
    }

    private fun clearBondReceiver() {
        bondReceiver?.let { try { activity.unregisterReceiver(it) } catch (_: Exception) {} }
        bondReceiver = null
    }

    private fun openGatt(device: BluetoothDevice, epoch: Int) {
        if (epoch != connectionEpoch) return
        state = "CONNECTING"
        try { gatt = device.connectGatt(activity, false, callback, BluetoothDevice.TRANSPORT_LE) }
        catch (_: Exception) { close("CONNECT_FAILED") }
        handler.postDelayed({ if (epoch == connectionEpoch && state != "READY") close("CONNECT_TIMEOUT") }, 30_000)
    }

    private val callback = object : BluetoothGattCallback() {
        override fun onConnectionStateChange(client: BluetoothGatt, status: Int, newState: Int) {
            handler.post {
                if (client !== gatt) return@post
                if (status == BluetoothGatt.GATT_SUCCESS && newState == BluetoothGatt.STATE_CONNECTED) {
                    state = "DISCOVERING"
                    if (!client.discoverServices()) close("DISCOVERY_FAILED")
                } else close(if (status == BluetoothGatt.GATT_SUCCESS) "DISCONNECTED" else "GATT_$status")
            }
        }

        override fun onServicesDiscovered(client: BluetoothGatt, status: Int) {
            handler.post {
                if (client !== gatt) return@post
                if (status != BluetoothGatt.GATT_SUCCESS || !requiredServicesPresent(client)) {
                    close("SERVICES_MISSING"); return@post
                }
                state = "NEGOTIATING_MTU"
                if (!client.requestMtu(247)) {
                    audioPacketBytes = 20
                    prepareSubscriptions(client)
                }
                else handler.postDelayed({
                    if (client === gatt && state == "NEGOTIATING_MTU") close("MTU_TIMEOUT")
                }, 5000)
            }
        }

        override fun onMtuChanged(client: BluetoothGatt, mtu: Int, status: Int) {
            handler.post {
                if (client !== gatt || state != "NEGOTIATING_MTU") return@post
                audioPacketBytes = if (status == BluetoothGatt.GATT_SUCCESS) (mtu - 3).coerceIn(20, 244) else 20
                prepareSubscriptions(client)
            }
        }

        override fun onDescriptorWrite(client: BluetoothGatt, descriptor: BluetoothGattDescriptor, status: Int) {
            handler.post {
                if (client !== gatt) return@post
                if (status != BluetoothGatt.GATT_SUCCESS) { close("SUBSCRIBE_FAILED_$status"); return@post }
                notifications.removeFirstOrNull()
                subscribeNext(client)
            }
        }

        @Suppress("DEPRECATION")
        override fun onCharacteristicChanged(client: BluetoothGatt, characteristic: BluetoothGattCharacteristic) {
            onNotification(client, characteristic.uuid, characteristic.value ?: byteArrayOf())
        }

        override fun onCharacteristicChanged(client: BluetoothGatt, characteristic: BluetoothGattCharacteristic, value: ByteArray) {
            onNotification(client, characteristic.uuid, value)
        }

        override fun onCharacteristicWrite(client: BluetoothGatt, characteristic: BluetoothGattCharacteristic, status: Int) {
            handler.post {
                if (client !== gatt) return@post
                if (status != BluetoothGatt.GATT_SUCCESS) { close("WRITE_FAILED_$status"); return@post }
                if (characteristic.uuid == WatchProtocol.audioInput) {
                    val current = audio ?: return@post
                    current.writeDone = true
                    if (current.receipt != null) advanceAudio(current)
                }
            }
        }
    }

    private fun requiredServicesPresent(client: BluetoothGatt): Boolean = listOf(
        WatchProtocol.expressionService to listOf(WatchProtocol.expressionCommand, WatchProtocol.expressionStatus),
        WatchProtocol.soundService to listOf(WatchProtocol.soundCommand, WatchProtocol.soundEvent),
        WatchProtocol.audioService to listOf(WatchProtocol.audioInput, WatchProtocol.audioEvent),
    ).all { (service, chars) -> client.getService(service)?.let { found -> chars.all { found.getCharacteristic(it) != null } } == true }

    private fun prepareSubscriptions(client: BluetoothGatt) {
        notifications.clear()
        notifications.add(client.getService(WatchProtocol.expressionService).getCharacteristic(WatchProtocol.expressionStatus))
        notifications.add(client.getService(WatchProtocol.soundService).getCharacteristic(WatchProtocol.soundEvent))
        notifications.add(client.getService(WatchProtocol.audioService).getCharacteristic(WatchProtocol.audioEvent))
        state = "SUBSCRIBING"
        subscribeNext(client)
    }

    private fun subscribeNext(client: BluetoothGatt) {
        val char = notifications.firstOrNull()
        if (char == null) {
            state = "READY"
            connectDone?.invoke(true, "READY", snapshot())
            connectDone = null
            return
        }
        val descriptor = char.getDescriptor(UUID.fromString("00002902-0000-1000-8000-00805f9b34fb"))
        if (descriptor == null || !client.setCharacteristicNotification(char, true)) { close("SUBSCRIBE_FAILED"); return }
        val started = if (Build.VERSION.SDK_INT >= 33)
            client.writeDescriptor(descriptor, BluetoothGattDescriptor.ENABLE_NOTIFICATION_VALUE) == BluetoothStatusCodes.SUCCESS
        else {
            descriptor.value = BluetoothGattDescriptor.ENABLE_NOTIFICATION_VALUE
            @Suppress("DEPRECATION") client.writeDescriptor(descriptor)
        }
        if (!started) close("SUBSCRIBE_FAILED")
    }

    private fun onNotification(client: BluetoothGatt, uuid: UUID, bytes: ByteArray) {
        handler.post {
            if (client !== gatt || state != "READY") return@post
            if (uuid == WatchProtocol.audioEvent && audio != null) {
                onAudioNotification(bytes)
                return@post
            }
            val current = task ?: return@post
            if (current.epoch != connectionEpoch) return@post
            if (current.kind == "expression" && uuid == WatchProtocol.expressionStatus) {
                val status = try { String(bytes, StandardCharsets.US_ASCII).trim() } catch (_: Exception) { return@post }
                if (status.startsWith("ERR:")) { finishTask(false, status); return@post }
                if (status == current.packets[current.index].status) {
                    current.index++
                    if (current.index == current.packets.size) finishTask(true, status)
                    else writeCurrent()
                }
            } else if (current.kind == "sound" && uuid == WatchProtocol.soundEvent) {
                val frame = try { WatchProtocol.SoundFrame.decode(bytes) } catch (_: Exception) { return@post }
                if (frame.id != current.soundRequest) return@post
                val requested = current.packets[0].bytes[1].toInt() and 0xff
                when (frame.operation) {
                    0xff -> finishTask(false, "SOUND_REJECTED")
                    else -> if (WatchProtocol.soundTerminal(requested, frame.operation)) finishTask(true, "SOUND_CONFIRMED")
                }
            }
        }
    }

    fun expression(name: String, mode: String, done: (Boolean, String, JSONObject?) -> Unit) {
        val packet = try { WatchProtocol.expression(name, mode) } catch (_: Exception) { done(false, "INVALID_EXPRESSION", null); return }
        begin(Task(connectionEpoch, "expression", listOf(packet), 0, done))
    }

    fun bubble(text: String, done: (Boolean, String, JSONObject?) -> Unit) {
        val packets = try { WatchProtocol.bubble(text, textId) } catch (_: Exception) { done(false, "INVALID_TEXT", null); return }
        textId = if (textId == 255) 1 else textId + 1
        begin(Task(connectionEpoch, "expression", packets, 0, done))
    }

    fun clear(done: (Boolean, String, JSONObject?) -> Unit) =
        begin(Task(connectionEpoch, "expression", listOf(WatchProtocol.clear()), 0, done))

    fun sound(operation: Int, value: Int, done: (Boolean, String, JSONObject?) -> Unit) {
        val id = soundId
        soundId = if (soundId == 65535) 1 else soundId + 1
        val encoded = try {
            when (operation) {
                3 -> WatchProtocol.soundPlay(id, value)
                4 -> WatchProtocol.SoundFrame(4, id).encode()
                5 -> WatchProtocol.soundVolume(id, value)
                else -> { done(false, "INVALID_SOUND", null); return }
            }
        } catch (_: Exception) { done(false, "INVALID_SOUND", null); return }
        begin(Task(connectionEpoch, "sound", listOf(WatchProtocol.ExpectedPacket(encoded, "")), id, done))
    }

    private fun begin(newTask: Task) {
        if (state != "READY") { newTask.done(false, "NOT_READY", null); return }
        if (task != null || audio != null) { newTask.done(false, "DEVICE_BUSY", null); return }
        task = newTask
        writeCurrent()
    }

    private fun writeCurrent() {
        val client = gatt ?: run { close("DISCONNECTED"); return }
        val current = task ?: return
        val uuid = if (current.kind == "sound") WatchProtocol.soundCommand else WatchProtocol.expressionCommand
        val service = if (current.kind == "sound") WatchProtocol.soundService else WatchProtocol.expressionService
        val char = client.getService(service)?.getCharacteristic(uuid) ?: run { close("SERVICES_MISSING"); return }
        val bytes = current.packets[current.index].bytes
        val started = if (Build.VERSION.SDK_INT >= 33)
            client.writeCharacteristic(char, bytes, BluetoothGattCharacteristic.WRITE_TYPE_DEFAULT) == BluetoothStatusCodes.SUCCESS
        else {
            char.value = bytes
            @Suppress("DEPRECATION") client.writeCharacteristic(char)
        }
        if (!started) { close("WRITE_FAILED"); return }
        val packetIndex = current.index
        handler.postDelayed({
            if (task === current && connectionEpoch == current.epoch && current.index == packetIndex) close("ACK_TIMEOUT")
        }, if (current.kind == "sound") 4000 else 2000)
    }

    private fun finishTask(ok: Boolean, code: String) {
        val current = task ?: return
        task = null
        current.done(ok, code, if (ok) JSONObject().put("receipt", code) else null)
    }

    fun playPcm(clip: WavPcm16.Clip, done: (Boolean, String, JSONObject?) -> Unit) {
        if (state != "READY") { done(false, "NOT_READY", null); return }
        if (task != null || audio != null) { done(false, "DEVICE_BUSY", null); return }
        if (audioTransferId >= 65535) { done(false, "AUDIO_SESSION_EXHAUSTED_RECONNECT", null); return }
        val current = AudioTask(connectionEpoch, clip, done)
        audio = current
        handler.postDelayed({
            if (audio === current && current.connection == connectionEpoch) close("AUDIO_TOTAL_TIMEOUT")
        }, 180_000)
        sendAudio(current)
    }

    private fun sendAudio(current: AudioTask) {
        val client = gatt ?: run { close("DISCONNECTED"); return }
        val char = client.getService(WatchProtocol.audioService)?.getCharacteristic(WatchProtocol.audioInput)
            ?: run { close("SERVICES_MISSING"); return }
        val packet = when (current.stage) {
            "HELLO" -> WatchProtocol.AudioPacket(1, current.transfer, 0, audioPacketBytes.toLong())
            "BEGIN" -> WatchProtocol.AudioPacket(4, current.transfer, current.session,
                current.clip.rate.toLong(), WatchProtocol.pcmBeginMetadata(current.clip.pcm.size))
            "DATA" -> {
                val chunk = ((audioPacketBytes - 12) and -2).coerceAtLeast(2)
                current.nextOffset = (current.offset + chunk).coerceAtMost(current.clip.pcm.size)
                WatchProtocol.AudioPacket(5, current.transfer, current.session, current.offset.toLong(),
                    current.clip.pcm.copyOfRange(current.offset, current.nextOffset))
            }
            "COMMIT" -> WatchProtocol.AudioPacket(6, current.transfer, current.session, current.clip.pcm.size.toLong())
            "PLAY" -> WatchProtocol.AudioPacket(7, current.transfer, current.session)
            else -> return
        }
        current.writeDone = false
        current.receipt = null
        current.serial++
        val bytes = packet.encode()
        val started = if (Build.VERSION.SDK_INT >= 33)
            client.writeCharacteristic(char, bytes, BluetoothGattCharacteristic.WRITE_TYPE_DEFAULT) == BluetoothStatusCodes.SUCCESS
        else {
            char.value = bytes
            @Suppress("DEPRECATION") client.writeCharacteristic(char)
        }
        if (!started) { close("AUDIO_WRITE_FAILED"); return }
        val serial = current.serial
        handler.postDelayed({
            if (audio === current && current.connection == connectionEpoch && current.serial == serial)
                close("AUDIO_${current.stage}_TIMEOUT")
        }, 5000)
    }

    private fun onAudioNotification(bytes: ByteArray) {
        val current = audio ?: return
        if (bytes.size > audioPacketBytes) { close("AUDIO_RECEIPT_OVERSIZE"); return }
        val packet = try { WatchProtocol.AudioPacket.decode(bytes) } catch (_: Exception) {
            close("AUDIO_BAD_RECEIPT"); return
        }
        if (packet.transfer != current.transfer) return
        if (packet.operation != 128 && packet.epoch != current.session) return
        if (packet.operation == 255 || (packet.operation == 129 && packet.data.contentEquals(byteArrayOf(8)))) {
            close("AUDIO_DEVICE_ERROR_${packet.value}"); return
        }
        if (current.stage == "PLAYED") {
            if (packet.operation == 134) finishAudio(true, "WATCH_PLAYED_RECEIPT")
            return
        }
        val expected = when (current.stage) { "HELLO" -> 128; "PLAY" -> 133; else -> 129 }
        if (packet.operation != expected) return
        if (current.stage == "HELLO") {
            if (packet.epoch == 0L || packet.value != 480000L || packet.data.size !in 4..5) {
                close("AUDIO_CAPS_INVALID"); return
            }
            val negotiated = (packet.data[0].toInt() and 255) or ((packet.data[1].toInt() and 255) shl 8)
            val seconds = (packet.data[2].toInt() and 255) or ((packet.data[3].toInt() and 255) shl 8)
            if (negotiated !in 20..audioPacketBytes || seconds != 10) { close("AUDIO_CAPS_INVALID"); return }
        } else if (current.stage == "PLAY") {
            if (packet.value != current.clip.pcm.size.toLong()) return
        } else {
            val op = when (current.stage) { "BEGIN" -> 4; "DATA" -> 5; "COMMIT" -> 6; else -> return }
            if (!packet.data.contentEquals(byteArrayOf(op.toByte()))) return
            val expectedOffset = if (current.stage == "DATA") current.nextOffset.toLong()
                else if (current.stage == "COMMIT") current.clip.pcm.size.toLong() else 0L
            if (packet.value != expectedOffset) return
        }
        current.receipt = packet
        if (current.writeDone) advanceAudio(current)
    }

    private fun advanceAudio(current: AudioTask) {
        val receipt = current.receipt ?: return
        when (current.stage) {
            "HELLO" -> {
                current.session = receipt.epoch
                audioPacketBytes = (receipt.data[0].toInt() and 255) or ((receipt.data[1].toInt() and 255) shl 8)
                audioTransferId++
                current.transfer = audioTransferId
                current.stage = "BEGIN"
            }
            "BEGIN" -> current.stage = "DATA"
            "DATA" -> {
                current.offset = current.nextOffset
                current.stage = if (current.offset == current.clip.pcm.size) "COMMIT" else "DATA"
            }
            "COMMIT" -> current.stage = "PLAY"
            "PLAY" -> {
                current.stage = "PLAYED"
                current.serial++
                val serial = current.serial
                handler.postDelayed({
                    if (audio === current && current.connection == connectionEpoch && current.serial == serial)
                        close("AUDIO_PLAYED_TIMEOUT")
                }, 15_000)
                return
            }
        }
        sendAudio(current)
    }

    private fun finishAudio(ok: Boolean, code: String) {
        val current = audio ?: return
        audio = null
        current.done(ok, code, if (ok) JSONObject().put("receipt", code).put("bytes", current.clip.pcm.size) else null)
    }

    fun disconnect() { close("DISCONNECTED") }

    private fun close(reason: String) {
        connectionEpoch++
        scanDone?.invoke(false, reason, null)
        stopScan()
        clearBondReceiver()
        try { gatt?.disconnect() } catch (_: Exception) {}
        try { gatt?.close() } catch (_: Exception) {}
        gatt = null
        notifications.clear()
        state = "DISCONNECTED"
        connectDone?.invoke(false, reason, null)
        connectDone = null
        finishTask(false, reason)
        finishAudio(false, reason)
    }
}
