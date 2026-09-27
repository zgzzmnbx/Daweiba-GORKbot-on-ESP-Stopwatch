package com.daweiba.gork

import org.junit.Assert.assertEquals
import org.junit.Assert.assertThrows
import org.junit.Test
import java.nio.ByteBuffer
import java.nio.ByteOrder

class WaveToWatchTest {
    private fun wav(rate: Int, channels: Int, frames: Int, bits: Int = 16): ByteArray {
        val sampleBytes = bits / 8
        val dataSize = frames * channels * sampleBytes
        val bytes = ByteBuffer.allocate(44 + dataSize).order(ByteOrder.LITTLE_ENDIAN)
        bytes.put("RIFF".toByteArray()).putInt(36 + dataSize).put("WAVEfmt ".toByteArray())
        bytes.putInt(16).putShort(1).putShort(channels.toShort()).putInt(rate)
        bytes.putInt(rate * channels * sampleBytes).putShort((channels * sampleBytes).toShort()).putShort(bits.toShort())
        bytes.put("data".toByteArray()).putInt(dataSize)
        repeat(frames) { repeat(channels) { channel ->
            if (bits == 16) bytes.putShort((if (channel == 0) 1000 else 3000).toShort())
            else bytes.put(127.toByte())
        } }
        return bytes.array()
    }

    @Test fun downsamplesAndMixesStereoWithoutBoost() {
        val clip = WaveToWatch.convert(wav(48000, 2, 4800))
        assertEquals(16000, clip.rate)
        assertEquals(3200, clip.pcm.size)
        assertEquals(2000, ByteBuffer.wrap(clip.pcm).order(ByteOrder.LITTLE_ENDIAN).short.toInt())
    }

    @Test fun preservesTwentyFourKhzMonoAndTenSecondLimit() {
        val clip = WaveToWatch.convert(wav(24000, 1, 240000))
        assertEquals(24000, clip.rate)
        assertEquals(480000, clip.pcm.size)
        assertThrows(IllegalArgumentException::class.java) { WaveToWatch.convert(wav(24000, 1, 240001)) }
    }

    @Test fun rejectsUnsupportedBitDepthAndTruncation() {
        assertThrows(IllegalArgumentException::class.java) { WaveToWatch.convert(wav(16000, 1, 1600, 8)) }
        val full = wav(16000, 1, 1600)
        assertThrows(IllegalArgumentException::class.java) { WaveToWatch.convert(full.copyOf(full.size - 2)) }
    }
}
