package com.openbasin.agent

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.provider.Telephony
import com.openbasin.AgentConfig
import com.openbasin.transport.EncryptedUploader
import com.openbasin.transport.SignalPayload
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch

/**
 * Passively captures incoming SMS via the `SMS_RECEIVED` broadcast (READ_SMS).
 * Multi-part messages are concatenated into a single signal. The body is
 * encrypted and uploaded; nothing is parsed on-device — extraction is the
 * server's job.
 */
class SmsReceiver : BroadcastReceiver() {

    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action != Telephony.Sms.Intents.SMS_RECEIVED_ACTION) return

        val messages = Telephony.Sms.Intents.getMessagesFromIntent(intent) ?: return
        if (messages.isEmpty()) return

        val sender = messages.first().originatingAddress
        val body = messages.joinToString(separator = "") { it.messageBody ?: "" }
        if (body.isBlank()) return

        val config = AgentConfig(context)
        val payload = SignalPayload(
            signalType = "sms",
            rawContent = body,
            sender = sender,
            sourceApp = "android.sms",
            timestampMillis = messages.first().timestampMillis,
            deviceId = config.deviceId,
        )

        // BroadcastReceivers must not block; hand off to a background coroutine.
        val pending = goAsync()
        CoroutineScope(Dispatchers.IO).launch {
            try {
                EncryptedUploader(config).upload(payload)
            } finally {
                pending.finish()
            }
        }
    }
}
