package com.openbasin.agent

import android.app.Notification
import android.service.notification.NotificationListenerService
import android.service.notification.StatusBarNotification
import com.openbasin.AgentConfig
import com.openbasin.transport.EncryptedUploader
import com.openbasin.transport.SignalPayload
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch

/**
 * Captures app notifications via [NotificationListenerService]. Each posted
 * notification's title + text becomes a `notification` signal tagged with the
 * originating package (`source_app`), which pipelines can filter on.
 *
 * Ongoing/foreground-service notifications and our own are ignored to avoid
 * noise and feedback loops.
 */
class NotificationCollector : NotificationListenerService() {

    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)

    override fun onNotificationPosted(sbn: StatusBarNotification) {
        val pkg = sbn.packageName ?: return
        if (pkg == packageName) return
        if (sbn.isOngoing) return

        val extras = sbn.notification.extras
        val title = extras.getCharSequence(Notification.EXTRA_TITLE)?.toString().orEmpty()
        val text = extras.getCharSequence(Notification.EXTRA_TEXT)?.toString().orEmpty()
        if (title.isBlank() && text.isBlank()) return

        val config = AgentConfig(applicationContext)
        val payload = SignalPayload(
            signalType = "notification",
            rawContent = if (title.isBlank()) text else "$title\n$text",
            sender = title.ifBlank { null },
            sourceApp = pkg,
            timestampMillis = sbn.postTime,
            deviceId = config.deviceId,
        )
        scope.launch { EncryptedUploader(config).upload(payload) }
    }
}
