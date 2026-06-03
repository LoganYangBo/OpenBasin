package com.openbasin.agent

import android.content.Context
import androidx.work.CoroutineWorker
import androidx.work.WorkerParameters
import com.openbasin.AgentConfig
import com.openbasin.transport.EncryptedUploader
import com.openbasin.transport.SignalPayload
import javax.mail.Flags
import javax.mail.Folder
import javax.mail.Session
import javax.mail.search.FlagTerm
import java.util.Properties

/**
 * Periodically polls an IMAP mailbox for unseen messages and uploads each as an
 * `email` signal. Scheduled via WorkManager (see [MainActivity]); the interval
 * is bounded by Android's minimum periodic-work window (~15 min).
 *
 * IMAP credentials are read from SharedPreferences. Messages are marked seen
 * only after a successful upload, so a failed upload is retried next cycle.
 */
class EmailPoller(context: Context, params: WorkerParameters) :
    CoroutineWorker(context, params) {

    override suspend fun doWork(): Result {
        val config = AgentConfig(applicationContext)
        if (!config.isConfigured) return Result.success()

        val prefs = applicationContext.getSharedPreferences("openbasin_email", Context.MODE_PRIVATE)
        val host = prefs.getString("imap_host", "") ?: ""
        val user = prefs.getString("imap_user", "") ?: ""
        val password = prefs.getString("imap_password", "") ?: ""
        if (host.isEmpty() || user.isEmpty()) return Result.success()

        return try {
            poll(config, host, user, password)
            Result.success()
        } catch (e: Exception) {
            Result.retry()
        }
    }

    private fun poll(config: AgentConfig, host: String, user: String, password: String) {
        val props = Properties().apply {
            put("mail.store.protocol", "imaps")
            put("mail.imaps.host", host)
            put("mail.imaps.port", "993")
            put("mail.imaps.ssl.enable", "true")
        }
        val store = Session.getInstance(props).getStore("imaps")
        store.connect(host, user, password)
        try {
            val inbox = store.getFolder("INBOX")
            inbox.open(Folder.READ_WRITE)
            val uploader = EncryptedUploader(config)
            val unseen = inbox.search(FlagTerm(Flags(Flags.Flag.SEEN), false))
            for (msg in unseen) {
                val payload = SignalPayload(
                    signalType = "email",
                    rawContent = extractText(msg),
                    sender = msg.from?.firstOrNull()?.toString(),
                    sourceApp = "imap",
                    subject = msg.subject,
                    timestampMillis = msg.sentDate?.time ?: System.currentTimeMillis(),
                    deviceId = config.deviceId,
                )
                if (uploader.upload(payload)) {
                    msg.setFlag(Flags.Flag.SEEN, true)
                }
            }
            inbox.close(false)
        } finally {
            store.close()
        }
    }

    private fun extractText(msg: javax.mail.Message): String {
        val content = msg.content
        return when (content) {
            is String -> content
            is javax.mail.Multipart -> buildString {
                for (i in 0 until content.count) {
                    val part = content.getBodyPart(i)
                    if (part.isMimeType("text/plain")) append(part.content.toString())
                }
            }.ifBlank { "[non-text email body]" }
            else -> content?.toString() ?: ""
        }
    }
}
