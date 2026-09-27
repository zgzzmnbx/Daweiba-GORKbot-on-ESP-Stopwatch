package com.daweiba.gork

import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertThrows
import org.junit.Test
import java.nio.ByteBuffer
import java.nio.ByteOrder

class WavPcm16Test {
    private fun wav(samples: Int = 1600, rate: Int = 16000, channels: Int = 1): ByteArray {
        val pcm = ByteArray(samples * channels * 2)
        val bytes = ByteBuffer.allocate(44 + pcm.size).order(ByteOrder.LITTLE_ENDIAN)
        bytes.put("RIFF".toByteArray()).putInt(36 + pcm.size).put("WAVEfmt ".toByteArray())
        bytes.putInt(16).putShort(1).putShort(channels.toShort()).putInt(rate)
        bytes.putInt(rate * channels * 2).putShort((channels * 2).toShort()).putShort(16)
        bytes.put("data".toByteArray()).putInt(pcm.size).put(pcm)
        return bytes.array()
    }

    @Test fun acceptsExactlyPointOneSecondMonoPcmAndPreservesBytes() {
        val clip = WavPcm16.read(wav())
        assertEquals(16000, clip.rate)
        assertEquals(0.1, clip.seconds, 0.00001)
        assertArrayEquals(ByteArray(3200), clip.pcm)
    }

    @Test fun rejectsTruncatedAndUnsupportedInput() {
        val valid = wav()
        assertThrows(IllegalArgumentException::class.java) { WavPcm16.read(valid.copyOf(valid.size - 1)) }
        assertThrows(IllegalArgumentException::class.java) { WavPcm16.read(wav(rate = 22050)) }
        assertThrows(IllegalArgumentException::class.java) { WavPcm16.read(wav(channels = 2)) }
        assertThrows(IllegalArgumentException::class.java) { WavPcm16.read(wav(samples = 1599)) }
    }

    @Test fun acceptsTwentyFourKhzAndTenSecondBoundary() {
        val clip = WavPcm16.read(wav(samples = 240000, rate = 24000))
        assertEquals(24000, clip.rate)
        assertEquals(10.0, clip.seconds, 0.00001)
        assertEquals(480000, clip.pcm.size)
    }
}
