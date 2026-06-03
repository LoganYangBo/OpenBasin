# OpenBasin Android agent

Passively captures SMS, app notifications, and email, encrypts each signal with
AES-256-GCM on-device, and uploads it to your self-hosted OpenBasin server.

## Build

```bash
cd android
./gradlew assembleDebug      # APK at app/build/outputs/apk/debug/app-debug.apk
```

(Requires the Android SDK and a `local.properties` with `sdk.dir=...`, or build
from Android Studio.)

## Components

| File | Role |
|---|---|
| `agent/SmsReceiver.kt` | `BroadcastReceiver` on `SMS_RECEIVED` (READ_SMS) |
| `agent/NotificationCollector.kt` | `NotificationListenerService` for app notifications |
| `agent/EmailPoller.kt` | WorkManager job polling IMAP for unseen mail |
| `transport/EncryptedUploader.kt` | AES-256-GCM envelope + `X-Device-Token` upload |
| `transport/SignalPayload.kt` | On-device signal model + dedup `content_hash` |

## Setup on device

1. Install the APK.
2. Open the app; enter **Server URL**, **Device ID**, **Device token**, and the
   **AES key** (base64) — the same values you put under `devices:` in the
   server's `config.yaml`.
3. Tap **Save & enable capture** (grants SMS permission, schedules email polling).
4. Tap **Grant notification access** and enable OpenBasin in the system page.

For email, also store IMAP credentials in the `openbasin_email` SharedPreferences
(`imap_host`, `imap_user`, `imap_password`) — wire these into the onboarding UI
for your build, or set them via adb for testing.

## Privacy

The only network destination is the server URL you configure. No analytics, no
crash reporting, no third-party SDKs in the capture path.

## Crypto contract

Must stay in lockstep with `server/transport/crypto.py`:

- AES-256-GCM, 12-byte random nonce, 128-bit tag appended to the ciphertext
- Envelope JSON: `{ device_id, nonce(base64), ciphertext(base64) }`
- Per-device token in the `X-Device-Token` header
