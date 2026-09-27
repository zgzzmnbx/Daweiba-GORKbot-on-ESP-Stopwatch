package com.daweiba.gork

import android.content.Context
import android.speech.tts.TextToSpeech
import android.speech.tts.Voice
import org.json.JSONObject
import java.util.Locale

/** Uses only a Chinese voice that declares no network requirement. */
class LocalSpeech(private val context: Context) {
    private var engine: TextToSpeech? = null
    private var voice: Voice? = null
    private var loading = false
    private val waiters = mutableListOf<(Boolean, String, JSONObject?) -> Unit>()

    fun status(done: (Boolean, String, JSONObject?) -> Unit) {
        if (voice != null) { done(true, "READY", JSONObject().put("available", true).put("voice", voice!!.name)); return }
        waiters += done
        if (loading) return
        engine?.shutdown()
        engine = null
        loading = true
        engine = TextToSpeech(context) { result ->
            loading = false
            val tts = engine
            if (result != TextToSpeech.SUCCESS || tts == null) {
                finish(false, "TTS_ENGINE_UNAVAILABLE"); return@TextToSpeech
            }
            voice = tts.voices?.firstOrNull { candidate ->
                candidate.locale.language == Locale.CHINESE.language && !candidate.isNetworkConnectionRequired
            }
            val chosen = voice
            if (chosen == null || tts.setVoice(chosen) != TextToSpeech.SUCCESS) {
                voice = null
                finish(false, "LOCAL_CHINESE_VOICE_UNAVAILABLE")
            } else finish(true, "READY")
        }
    }

    private fun finish(ok: Boolean, code: String) {
        val result = if (ok) JSONObject().put("available", true).put("voice", voice?.name) else null
        val callbacks = waiters.toList()
        waiters.clear()
        callbacks.forEach { it(ok, code, result) }
    }

    fun speak(text: String, done: (Boolean, String, JSONObject?) -> Unit) {
        if (text.isBlank() || text.length > 300) { done(false, "INVALID_TEXT", null); return }
        status { ok, code, _ ->
            if (!ok) { done(false, code, null); return@status }
            val queued = engine?.speak(text, TextToSpeech.QUEUE_FLUSH, null, "gork-local") == TextToSpeech.SUCCESS
            done(queued, if (queued) "QUEUED" else "TTS_FAILED", if (queued) JSONObject().put("queued", true) else null)
        }
    }

    fun stop() { engine?.stop() }
    fun shutdown() { engine?.stop(); engine?.shutdown(); engine = null; voice = null }
}
