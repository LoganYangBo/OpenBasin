package com.openbasin.transport

import android.util.Base64
import com.openbasin.AgentConfig
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject
import java.security.SecureRandom
import java.util.concurrent.TimeUnit
import javax.crypto.Cipher
import javax.crypto.spec.GCMParameterSpec
import javax.crypto.spec.SecretKeySpec

/**
 * Encrypts a [SignalPayload] with AES-256-GCM on-device and uploads the
 * envelope to the OpenBasin server. The wire format and crypto parameters match
 * the server's `server/transport/crypto.py` exactly:
 *
 *   - AES-256-GCM, 12-byte random nonce, 128-bit tag (appended to ciphertext)
 *   - envelope = { device_id, nonce(base64), ciphertext(base64) }
 *   - per-device token sent in the `X-Device-Token` header
 *
 * No analytics, no third party — the only network call is to the user's server.
 */
class EncryptedUploader(private val config: AgentConfig) {

    private val http = OkHttpClient.Builder()
        .connectTimeout(15, TimeUnit.SECONDS)
        .writeTimeout(30, TimeUnit.SECONDS)
        .build()

    private val json = "application/json".toMediaType()

    /** Returns true on a 2xx response. Safe to call off the main thread. */
    fun upload(payload: SignalPayload): Boolean {
        if (!config.isConfigured) return false

        val envelope = encrypt(payload.toJson())
        val request = Request.Builder()
            .url("${config.serverUrl}/v1/events")
            .header("X-Device-Token", config.token)
            .post(envelope.toString().toRequestBody(json))
            .build()

        return http.newCall(request).execute().use { it.isSuccessful }
    }

    private fun encrypt(plaintext: JSONObject): JSONObject {
        val nonce = ByteArray(NONCE_BYTES).also { SecureRandom().nextBytes(it) }
        val key = SecretKeySpec(config.aesKey, "AES")
        val cipher = Cipher.getInstance("AES/GCM/NoPadding").apply {
            init(Cipher.ENCRYPT_MODE, key, GCMParameterSpec(TAG_BITS, nonce))
        }
        // GCM output is ciphertext || 16-byte tag — exactly what the server expects.
        val ciphertext = cipher.doFinal(plaintext.toString().toByteArray(Charsets.UTF_8))

        return JSONObject().apply {
            put("device_id", config.deviceId)
            put("nonce", Base64.encodeToString(nonce, Base64.NO_WRAP))
            put("ciphertext", Base64.encodeToString(ciphertext, Base64.NO_WRAP))
        }
    }

    companion object {
        private const val NONCE_BYTES = 12
        private const val TAG_BITS = 128
    }
}
