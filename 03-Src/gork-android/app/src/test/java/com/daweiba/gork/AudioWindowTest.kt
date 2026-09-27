package com.daweiba.gork

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class AudioWindowTest {
    @Test fun sendsAtMostThreeAndCountsOnlyDeviceAcknowledgements() {
        val window = AudioWindow(16, 4)
        assertEquals(AudioWindow.Block(0, 4), window.next())
        assertEquals(AudioWindow.Block(4, 8), window.next())
        assertEquals(AudioWindow.Block(8, 12), window.next())
        assertNull(window.next())
        assertEquals(12, window.sentBytes)
        assertEquals(0, window.confirmedBytes)
        assertFalse(window.acknowledge(16))
        assertEquals(0, window.confirmedBytes)
        assertTrue(window.acknowledge(8))
        assertEquals(8, window.confirmedBytes)
        assertEquals(AudioWindow.Block(12, 16), window.next())
        assertTrue(window.acknowledge(16))
        assertTrue(window.complete)
        assertFalse(window.acknowledge(4))
    }
}
