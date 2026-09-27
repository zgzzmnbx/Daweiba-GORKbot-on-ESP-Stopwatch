package com.daweiba.gork

import android.content.Context
import android.content.SharedPreferences
import android.os.Handler
import android.os.Looper
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.Base64
import org.json.JSONObject
import java.io.ByteArrayOutputStream
import java.net.URI
import java.nio.charset.StandardCharsets
import java.security.KeyStore
import java.util.concurrent.Executors
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec
import javax.net.ssl.HttpsURLConnection

/** User configured text provider. All network and credential operations stay outside the WebView. */
class CloudText(context: Context) {
    private val prefs: SharedPreferences = context.getSharedPreferences("gork_cloud", Context.MODE_PRIVATE)
    private val main = Handler(Looper.getMainLooper())
    private val worker = Executors.newSingleThreadExecutor()
    @Volatile private var epoch = 0
    private var pending: ((Boolean, String, JSONObject?) -> Unit)? = null
    @Volatile private var connection: HttpsURLConnection? = null

    fun settings(): JSONObject = JSONObject()
        .put("endpoint", prefs.getString("endpoint", DEFAULT_ENDPOINT))
        .put("model", prefs.getString("model", "qwen-plus"))
        .put("timeoutSeconds", prefs.getInt("timeoutSeconds", 35))
        .put("hasKey", !prefs.getString("encryptedKey", null).isNullOrBlank())
        .put("allowAudioUpload", prefs.getBoolean("allowAudioUpload", false))
        .put("allowSynthesisTextUpload", prefs.getBoolean("allowSynthesisTextUpload", false))
        .put("allowAnswerTextUpload", prefs.getBoolean("allowAnswerTextUpload", false))
        .put("allowPromptUpload", prefs.getBoolean("allowPromptUpload", false))

    fun saveSettings(input: JSONObject): String? {
        val endpoint = input.optString("endpoint")
        val model = input.optString("model")
        val timeout = input.optInt("timeoutSeconds", 35)
        if (!validEndpoint(endpoint)) return "INVALID_HTTPS_ENDPOINT"
        if (!model.matches(Regex("[A-Za-z0-9._/-]{1,80}"))) return "INVALID_MODEL"
        if (timeout !in 10..60) return "INVALID_TIMEOUT"
        if (pending != null) cancel()
        val saved = prefs.edit()
            .putString("endpoint", endpoint)
            .putString("model", model)
            .putInt("timeoutSeconds", timeout)
            .commit()
        return if (saved) null else "SETTINGS_SAVE_FAILED"
    }

    fun saveConsents(input: JSONObject): Boolean {
        val changedToOff = listOf("allowAudioUpload", "allowSynthesisTextUpload",
            "allowAnswerTextUpload", "allowPromptUpload").any { key ->
            prefs.getBoolean(key, false) && !input.optBoolean(key, false)
        }
        val saved = prefs.edit()
            .putBoolean("allowAudioUpload", input.optBoolean("allowAudioUpload", false))
            .putBoolean("allowSynthesisTextUpload", input.optBoolean("allowSynthesisTextUpload", false))
            .putBoolean("allowAnswerTextUpload", input.optBoolean("allowAnswerTextUpload", false))
            .putBoolean("allowPromptUpload", input.optBoolean("allowPromptUpload", false))
            .commit()
        if (changedToOff) cancel()
        return saved
    }

    fun saveKey(value: String): String? {
        if (value.length !in 8..256 || value.any { it.isWhitespace() }) return "INVALID_API_KEY"
        if (pending != null) cancel()
        return try {
            val cipher = Cipher.getInstance("AES/GCM/NoPadding")
            cipher.init(Cipher.ENCRYPT_MODE, secretKey())
            val encrypted = cipher.iv + cipher.doFinal(value.toByteArray(StandardCharsets.UTF_8))
            if (prefs.edit().putString("encryptedKey", Base64.encodeToString(encrypted, Base64.NO_WRAP)).commit())
                null else "KEY_SAVE_FAILED"
        } catch (_: Exception) { "KEYSTORE_UNAVAILABLE" }
    }

    fun clearKey(): Boolean {
        cancel()
        return prefs.edit().remove("encryptedKey").commit()
    }

