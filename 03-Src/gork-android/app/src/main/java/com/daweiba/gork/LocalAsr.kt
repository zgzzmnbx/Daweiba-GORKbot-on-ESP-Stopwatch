package com.daweiba.gork

import android.content.Context
import android.content.Intent
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.speech.RecognitionListener
import android.speech.RecognizerIntent
import android.speech.SpeechRecognizer

/** Explicit, on-device-only speech recognition. Never falls back to a network recognizer. */
class LocalAsr(private val context: Context) {
    private val handler = Handler(Looper.getMainLooper())
    private var session: Session? = null

    private data class Session(
        val recognizer: SpeechRecognizer,
        val done: (Boolean, String, String?) -> Unit,
        var released: Boolean = false,
    )

    fun available(): Boolean = try { SpeechRecognizer.isOnDeviceRecognitionAvailable(context) }
        catch (_: Exception) { false }

    fun start(done: (Boolean, String, String?) -> Unit) {
        if (session != null) { done(false, "ASR_BUSY", null); return }
        if (!available()) { done(false, "ON_DEVICE_ASR_UNAVAILABLE", null); return }
        val recognizer = try { SpeechRecognizer.createOnDeviceSpeechRecognizer(context) }
            catch (_: Exception) { done(false, "ON_DEVICE_ASR_UNAVAILABLE", null); return }
        val current = Session(recognizer, done)
        session = current
        recognizer.setRecognitionListener(object : RecognitionListener {
            override fun onReadyForSpeech(params: Bundle?) = Unit
            override fun onBeginningOfSpeech() = Unit
            override fun onRmsChanged(rmsdB: Float) = Unit
            override fun onBufferReceived(buffer: ByteArray?) = Unit
            override fun onEndOfSpeech() = Unit
            override fun onPartialResults(partialResults: Bundle?) = Unit
            override fun onEvent(eventType: Int, params: Bundle?) = Unit
            override fun onError(error: Int) { finish(current, false, errorName(error), null) }
            override fun onResults(results: Bundle?) {
                val text = results?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)
                    ?.firstOrNull()?.trim()
                if (text.isNullOrEmpty()) finish(current, false, "ASR_NO_TEXT", null)
                else if (text.length > 300) finish(current, false, "ASR_TEXT_TOO_LONG", null)
                else finish(current, true, "READY", text)
            }
        })
        val intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
            putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
            putExtra(RecognizerIntent.EXTRA_LANGUAGE, "zh-CN")
            putExtra(RecognizerIntent.EXTRA_PREFER_OFFLINE, true)
            putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, false)
            putExtra(RecognizerIntent.EXTRA_MAX_RESULTS, 1)
        }
        try { recognizer.startListening(intent) }
        catch (_: Exception) { finish(current, false, "ASR_START_FAILED", null); return }
        handler.postDelayed({ if (session === current) finish(current, false, "ASR_TIMEOUT", null) }, 30_000)
    }

    fun release() {
        val current = session ?: return
        if (current.released) return
        current.released = true
        try { current.recognizer.stopListening() }
        catch (_: Exception) { finish(current, false, "ASR_STOP_FAILED", null) }
    }

    fun cancel() {
        val current = session ?: return
        try { current.recognizer.cancel() } catch (_: Exception) {}
        finish(current, false, "ASR_CANCELLED", null)
    }

    private fun finish(current: Session, ok: Boolean, code: String, text: String?) {
        if (session !== current) return
        session = null
        try { current.recognizer.destroy() } catch (_: Exception) {}
        current.done(ok, code, text)
    }

    private fun errorName(error: Int): String = when (error) {
        SpeechRecognizer.ERROR_AUDIO -> "ASR_MICROPHONE_ERROR"
        SpeechRecognizer.ERROR_CLIENT -> "ASR_CLIENT_ERROR"
        SpeechRecognizer.ERROR_INSUFFICIENT_PERMISSIONS -> "ASR_PERMISSION_DENIED"
        SpeechRecognizer.ERROR_LANGUAGE_NOT_SUPPORTED -> "ASR_CHINESE_NOT_SUPPORTED"
        SpeechRecognizer.ERROR_LANGUAGE_UNAVAILABLE -> "ASR_CHINESE_MODEL_MISSING"
        SpeechRecognizer.ERROR_NO_MATCH -> "ASR_NO_MATCH"
        SpeechRecognizer.ERROR_RECOGNIZER_BUSY -> "ASR_SERVICE_BUSY"
        SpeechRecognizer.ERROR_SPEECH_TIMEOUT -> "ASR_NO_SPEECH"
        SpeechRecognizer.ERROR_NETWORK, SpeechRecognizer.ERROR_NETWORK_TIMEOUT -> "ASR_SERVICE_NETWORK_ERROR"
        else -> "ASR_ERROR_$error"
    }
}
