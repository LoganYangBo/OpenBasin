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
 * Periodically polls one or more IMAP mailboxes for unseen messages and uploads
 * each as an `email` signal. Scheduled via WorkManager (see [MainActivity]); the
 * interval is bounded by Android's minimum periodic-work window (~15 min).
 *
 * Accounts are read from SharedPreferences via [EmailAccount]. Each account is
 * polled independently — one failing mailbox doesn't block the others. Messages
 * are marked seen only after a successful upload, so a failed upload is retried
 * next cycle.
 */
class EmailPoller(context: Context, params: WorkerParameters) :
    CoroutineWorker(context, params) {

    override suspend fun doWork(): Result {
        val config = AgentConfig(applicationContext)
        if (!config.isConfigured) return Result.success()

        val accounts = EmailAccount.load(applicationContext)
        if (accounts.isEmpty()) return Result.success()

        val uploader = EncryptedUploader(config)
        var hadError = false
        for (account in accounts) {
            try {
                poll(account, config, uploader)
            } catch (e: Exception) {
                // Isolate failures so a bad mailbox doesn't starve the rest;
                // retry the whole batch next cycle.
                hadError = true
            }
        }
        return if (hadError) Result.retry() else Result.success()
    }

    private fun poll(account: EmailAccount, config: AgentConfig, uploader: EncryptedUploader) {
        val props = Properties().apply {
            put("mail.store.protocol", "imaps")
            put("mail.imaps.host", account.host)
            put("mail.imaps.port", account.port.toString())
            put("mail.imaps.ssl.enable", "true")
        }
        val store = Session.getInstance(props).getStore("imaps")
        store.connect(account.host, account.user, account.password)
        try {
            val inbox = store.getFolder("INBOX")
            inbox.open(Folder.READ_WRITE)
            val unseen = inbox.search(FlagTerm(Flags(Flags.Flag.SEEN), false))
            for (msg in unseen) {
                val payload = SignalPayload(
                    signalType = "email",
                    rawContent = extractText(msg),
                    sender = msg.from?.firstOrNull()?.toString(),
                    sourceApp = "imap:${account.user}",  // which mailbox it came from
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
