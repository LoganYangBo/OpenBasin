package com.openbasin.agent

import android.content.Context
import org.json.JSONArray
import org.json.JSONException
import org.json.JSONObject

/**
 * One IMAP mailbox to poll. Multiple accounts are stored as a JSON array in the
 * `openbasin_email` SharedPreferences under [KEY]; [EmailPoller] polls each in
 * turn. Add/remove them from the onboarding screen.
 */
data class EmailAccount(
    val host: String,
    val port: Int = 993,
    val user: String,
    val password: String,
) {
    fun toJson(): JSONObject = JSONObject().apply {
        put("host", host)
        put("port", port)
        put("user", user)
        put("password", password)
    }

    /** "user (host)" — for display in the accounts list (no password shown). */
    fun label(): String = "$user ($host:$port)"

    companion object {
        const val PREFS = "openbasin_email"
        private const val KEY = "imap_accounts"

        fun load(context: Context): List<EmailAccount> {
            val prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            val raw = prefs.getString(KEY, "") ?: ""
            val accounts = mutableListOf<EmailAccount>()
            if (raw.isNotEmpty()) {
                try {
                    val arr = JSONArray(raw)
                    for (i in 0 until arr.length()) {
                        val o = arr.getJSONObject(i)
                        accounts.add(
                            EmailAccount(
                                host = o.getString("host"),
                                port = o.optInt("port", 993),
                                user = o.getString("user"),
                                password = o.optString("password", ""),
                            )
                        )
                    }
                } catch (_: JSONException) {
                    // Corrupt store — treat as empty rather than crashing the poll.
                }
            }
            // Backward-compat: migrate a legacy single-account config on first read.
            if (accounts.isEmpty()) {
                val host = prefs.getString("imap_host", "") ?: ""
                val user = prefs.getString("imap_user", "") ?: ""
                if (host.isNotEmpty() && user.isNotEmpty()) {
                    accounts.add(
                        EmailAccount(host, 993, user, prefs.getString("imap_password", "") ?: "")
                    )
                    save(context, accounts)  // persist in the new format
                }
            }
            return accounts
        }

        fun save(context: Context, accounts: List<EmailAccount>) {
            val arr = JSONArray()
            accounts.forEach { arr.put(it.toJson()) }
            context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
                .edit()
                .putString(KEY, arr.toString())
                // Drop any legacy single-account keys once migrated.
                .remove("imap_host")
                .remove("imap_user")
                .remove("imap_password")
                .apply()
        }

        fun add(context: Context, account: EmailAccount) {
            save(context, load(context) + account)
        }

        fun clear(context: Context) {
            context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit().clear().apply()
        }
    }
}
