package com.daweiba.gork

import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.nio.charset.StandardCharsets

/** Strict PCM16 mono input for the Watch's 0.1–10 second playback protocol. */
object WavPcm16 {
    data class Clip(val pcm: ByteArray, val rate: Int) {
        val seconds: Double get() = pcm.size / 2.0 / rate
    }

    fun read(bytes: ByteArray): Clip {
        require(bytes.size in 44..484096) { "WAV 文件大小不在设备范围内" }
        require(tag(bytes, 0) == "RIFF" && tag(bytes, 8) == "WAVE") { "需要 RIFF/WAVE 文件" }
        val input = ByteBuffer.wrap(bytes).order(ByteOrder.LITTLE_ENDIAN)
        val riffLength = input.getInt(4).toLong() and 0xffffffffL
        require(riffLength + 8 == bytes.size.toLong()) { "WAV 长度与文件内容不一致" }
        var offset = 12
        var rate = 0
        var data: ByteArray? = null
        while (offset + 8 <= bytes.size) {
            val name = tag(bytes, offset)
            val size = input.getInt(offset + 4).toLong() and 0xffffffffL
            val start = offset + 8
            require(size <= bytes.size - start.toLong()) { "WAV 分块被截断" }
            if (name == "fmt ") {
                require(rate == 0 && size >= 16) { "WAV fmt 分块无效" }
                require(input.getShort(start).toInt() == 1 && input.getShort(start + 2).toInt() == 1) {
                    "需要 PCM 单声道 WAV"
                }
                rate = input.getInt(start + 4)
                require(rate == 16000 || rate == 24000) { "需要 16/24 kHz WAV" }
                require(input.getInt(start + 8) == rate * 2 && input.getShort(start + 12).toInt() == 2 &&
                    input.getShort(start + 14).toInt() == 16) { "需要 PCM16 单声道 WAV" }
            } else if (name == "data") {
                require(data == null && size <= 480000 && size % 2L == 0L) { "WAV 音频长度无效" }
                data = bytes.copyOfRange(start, start + size.toInt())
            }
            offset = start + size.toInt() + (size.toInt() and 1)
        }
        require(offset == bytes.size && rate != 0 && data != null) { "WAV 分块不完整" }
        val pcm = data
        require(pcm.size / 2 in rate / 10..rate * 10) { "WAV 必须为 0.1–10 秒，不得截尾" }
        return Clip(pcm, rate)
    }

    private fun tag(bytes: ByteArray, offset: Int): String =
        String(bytes, offset, 4, StandardCharsets.US_ASCII)
}
