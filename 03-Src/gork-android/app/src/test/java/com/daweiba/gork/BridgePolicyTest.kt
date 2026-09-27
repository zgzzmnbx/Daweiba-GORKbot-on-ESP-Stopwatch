package com.daweiba.gork

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class BridgePolicyTest {
    @Test fun rejectsStalePageExceptCapabilityHandshake() {
        assertTrue(BridgePolicy.validGeneration(0, 3, "capabilities.get"))
        assertTrue(BridgePolicy.validGeneration(3, 3, "device.scan"))
        assertFalse(BridgePolicy.validGeneration(2, 3, "device.scan"))
        assertFalse(BridgePolicy.validGeneration(0, 3, "task.cancel"))
    }
}
