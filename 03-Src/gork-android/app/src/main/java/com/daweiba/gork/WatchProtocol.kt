package com.daweiba.gork

import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.nio.charset.StandardCharsets
import java.util.UUID

/** Wire constants mirror tools/stopwatch_ble.py, stopwatch_sound.py and stopwatch_audio.py. */
object WatchProtocol {
    val expressionService: UUID = UUID.fromString("48f1a001-8a75-4db6-9c18-590f7e9b0a01")
    val expressionCommand: UUID = UUID.fromString("48f1a002-8a75-4db6-9c18-590f7e9b0a01")
    val expressionStatus: UUID = UUID.fromString("48f1a003-8a75-4db6-9c18-590f7e9b0a01")
    val soundService: UUID = UUID.fromString("48f1c001-8a75-4db6-9c18-590f7e9b0a01")
    val soundCommand: UUID = UUID.fromString("48f1c002-8a75-4db6-9c18-590f7e9b0a01")
    val soundEvent: UUID = UUID.fromString("48f1c003-8a75-4db6-9c18-590f7e9b0a01")
    val audioService: UUID = UUID.fromString("48f1b001-8a75-4db6-9c18-590f7e9b0a01")
    val audioInput: UUID = UUID.fromString("48f1b002-8a75-4db6-9c18-590f7e9b0a01")
    val audioEvent: UUID = UUID.fromString("48f1b003-8a75-4db6-9c18-590f7e9b0a01")

    val expressions = setOf(
        "idle", "listening", "thinking", "happy", "happy-work", "excited", "curious",
        "confused", "angry", "surprised", "sad", "sleepy", "dizzy", "sleeping",
        "waking", "searching", "working", "bored", "suspicious", "proud", "shy",
        "laughing", "scared", "celebrate"
    )

    data class ExpectedPacket(val bytes: ByteArray, val status: String)

    fun expression(name: String, mode: String = "once"): ExpectedPacket {
        require(name in expressions) { "未知表情" }
        require(mode in setOf("once", "loop", "pingpong")) { "未知播放方式" }
        val command = if (mode == "once") name else "$mode $name"
        val bytes = command.toByteArray(StandardCharsets.US_ASCII)
        require(bytes.size <= 20) { "表情命令超长" }
        val reported = when (name) { "sleepy" -> "drowsy"; "dizzy" -> "playful"; else -> name }
        return ExpectedPacket(bytes, "OK:${reported.uppercase()}")
    }

    fun bubble(text: String, id: Int): List<ExpectedPacket> {
        require(id in 1..255) { "文字事务号无效" }
        val value = text.trim()
        require(value.isNotEmpty() && value.codePoints().allMatch { !Character.isISOControl(it) }) {
            "文字不能为空或包含控制字符"
        }
        require(value.length <= 24 && value.codePoints().allMatch { it <= 0xffff }) {
            "最多 24 字，暂不支持 emoji"
        }
        val bytes = value.toByteArray(StandardCharsets.UTF_8)
        require(bytes.size <= 72) { "UTF-8 文字最多 72 字节" }
        val result = mutableListOf(ExpectedPacket(byteArrayOf(0xf0.toByte(), id.toByte(), bytes.size.toByte()), "OK:BEGIN:$id"))
        bytes.asList().chunked(17).forEachIndexed { index, chunk ->
            result += ExpectedPacket(byteArrayOf(0xf1.toByte(), id.toByte(), index.toByte()) + chunk.toByteArray(), "OK:PART:$id:$index")
        }
        result += ExpectedPacket(byteArrayOf(0xf2.toByte(), id.toByte()), "OK:TEXT:$id")
        return result
    }

    fun clear(): ExpectedPacket = ExpectedPacket(byteArrayOf(0xf3.toByte()), "OK:CLEAR")

    data class SoundFrame(val operation: Int, val id: Int, val value: Long = 0, val argument: Int = 0) {
        fun encode(): ByteArray {
            require(id in 1..65535 && value in 0..0xffffffffL && argument in 0..255)
            return ByteBuffer.allocate(9).order(ByteOrder.LITTLE_ENDIAN)
                .put(1).put(operation.toByte()).putShort(id.toShort()).putInt(value.toInt())
                .put(argument.toByte()).array()
        }

        companion object {
            fun decode(bytes: ByteArray): SoundFrame {
                require(bytes.size == 9) { "短音回执长度错误" }
                val buffer = ByteBuffer.wrap(bytes).order(ByteOrder.LITTLE_ENDIAN)
                require(buffer.get().toInt() == 1) { "短音协议版本错误" }
                val operation = buffer.get().toInt() and 0xff
                val id = buffer.short.toInt() and 0xffff
                require(id != 0) { "短音回执事务号无效" }
                return SoundFrame(operation, id, buffer.int.toLong() and 0xffffffffL, buffer.get().toInt() and 0xff)
            }
        }
    }

    fun soundTerminal(requestOperation: Int, eventOperation: Int): Boolean = when (requestOperation) {
        3 -> eventOperation == 0x82 || eventOperation == 0x83
        4 -> eventOperation == 0x83
        5 -> eventOperation == 0x82
        else -> false
    }

    fun soundPlay(id: Int, soundId: Int): ByteArray {
        require(soundId in 1..6)
        return SoundFrame(3, id, argument = soundId).encode()
    }

    fun soundVolume(id: Int, volume: Int): ByteArray {
        require(volume in 0..100)
        return SoundFrame(5, id, value = volume.toLong()).encode()
    }

    data class AudioPacket(val operation: Int, val transfer: Int, val epoch: Long, val value: Long = 0, val data: ByteArray = byteArrayOf()) {
        fun encode(): ByteArray {
            require(transfer in 1..65535 && epoch in 0..0xffffffffL && value in 0..0xffffffffL && data.size <= 232)
            return ByteBuffer.allocate(12 + data.size).order(ByteOrder.LITTLE_ENDIAN)
                .put(1).put(operation.toByte()).putShort(transfer.toShort()).putInt(epoch.toInt())
                .putInt(value.toInt()).put(data).array()
        }

        companion object {
            fun decode(bytes: ByteArray): AudioPacket {
                require(bytes.size in 12..244) { "音频包长度无效" }
                val input = ByteBuffer.wrap(bytes).order(ByteOrder.LITTLE_ENDIAN)
                require(input.get().toInt() == 1) { "音频协议版本无效" }
                val operation = input.get().toInt() and 0xff
                val transfer = input.short.toInt() and 0xffff
                require(transfer != 0) { "音频传输号无效" }
                val epoch = input.int.toLong() and 0xffffffffL
                val value = input.int.toLong() and 0xffffffffL
                val payload = ByteArray(input.remaining())
                input.get(payload)
                return AudioPacket(operation, transfer, epoch, value, payload)
            }
        }
    }

    fun pcmBeginMetadata(byteCount: Int): ByteArray {
        require(byteCount in 3200..480000 && byteCount % 2 == 0)
        return ByteBuffer.allocate(4).order(ByteOrder.LITTLE_ENDIAN).putInt(byteCount).array()
    }
}
