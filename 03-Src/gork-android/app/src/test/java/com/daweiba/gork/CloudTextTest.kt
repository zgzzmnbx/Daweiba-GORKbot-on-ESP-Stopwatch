package com.daweiba.gork

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class CloudTextTest {
    @Test fun endpointRequiresHttpsWithoutCredentialsOrRedirectInputs() {
        assertTrue(CloudText.validEndpoint(CloudText.DEFAULT_ENDPOINT))
        assertFalse(CloudText.validEndpoint("http://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"))
        assertFalse(CloudText.validEndpoint("https://user:secret@example.com/v1/chat/completions"))
        assertFalse(CloudText.validEndpoint("https://example.com/v1/chat/completions?key=secret"))
        assertFalse(CloudText.validEndpoint("https://example.com/v1/chat/completions#fragment"))
        assertFalse(CloudText.validEndpoint("https://example.com"))
    }
}
