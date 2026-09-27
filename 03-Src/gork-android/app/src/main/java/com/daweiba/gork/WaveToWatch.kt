package com.daweiba.gork

import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.nio.charset.StandardCharsets
import kotlin.math.roundToInt

/** Converts complete uncompressed PCM16 WAV output from a TTS engine to Watch PCM. */
object WaveToWatch {
    fun convert(bytes: ByteArray): WavPcm16.Clip {
        require(bytes.size in 44..2_000_000) { "WAV 文件大小不受支持" }
        val input = ByteBuffer.wrap(bytes).order(ByteOrder.LITTLE_ENDIAN)
        require(tag(bytes, 0) == "RIFF" && tag(bytes, 8) == "WAVE" &&
            (input.getInt(4).toLong() and 0xffffffffL) + 8 == bytes.size.toLong()) { "需要完整 RIFF/WAVE" }
        var offset = 12
        var rate = 0
        var channels = 0
        var dataStart = -1
        var dataBytes = 0
        while (offset + 8 <= bytes.size) {
            val name = tag(bytes, offset)
            val size = input.getInt(offset + 4).toLong() and 0xffffffffL
            val start = offset + 8
            require(size <= bytes.size - start.toLong()) { "WAV 分块被截断" }
            when (name) {
                "fmt " -> {
                    require(rate == 0 && size >= 16 && input.getShort(start).toInt() == 1) {
                        "只支持非压缩 PCM WAV"
                    }
                    channels = input.getShort(start + 2).toInt()
                    rate = input.getInt(start + 4)
                    require(channels in 1..2 && rate in 8000..48000) { "WAV 声道或采样率不受支持" }
                    require(input.getShort(start + 14).toInt() == 16 &&
                        input.getInt(start + 8) == rate * channels * 2 &&
                        input.getShort(start + 12).toInt() == channels * 2) { "需要 PCM16 WAV" }
                }
                "data" -> {
                    require(dataStart < 0 && size <= 1_920_000) { "WAV 数据段无效" }
                    dataStart = start
                    dataBytes = size.toInt()
                }
            }
            offset = start + size.toInt() + (size.toInt() and 1)
        }
        require(offset == bytes.size && rate != 0 && dataStart >= 0 &&
            dataBytes % (channels * 2) == 0) { "WAV 格式或长度不完整" }
        val frames = dataBytes / (channels * 2)
        require(frames in rate / 10..rate * 10) { "语音必须为 0.1–10 秒，不得截尾" }
        val targetRate = if (rate == 24000) 24000 else 16000
        val outputFrames = ((frames.toLong() * targetRate + rate / 2) / rate).toInt()
        require(outputFrames in targetRate / 10..targetRate * 10) { "转换后的时长无效" }
        val output = ByteBuffer.allocate(outputFrames * 2).order(ByteOrder.LITTLE_ENDIAN)
        fun mono(frame: Int): Int {
            val first = input.getShort(dataStart + frame * channels * 2).toInt()
            return if (channels == 1) first
                else (first + input.getShort(dataStart + frame * channels * 2 + 2).toInt()) / 2
        }
        for (i in 0 until outputFrames) {
            val position = i.toDouble() * rate / targetRate
            val left = position.toInt().coerceAtMost(frames - 1)
            val right = (left + 1).coerceAtMost(frames - 1)
            val fraction = position - left
            val sample = (mono(left) * (1 - fraction) + mono(right) * fraction).roundToInt()
            output.putShort(sample.coerceIn(-32768, 32767).toShort())
        }
        return WavPcm16.Clip(output.array(), targetRate)
    }

    private fun tag(bytes: ByteArray, offset: Int): String =
        String(bytes, offset, 4, StandardCharsets.US_ASCII)
}
