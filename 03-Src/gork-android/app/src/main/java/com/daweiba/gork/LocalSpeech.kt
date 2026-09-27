package com.daweiba.gork

import android.content.Context
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.speech.tts.TextToSpeech
import android.speech.tts.UtteranceProgressListener
import android.speech.tts.Voice
import org.json.JSONObject
import java.io.File
import java.util.Locale
import java.util.UUID

/** Uses only a Chinese voice that declares no network requirement. */
class LocalSpeech(private val context: Context) {
    private val handler = Handler(Looper.getMainLooper())
    private var engine: TextToSpeech? = null
    private var voice: Voice? = null
    private var loading = false
    private var initSerial = 0
    private val waiters = mutableListOf<(Boolean, String, JSONObject?) -> Unit>()
    private var synthesis: SynthesisJob? = null

    init {
        context.cacheDir.listFiles()?.filter {
            it.isFile && it.name.startsWith("gork-tts-") && it.name.endsWith(".wav")
        }?.forEach { it.delete() }
    }

    private data class SynthesisJob(
        val id: String,
        val file: File,
        val done: (Boolean, String, WavPcm16.Clip?) -> Unit,
    )

    fun status(done: (Boolean, String, JSONObject?) -> Unit) {
        if (voice != null) { done(true, "READY", JSONObject().put("available", true).put("voice", voice!!.name)); return }
        waiters += done
        if (loading) return
        engine?.shutdown()
        engine = null
        loading = true
        val serial = ++initSerial
        engine = TextToSpeech(context) { result ->
            handler.post {
                if (!loading || serial != initSerial) return@post
                loading = false
                val tts = engine
                if (result != TextToSpeech.SUCCESS || tts == null) {
                    finish(false, "TTS_ENGINE_UNAVAILABLE")
                } else {
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
        }
        handler.postDelayed({
            if (loading && serial == initSerial) {
                loading = false
                engine?.shutdown()
                engine = null
                finish(false, "TTS_INIT_TIMEOUT")
            }
        }, 15_000)
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

    fun synthesize(text: String, done: (Boolean, String, WavPcm16.Clip?) -> Unit) {
        if (text.isBlank() || text.length > 300) { done(false, "INVALID_TEXT", null); return }
        if (synthesis != null) { done(false, "TTS_BUSY", null); return }
        val id = UUID.randomUUID().toString()
        val job = SynthesisJob(id, File(context.cacheDir, "gork-tts-$id.wav"), done)
        synthesis = job
        status { ok, code, _ ->
            if (synthesis !== job) return@status
            if (!ok) { finishSynthesis(job, false, code); return@status }
            val tts = engine ?: run { finishSynthesis(job, false, "TTS_ENGINE_UNAVAILABLE"); return@status }
            val listenerReady = tts.setOnUtteranceProgressListener(object : UtteranceProgressListener() {
                override fun onStart(utteranceId: String) = Unit
                override fun onDone(utteranceId: String) {
                    if (utteranceId == id) handler.post { finishSynthesis(job, true, "DONE") }
                }
                @Deprecated("Android still calls this callback on some engines")
                override fun onError(utteranceId: String) {
                    if (utteranceId == id) handler.post { finishSynthesis(job, false, "TTS_SYNTHESIS_FAILED") }
                }
                override fun onError(utteranceId: String, errorCode: Int) {
                    if (utteranceId == id) handler.post { finishSynthesis(job, false, "TTS_SYNTHESIS_ERROR_$errorCode") }
                }
                override fun onStop(utteranceId: String, interrupted: Boolean) {
                    if (utteranceId == id) handler.post { finishSynthesis(job, false, "TTS_SYNTHESIS_STOPPED") }
                }
            }) == TextToSpeech.SUCCESS
            if (!listenerReady) { finishSynthesis(job, false, "TTS_LISTENER_UNAVAILABLE"); return@status }
            val queued = try { tts.synthesizeToFile(text, Bundle.EMPTY, job.file, id) == TextToSpeech.SUCCESS }
                catch (_: Exception) { false }
            if (!queued)
                finishSynthesis(job, false, "TTS_SYNTHESIS_NOT_QUEUED")
            else handler.postDelayed({
                if (synthesis === job) {
                    tts.stop()
                    finishSynthesis(job, false, "TTS_SYNTHESIS_TIMEOUT")
                }
            }, 45_000)
        }
    }

    private fun finishSynthesis(job: SynthesisJob, ok: Boolean, code: String) {
        if (synthesis !== job) return
        synthesis = null
        val clip = if (ok) try {
            require(job.file.length() in 44..2_000_000) { "TTS output size invalid" }
            WaveToWatch.convert(job.file.readBytes())
        } catch (_: Exception) { null } else null
        job.file.delete()
        job.done(clip != null, if (clip != null) code else if (ok) "TTS_WAV_UNSUPPORTED_OR_TOO_LONG" else code, clip)
    }

    fun stop() {
        synthesis?.let { finishSynthesis(it, false, "TTS_SYNTHESIS_CANCELLED") }
        engine?.stop()
    }
    fun shutdown() {
        stop()
        if (loading) { loading = false; initSerial++; finish(false, "TTS_SHUTDOWN") }
        engine?.shutdown()
        engine = null
        voice = null
    }
}
