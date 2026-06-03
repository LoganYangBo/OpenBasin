package com.openbasin

import android.content.Context
import android.util.Base64

/**
 * Device-side configuration: server URL, device id, per-device token, and the
 * 256-bit AES key shared with the server (the same base64 key listed under
 * `devices:` in the server's config.yaml).
 *
 * Stored in SharedPreferences. In a hardened build the AES key belongs in the
 * Android Keystore; kept here in prefs for clarity of the reference agent.
 */
class AgentConfig(context: Context) {
    private val prefs = context.getSharedPreferences("openbasin", Context.MODE_PRIVATE)

    var serverUrl: String
        get() = prefs.getString(KEY_URL, "") ?: ""
        set(v) = prefs.edit().putString(KEY_URL, v.trimEnd('/')).apply()

    var deviceId: String
        get() = prefs.getString(KEY_DEVICE_ID, "") ?: ""
        set(v) = prefs.edit().putString(KEY_DEVICE_ID, v).apply()

    var token: String
        get() = prefs.getString(KEY_TOKEN, "") ?: ""
        set(v) = prefs.edit().putString(KEY_TOKEN, v).apply()

    /** base64-encoded 32-byte key. */
    var aesKeyBase64: String
        get() = prefs.getString(KEY_AES, "") ?: ""
        set(v) = prefs.edit().putString(KEY_AES, v).apply()

    val aesKey: ByteArray
        get() = Base64.decode(aesKeyBase64, Base64.DEFAULT)

    val isConfigured: Boolean
        get() = serverUrl.isNotEmpty() && deviceId.isNotEmpty() &&
            token.isNotEmpty() && aesKeyBase64.isNotEmpty()

    companion object {
        private const val KEY_URL = "server_url"
        private const val KEY_DEVICE_ID = "device_id"
        private const val KEY_TOKEN = "token"
        private const val KEY_AES = "aes_key"
    }
}
