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

For email, fill the **Email (IMAP)** fields on the same screen (host, user,
password). They are saved to the `openbasin_email` SharedPreferences and read by
`EmailPoller`, which polls every ~15 min for unseen mail.

## End-to-end test on an emulator (no physical phone)

The cleanest signal to drive through an emulator is **SMS** — the emulator can
inject one, which fires `SmsReceiver` exactly like a real message.

### 0. Install the toolchain

Install **Android Studio** (bundles the SDK, an emulator, adb, and Gradle). On
first launch it installs a default SDK. That's all you need — no separate Gradle.

### 1. Run the server on your host

```powershell
# config.yaml ships pointing at pipelines/dev (SMS archive, no LLM needed)
.\.venv\Scripts\python.exe -m server     # binds 0.0.0.0:8080
```

The emulator reaches your host at the special IP **`10.0.2.2`** (NOT
`localhost` — that's the emulator itself). Cleartext to `10.0.2.2` is already
permitted by `res/xml/network_security_config.xml`.

### 2. Build & install the app

Open the `android/` folder in Android Studio → let Gradle sync → create an AVD
(Device Manager → any Pixel, API 33/34) → press **Run**. Or from the command
line once the SDK is installed:

```powershell
cd android
echo "sdk.dir=$env:LOCALAPPDATA\Android\Sdk" > local.properties
.\gradlew installDebug
```

### 3. Configure the agent (in the app)

| Field | Value |
|---|---|
| Server URL | `http://10.0.2.2:8080` |
| Device ID | `test-device` |
| Device token | (the `token` from your `config.yaml`) |
| AES key (base64) | (the `aes_key` from your `config.yaml`) |

Tap **Save & enable capture** and grant the SMS permission when prompted.

### 4. Inject a test SMS

Android Studio → **Extended Controls** (`···` on the emulator toolbar) → **Phone**
→ set a sender, type a message, **Send Message**. Or via adb:

```powershell
adb emu sms send 10086 "Chase charged $42 at Cafe"
```

### 5. Verify the full chain

Watch the **server logs** for the incoming event, then:

```powershell
type ..\data\archive\sms.jsonl       # the message, captured → encrypted → uploaded → archived
curl http://localhost:8080/v1/events/recent -H "X-Device-Token: <your token>"
```

To test **notifications**, trigger any app notification on the emulator (after
granting notification access via the app's button).

To test **email**, fill the Email (IMAP) fields in the app (e.g. for Gmail:
host `imap.gmail.com`, your address, and an **app password**), then send an email
to that inbox. `EmailPoller` runs every ~15 min; to fire it immediately for a
test, force-stop and reopen the app, or trigger the WorkManager job from Android
Studio's **App Inspection → Background Task Inspector**. A poll uploads each
unseen message and marks it seen.

To test the **LLM extraction + real actions** path, point the server's
`pipelines_dir` back at `pipelines` and configure an LLM — see `scripts/README.md`.

### Troubleshooting

- **Nothing arrives:** confirm the URL is `10.0.2.2`, not `localhost`; confirm
  the server is bound to `0.0.0.0` (it is by default).
- **401 in server logs:** token in the app ≠ token in `config.yaml`.
- **400 "Decryption failed":** the AES key in the app ≠ the device's `aes_key`.
- **Upload silently fails on a LAN IP over HTTP:** add that IP to
  `network_security_config.xml`.

## Privacy

The only network destination is the server URL you configure. No analytics, no
crash reporting, no third-party SDKs in the capture path.

## Crypto contract

Must stay in lockstep with `server/transport/crypto.py`:

- AES-256-GCM, 12-byte random nonce, 128-bit tag appended to the ciphertext
- Envelope JSON: `{ device_id, nonce(base64), ciphertext(base64) }`
- Per-device token in the `X-Device-Token` header