    fun ask(text: String, done: (Boolean, String, JSONObject?) -> Unit) {
        if (pending != null) { done(false, "AI_BUSY", null); return }
        val message = text.trim()
        if (message.isEmpty() || message.length > 300 || message.toByteArray().size > 1200) {
            done(false, "AI_TEXT_LIMIT", null); return
        }
        if (!prefs.getBoolean("allowPromptUpload", false)) { done(false, "AI_UPLOAD_NOT_ALLOWED", null); return }
        val endpoint = prefs.getString("endpoint", DEFAULT_ENDPOINT).orEmpty()
        val model = prefs.getString("model", "qwen-plus").orEmpty()
        if (!validEndpoint(endpoint) || !model.matches(Regex("[A-Za-z0-9._/-]{1,80}"))) {
            done(false, "AI_CONFIG_INVALID", null); return
        }
        val key = try { readKey() } catch (_: Exception) { done(false, "KEY_UNREADABLE", null); return }
        if (key.isNullOrBlank()) { done(false, "KEY_NOT_CONFIGURED", null); return }
        val timeout = prefs.getInt("timeoutSeconds", 35).coerceIn(10, 60)
        val id = ++epoch
        pending = done
        worker.execute {
            if (id != epoch) return@execute
            val answer = try { request(id, endpoint, model, key, message, timeout) }
                catch (_: Exception) { Pair("AI_NETWORK_ERROR", null) }
            main.post {
                if (id != epoch) return@post
                val callback = pending ?: return@post
                pending = null
                callback(answer.second != null, answer.first,
                    answer.second?.let { JSONObject().put("text", it) })
            }
        }
    }

    fun cancel() {
        epoch++
        connection?.disconnect()
        connection = null
        val callback = pending
        pending = null
        callback?.invoke(false, "AI_CANCELLED", null)
    }

    fun shutdown() {
        cancel()
        worker.shutdownNow()
    }

    private fun request(id: Int, endpoint: String, model: String, key: String, text: String, timeout: Int): Pair<String, String?> {
        val conn = URI(endpoint).toURL().openConnection() as HttpsURLConnection
        connection = conn
        try {
            if (id != epoch) return Pair("AI_CANCELLED", null)
            conn.requestMethod = "POST"
            conn.instanceFollowRedirects = false
            conn.connectTimeout = 10_000
            conn.readTimeout = timeout * 1000
            conn.doOutput = true
            conn.setRequestProperty("Authorization", "Bearer $key")
            conn.setRequestProperty("Content-Type", "application/json; charset=utf-8")
            conn.setRequestProperty("Accept", "application/json")
            val body = JSONObject().put("model", model).put("stream", false)
                .put("messages", org.json.JSONArray().put(JSONObject().put("role", "user").put("content", text)))
                .toString().toByteArray(StandardCharsets.UTF_8)
            if (id != epoch) return Pair("AI_CANCELLED", null)
            conn.outputStream.use { it.write(body) }
            val status = conn.responseCode
            if (status != 200) return Pair("AI_HTTP_$status", null)
            val bytes = conn.inputStream.use { input ->
                val output = ByteArrayOutputStream()
                val buffer = ByteArray(4096)
                while (output.size() <= 65_536) {
                    val count = input.read(buffer, 0, minOf(buffer.size, 65_537 - output.size()))
                    if (count <= 0) break
                    output.write(buffer, 0, count)
                }
                output.toByteArray()
            }
            if (bytes.size > 65_536) return Pair("AI_RESPONSE_TOO_LARGE", null)
            val response = JSONObject(String(bytes, StandardCharsets.UTF_8))
            val answer = response.optJSONArray("choices")?.optJSONObject(0)
                ?.optJSONObject("message")?.optString("content")?.trim()
            return if (answer.isNullOrBlank() || answer.length > 1000)
                Pair("AI_RESPONSE_INVALID", null) else Pair("READY", answer)
        } finally {
            conn.disconnect()
            if (connection === conn) connection = null
        }
    }

    private fun readKey(): String? {
        val saved = prefs.getString("encryptedKey", null) ?: return null
        val bytes = Base64.decode(saved, Base64.DEFAULT)
        require(bytes.size > 28)
        val cipher = Cipher.getInstance("AES/GCM/NoPadding")
        cipher.init(Cipher.DECRYPT_MODE, secretKey(), GCMParameterSpec(128, bytes.copyOfRange(0, 12)))
        return String(cipher.doFinal(bytes.copyOfRange(12, bytes.size)), StandardCharsets.UTF_8)
    }

    private fun secretKey(): SecretKey {
        val store = KeyStore.getInstance("AndroidKeyStore").apply { load(null) }
        (store.getKey(KEY_ALIAS, null) as? SecretKey)?.let { return it }
        val generator = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore")
        generator.init(KeyGenParameterSpec.Builder(KEY_ALIAS,
            KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT)
            .setKeySize(256)
            .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
            .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE).build())
        return generator.generateKey()
    }

    companion object {
        const val DEFAULT_ENDPOINT = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
        private const val KEY_ALIAS = "gork.cloud.text.v1"

        fun validEndpoint(value: String): Boolean = try {
            val uri = URI(value)
            uri.scheme.equals("https", true) && !uri.host.isNullOrBlank() && uri.userInfo == null &&
                uri.fragment == null && uri.query == null && uri.path.isNotBlank() &&
                uri.port in -1..65535 && value.length <= 240
        } catch (_: Exception) { false }
    }
}
