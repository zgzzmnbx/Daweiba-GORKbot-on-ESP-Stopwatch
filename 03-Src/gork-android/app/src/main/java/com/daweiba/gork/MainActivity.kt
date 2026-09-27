package com.daweiba.gork

import android.app.Activity
import android.Manifest
import android.content.pm.PackageManager
import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.graphics.Bitmap
import android.webkit.WebResourceRequest
import android.webkit.WebResourceResponse
import android.webkit.RenderProcessGoneDetail
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.TextView
import androidx.webkit.WebMessageCompat
import androidx.webkit.WebViewAssetLoader
import androidx.webkit.WebViewCompat
import androidx.webkit.WebViewFeature
import org.json.JSONObject
import java.io.ByteArrayInputStream
import java.io.ByteArrayOutputStream

class MainActivity : Activity() {
    private lateinit var webView: WebView
    private val origin = "https://appassets.androidplatform.net"
    private val page = "$origin/assets/index.html"
    private val prefs by lazy { getSharedPreferences("gork", MODE_PRIVATE) }
    private val ble by lazy { WatchBleController(this) }
    private val speech by lazy { LocalSpeech(this) }
    private var permissionDone: ((Boolean) -> Unit)? = null
    private var webViewDestroyed = false
    private var audioPickDone: ((Boolean, String, JSONObject?) -> Unit)? = null
    private var pageGeneration = 0

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val loader = WebViewAssetLoader.Builder()
            .addPathHandler("/assets/", WebViewAssetLoader.AssetsPathHandler(this))
            .build()
        webView = WebView(this)
        webView.settings.apply {
            javaScriptEnabled = true
            allowFileAccess = false
            allowContentAccess = false
            domStorageEnabled = false
            javaScriptCanOpenWindowsAutomatically = false
        }
        webView.webViewClient = object : WebViewClient() {
            override fun onPageStarted(view: WebView, url: String?, favicon: Bitmap?) {
                pageGeneration++
                ble.disconnect()
                speech.stop()
                audioPickDone?.invoke(false, "PAGE_RELOADED", null)
                audioPickDone = null
            }
            override fun onRenderProcessGone(view: WebView, detail: RenderProcessGoneDetail): Boolean {
                ble.disconnect()
                setContentView(TextView(this@MainActivity).apply {
                    text = "Gork 页面进程已退出，所有 Watch 任务已停止。请重新打开应用。"
                    textSize = 18f
                    setPadding(32, 40, 32, 40)
                })
                view.destroy()
                webViewDestroyed = true
                return true
            }
            override fun shouldInterceptRequest(view: WebView, request: WebResourceRequest): WebResourceResponse {
                val uri = request.url
                if (uri.scheme == "https" && uri.host == "appassets.androidplatform.net" &&
                    uri.path?.startsWith("/assets/") == true) {
                    return loader.shouldInterceptRequest(uri) ?: forbidden()
                }
                return forbidden()
            }

            override fun shouldOverrideUrlLoading(view: WebView, request: WebResourceRequest): Boolean =
                request.url.toString() != page
        }
        if (WebViewFeature.isFeatureSupported(WebViewFeature.WEB_MESSAGE_LISTENER)) {
            WebViewCompat.addWebMessageListener(webView, "gorkNative", setOf(origin)) { _, message, sourceOrigin, isMainFrame, reply ->
                if (!BridgePolicy.allowedFrame(sourceOrigin, isMainFrame) || message.type != WebMessageCompat.TYPE_STRING) {
                    reply.postMessage(BridgePolicy.error(null, "FORBIDDEN"))
                    return@addWebMessageListener
                }
                handleMessage(message.data) { reply.postMessage(it) }
            }
        }
        setContentView(webView)
        webView.loadUrl(page)
    }

    private fun handleMessage(raw: String?, respond: (String) -> Unit) {
        if (raw == null || raw.toByteArray(Charsets.UTF_8).size > 16_384) {
            respond(BridgePolicy.error(null, "BAD_REQUEST")); return
        }
        val request = try { JSONObject(raw) } catch (_: Exception) {
            respond(BridgePolicy.error(null, "BAD_REQUEST")); return
        }
        val id = request.optString("requestId")
        val method = request.optString("method")
        val generation = request.optInt("generation", -1)
        if (!BridgePolicy.validRequest(id, method, generation)) {
            respond(BridgePolicy.error(id, "BAD_REQUEST")); return
        }
        if (!BridgePolicy.validGeneration(generation, pageGeneration, method)) {
            respond(BridgePolicy.error(id, "STALE_GENERATION")); return
        }
        val params = request.optJSONObject("params") ?: JSONObject()
        val complete: (Boolean, String, JSONObject?) -> Unit = { ok, code, result ->
            val payload = if (generation != pageGeneration && method != "capabilities.get")
                BridgePolicy.error(id, "STALE_GENERATION")
            else if (ok) BridgePolicy.success(id, result ?: JSONObject())
            else BridgePolicy.error(id, code)
            respond(payload)
        }
        when (request.getString("method")) {
            "speech.local.status" -> { speech.status(complete); return }
            "speech.local.speak" -> { speech.speak(params.optString("text"), complete); return }
            "speech.local.stop" -> { speech.stop(); complete(true, "LOCAL_STOPPED", JSONObject()); return }
            "device.scan" -> {
                ensureBluetoothPermission { allowed ->
                    if (allowed) ble.scan { ok, code, devices ->
                        complete(ok, code, if (devices != null) JSONObject().put("devices", devices) else null)
                    } else complete(false, "PERMISSION_DENIED", null)
                }
                return
            }
            "device.connect" -> {
                if (!hasBluetoothPermission()) complete(false, "PERMISSION_REQUIRED", null)
                else ble.connect(params.optString("address"), complete)
                return
            }
            "device.disconnect" -> { ble.disconnect(); complete(true, "OK", ble.snapshot()); return }
            "character.play" -> { ble.expression(params.optString("name"), params.optString("mode", "once"), complete); return }
            "character.showText" -> { ble.bubble(params.optString("text"), complete); return }
            "character.clear" -> { ble.clear(complete); return }
            "sound.play" -> { ble.sound(3, params.optInt("soundId"), complete); return }
            "sound.volume" -> { ble.sound(5, params.optInt("volume"), complete); return }
            "sound.stop" -> { ble.sound(4, 0, complete); return }
            "audio.pickAndPlayPcm" -> { pickAudio(complete); return }
            "task.cancel" -> { ble.disconnect(); complete(true, "LOCAL_STOPPED", ble.snapshot()); return }
        }
        val result = when (request.getString("method")) {
            "capabilities.get" -> JSONObject()
                .put("android", true).put("ble", true).put("speech", true)
                .put("avatar", true).put("version", "0.1.1-dev").put("generation", pageGeneration)
            "state.get" -> ble.snapshot().put("generation", request.getInt("generation"))
            "preferences.get" -> preferences()
            "preferences.set" -> savePreferences(params)
            else -> { respond(BridgePolicy.error(id, "UNKNOWN_METHOD")); return }
        }
        respond(BridgePolicy.success(id, result))
    }

    private fun pickAudio(done: (Boolean, String, JSONObject?) -> Unit) {
        if (!ble.snapshot().optBoolean("ready")) { done(false, "NOT_READY", null); return }
        if (audioPickDone != null) { done(false, "AUDIO_PICK_BUSY", null); return }
        audioPickDone = done
        try {
            startActivityForResult(Intent(Intent.ACTION_OPEN_DOCUMENT).apply {
                addCategory(Intent.CATEGORY_OPENABLE)
                type = "audio/*"
            }, 31)
        } catch (_: Exception) {
            audioPickDone = null
            done(false, "AUDIO_PICK_UNAVAILABLE", null)
        }
    }

    @Deprecated("Activity result API is retained for this minimal Activity")
    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        super.onActivityResult(requestCode, resultCode, data)
        if (requestCode != 31) return
        val done = audioPickDone ?: return
        audioPickDone = null
        if (resultCode != RESULT_OK || data?.data == null) {
            done(false, "AUDIO_PICK_CANCELLED", null); return
        }
        val clip = try {
            val source = contentResolver.openInputStream(data.data!!) ?: error("empty stream")
            val bytes = source.use { input ->
                val output = ByteArrayOutputStream()
                val buffer = ByteArray(8192)
                while (output.size() <= 484096) {
                    val count = input.read(buffer, 0, minOf(buffer.size, 484097 - output.size()))
                    if (count < 0) break
                    output.write(buffer, 0, count)
                }
                output.toByteArray()
            }
            WavPcm16.read(bytes)
        } catch (_: Exception) {
            done(false, "AUDIO_WAV_INVALID_PCM16_MONO_16_OR_24KHZ_0_1_TO_10S", null); return
        }
        ble.playPcm(clip, done)
    }

    private fun hasBluetoothPermission(): Boolean =
        checkSelfPermission(Manifest.permission.BLUETOOTH_SCAN) == PackageManager.PERMISSION_GRANTED &&
            checkSelfPermission(Manifest.permission.BLUETOOTH_CONNECT) == PackageManager.PERMISSION_GRANTED

    private fun ensureBluetoothPermission(done: (Boolean) -> Unit) {
        if (hasBluetoothPermission()) { done(true); return }
        if (permissionDone != null) { done(false); return }
        permissionDone = done
        requestPermissions(arrayOf(Manifest.permission.BLUETOOTH_SCAN, Manifest.permission.BLUETOOTH_CONNECT), 20)
    }

    override fun onRequestPermissionsResult(requestCode: Int, permissions: Array<out String>, grantResults: IntArray) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        if (requestCode == 20) {
            permissionDone?.invoke(hasBluetoothPermission())
            permissionDone = null
        }
    }

    override fun onResume() {
        super.onResume()
        if (::webView.isInitialized && !hasBluetoothPermission()) ble.disconnect()
    }

    private fun preferences(): JSONObject = JSONObject()
        .put("theme", prefs.getString("theme", "light"))
        .put("appearance", prefs.getString("appearance", "gork"))
        .put("draft", prefs.getString("draft", ""))
        .put("target", prefs.getString("target", "phone"))

    private fun savePreferences(params: JSONObject): JSONObject {
        val allowed = setOf("theme", "appearance", "draft", "target")
        val edit = prefs.edit()
        params.keys().forEach { key ->
            if (key in allowed) {
                val value = params.optString(key)
                if (value.length <= 1000) edit.putString(key, value)
            }
        }
        edit.apply()
        return preferences()
    }

    private fun forbidden() = WebResourceResponse(
        "text/plain", "UTF-8", 403, "Forbidden", emptyMap(), ByteArrayInputStream(byteArrayOf())
    )

    override fun onDestroy() {
        audioPickDone?.invoke(false, "ACTIVITY_DESTROYED", null)
        audioPickDone = null
        ble.disconnect()
        speech.shutdown()
        if (!webViewDestroyed) webView.destroy()
        super.onDestroy()
    }
}

object BridgePolicy {
    private const val ORIGIN = "https://appassets.androidplatform.net"
    fun allowedFrame(source: Uri, main: Boolean): Boolean = main && source.toString() == ORIGIN
    fun validRequest(id: String, method: String, generation: Int): Boolean =
        id.length in 1..64 && id.all { it.isLetterOrDigit() || it in "-_" } &&
            method.length in 1..64 && generation >= 0
    fun validGeneration(request: Int, current: Int, method: String): Boolean =
        request == current || (method == "capabilities.get" && request == 0)
    fun error(id: String?, code: String): String = JSONObject()
        .put("requestId", id ?: JSONObject.NULL).put("ok", false).put("error", code).toString()
    fun success(id: String, result: JSONObject): String = JSONObject()
        .put("requestId", id).put("ok", true).put("result", result).toString()
}
