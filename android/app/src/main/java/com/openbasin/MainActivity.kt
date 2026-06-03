package com.openbasin

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Bundle
import android.provider.Settings
import android.widget.Button
import android.widget.EditText
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.core.app.ActivityCompat
import androidx.work.Constraints
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.NetworkType
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import com.openbasin.agent.EmailAccount
import com.openbasin.agent.EmailPoller
import java.util.concurrent.TimeUnit

/**
 * Minimal onboarding screen: enter server URL, device id, token and AES key,
 * grant SMS + notification-access permissions, and schedule the IMAP poller.
 *
 * Capture itself runs in the background components (SmsReceiver,
 * NotificationCollector, EmailPoller) — this activity only configures them.
 */
class MainActivity : AppCompatActivity() {

    private lateinit var config: AgentConfig

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)
        config = AgentConfig(this)

        val urlField = findViewById<EditText>(R.id.serverUrl)
        val deviceField = findViewById<EditText>(R.id.deviceId)
        val tokenField = findViewById<EditText>(R.id.token)
        val keyField = findViewById<EditText>(R.id.aesKey)
        val imapHostField = findViewById<EditText>(R.id.imapHost)
        val imapPortField = findViewById<EditText>(R.id.imapPort)
        val imapUserField = findViewById<EditText>(R.id.imapUser)
        val imapPasswordField = findViewById<EditText>(R.id.imapPassword)
        val accountsList = findViewById<TextView>(R.id.accountsList)

        urlField.setText(config.serverUrl)
        deviceField.setText(config.deviceId)
        refreshAccountsList(accountsList)

        findViewById<Button>(R.id.saveButton).setOnClickListener {
            config.serverUrl = urlField.text.toString()
            config.deviceId = deviceField.text.toString()
            config.token = tokenField.text.toString()
            config.aesKeyBase64 = keyField.text.toString()

            requestSmsPermission()
            scheduleEmailPolling()
            Toast.makeText(this, "Saved. Grant notification access next.", Toast.LENGTH_LONG).show()
        }

        // Add one mailbox to the list. Repeat for as many accounts as you want.
        findViewById<Button>(R.id.addMailboxButton).setOnClickListener {
            val host = imapHostField.text.toString().trim()
            val user = imapUserField.text.toString().trim()
            val password = imapPasswordField.text.toString()
            if (host.isEmpty() || user.isEmpty()) {
                Toast.makeText(this, "Host and user are required", Toast.LENGTH_SHORT).show()
                return@setOnClickListener
            }
            val port = imapPortField.text.toString().trim().toIntOrNull() ?: 993
            EmailAccount.add(this, EmailAccount(host, port, user, password))

            // Clear the inputs so the next mailbox can be entered.
            listOf(imapHostField, imapPortField, imapUserField, imapPasswordField)
                .forEach { it.text.clear() }
            refreshAccountsList(accountsList)
            scheduleEmailPolling()
            Toast.makeText(this, "Mailbox added: $user", Toast.LENGTH_SHORT).show()
        }

        findViewById<Button>(R.id.clearMailboxesButton).setOnClickListener {
            EmailAccount.clear(this)
            refreshAccountsList(accountsList)
            Toast.makeText(this, "All mailboxes removed", Toast.LENGTH_SHORT).show()
        }

        // Notification access cannot be granted via runtime permission — it
        // requires the system settings page. Guide the user there.
        findViewById<Button>(R.id.notificationAccessButton).setOnClickListener {
            startActivity(Intent(Settings.ACTION_NOTIFICATION_LISTENER_SETTINGS))
        }
    }

    private fun refreshAccountsList(view: TextView) {
        val accounts = EmailAccount.load(this)
        view.text = if (accounts.isEmpty()) {
            "No mailboxes configured"
        } else {
            accounts.joinToString("\n") { "• ${it.label()}" }
        }
    }

    private fun requestSmsPermission() {
        val perms = arrayOf(Manifest.permission.RECEIVE_SMS, Manifest.permission.READ_SMS)
        val missing = perms.any {
            ActivityCompat.checkSelfPermission(this, it) != PackageManager.PERMISSION_GRANTED
        }
        if (missing) ActivityCompat.requestPermissions(this, perms, 1)
    }

    private fun scheduleEmailPolling() {
        val request = PeriodicWorkRequestBuilder<EmailPoller>(15, TimeUnit.MINUTES)
            .setConstraints(Constraints.Builder().setRequiredNetworkType(NetworkType.CONNECTED).build())
            .build()
        WorkManager.getInstance(this).enqueueUniquePeriodicWork(
            "openbasin-email-poll", ExistingPeriodicWorkPolicy.UPDATE, request
        )
    }
}
