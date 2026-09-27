package com.daweiba.gork

import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertThrows
import org.junit.Test

class WatchProtocolTest {
    private fun hex(value: String): ByteArray = value.chunked(2).map { it.toInt(16).toByte() }.toByteArray()

    @Test fun textMatchesPythonGoldenVector() {
        val packets = WatchProtocol.bubble("你好Gork", 7)
        val expected = listOf("f0070a", "f10700e4bda0e5a5bd476f726b", "f207")
        packets.zip(expected).forEach { (packet, bytes) -> assertArrayEquals(hex(bytes), packet.bytes) }
        assertEquals(listOf("OK:BEGIN:7", "OK:PART:7:0", "OK:TEXT:7"), packets.map { it.status })
    }

    @Test fun soundAndAudioUseLittleEndian() {
        assertArrayEquals(hex("010334120000000003"), WatchProtocol.soundPlay(0x1234, 3))
        assertArrayEquals(hex("010534123700000000"), WatchProtocol.soundVolume(0x1234, 55))
        assertArrayEquals(hex("01010df078563412efcdab90"), WatchProtocol.AudioPacket(1, 0xf00d, 0x12345678, 0x90abcdef).encode())
        val decoded=WatchProtocol.SoundFrame.decode(hex("018234120000000003"))
        assertEquals(0x1234,decoded.id)
        assertEquals(0x82,decoded.operation)
        assertEquals(true,WatchProtocol.soundTerminal(3,decoded.operation))
        assertEquals(false,WatchProtocol.soundTerminal(4,decoded.operation))
    }

    @Test fun rejectsUnsupportedTextAndOutOfRangeSound() {
        assertThrows(IllegalArgumentException::class.java) { WatchProtocol.bubble("😀", 1) }
        assertThrows(IllegalArgumentException::class.java) { WatchProtocol.bubble("a".repeat(25), 1) }
        assertThrows(IllegalArgumentException::class.java) { WatchProtocol.bubble("中".repeat(25), 1) }
        assertThrows(IllegalArgumentException::class.java) { WatchProtocol.soundVolume(1, 101) }
    }

    @Test fun pcmFramesRoundTripAndRejectTruncation() {
        val raw = WatchProtocol.AudioPacket(5, 0xf00e, 0x12345678, 3200,
            hex("34127856")).encode()
        assertArrayEquals(hex("01050ef078563412800c000034127856"), raw)
        val decoded = WatchProtocol.AudioPacket.decode(raw)
        assertEquals(5, decoded.operation)
        assertEquals(0xf00e, decoded.transfer)
        assertEquals(3200L, decoded.value)
        assertArrayEquals(hex("34127856"), decoded.data)
        assertArrayEquals(hex("800c0000"), WatchProtocol.pcmBeginMetadata(3200))
        assertThrows(IllegalArgumentException::class.java) { WatchProtocol.AudioPacket.decode(raw.copyOf(11)) }
    }
}
