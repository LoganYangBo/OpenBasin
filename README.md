# OpenBasin

> Your phone sees everything. Now so do you.

OpenBasin is an open-source personal signal aggregation framework for Android. It silently collects SMS, notifications, and emails from your device and routes them through your self-hosted server — where your own LLM turns raw signals into actions.

No cloud. No vendor. Your data stays on your machine.

---

## How it works

```
Android device                     Your server (Docker)
─────────────────                  ────────────────────────────────────
SMS                ──┐
App notifications  ──┼──► OpenBasin agent ──► pipeline engine ──► actions
Emails             ──┘       (encrypted)       (your LLM)
```

A lightweight Android agent monitors your device for authorized signals. Every event is encrypted on-device and sent to your self-hosted OpenBasin server. There, a YAML-defined pipeline uses the LLM of your choice to extract structure and trigger actions — bookkeeping, notifications, archiving, webhooks, or anything else you wire up.

---

## Features

- **Fully silent capture** — SMS, push notifications, and email, automatically collected with zero manual input
- **Model-agnostic** — bring your own LLM: OpenAI, Anthropic, Ollama (local/offline), Azure OpenAI, or any OpenAI-compatible API
- **Self-hosted** — one `docker compose up` and you're running; your data never leaves your infrastructure
- **YAML pipelines** — define signal → condition → action workflows in plain text
- **Extensible** — sources, extractors, and actions are all pluggable; community can contribute new ones
- **End-to-end encrypted** — device-to-server transport uses AES-256; server stores only what you choose

---

## Supported platforms

| Platform | Status | Notes |
|---|---|---|
| Android (Pixel) | ✅ Supported | Primary target |
| Android (Samsung One UI) | ✅ Supported | |
| Android (Nothing OS) | ✅ Supported | |
| Android (MIUI / EMUI / ColorOS) | ⚠️ Not supported | Aggressive background kill |
| iOS | ❌ Not supported | System sandbox prevents SMS/notification access |
| macOS / Windows | 🗓 Planned | Phase 2 |

---

## Quick start

### 1. Deploy the server

```bash
git clone https://github.com/yourusername/OpenBasin
cd OpenBasin
cp config.example.yaml config.yaml
# edit config.yaml — set your LLM provider and API key
docker compose up -d
```

Your server is now running at `http://your-server:8080`.

### 2. Configure your LLM

Edit `config.yaml`:

```yaml
llm:
  provider: openai                        # openai | anthropic | ollama | azure
  model: gpt-4o-mini
  api_key: ${OPENAI_API_KEY}
  base_url: https://api.openai.com/v1    # replace with Ollama URL for local inference
```

### 3. Install the Android agent

Download the latest APK from [Releases](https://github.com/yourusername/OpenBasin/releases), install it on your Android device, and enter your server URL and device token when prompted.

Grant the following permissions when asked:
- **Notification access** — to capture app notifications
- **SMS** — to capture incoming SMS
- The app will guide you to the correct system settings page for each

### 4. Create your first pipeline

Create a file at `pipelines/credit-card.yaml`:

```yaml
name: credit_card_bookkeeping
trigger:
  signal_type: sms
  filter: "bank OR charged OR payment OR transaction"

extract:
  schema:
    merchant: str
    amount: float
    currency: str
    category: str       # inferred by LLM

actions:
  - type: firefly
    account: "Chase Sapphire"
  - type: telegram
    message: "💳 {merchant} {currency}{amount} → {category}"
```

Restart the server or run `OpenBasin reload` — the pipeline is live.

---

## Built-in pipeline templates

OpenBasin ships with ready-to-use templates in `pipelines/examples/`:

| Template | Trigger | What it does |
|---|---|---|
| `credit-card.yaml` | Bank SMS | Extracts merchant, amount, category → Firefly III + Telegram |
| `parcel-tracking.yaml` | Courier SMS / email | Tracks delivery status → Telegram updates |
| `invoice-archive.yaml` | Email attachments | Extracts amount, vendor, date → Google Sheet + Drive |
| `subscription-alert.yaml` | Billing emails | Detects renewals → Telegram reminder 3 days before |
| `news-digest.yaml` | News app notifications | Aggregates headlines → daily summary via Telegram |

---

## Pipeline reference

A pipeline has three sections:

```yaml
name: my_pipeline

trigger:
  signal_type: sms | email | notification   # which signal type to listen for
  source_app: com.example.app               # optional: filter by Android app package
  filter: "keyword1 OR keyword2"            # optional: simple keyword pre-filter

extract:
  schema:                                   # define the fields you want LLM to extract
    field_name: str | float | int | bool | datetime

conditions:                                 # optional: only proceed if conditions pass
  - "amount > 100"
  - "merchant != 'Internal Transfer'"

actions:                                    # one or more actions to execute
  - type: firefly | telegram | sheet | notion | webhook | file
    # action-specific config below
```

### Available actions

**`telegram`**
```yaml
- type: telegram
  chat_id: ${TELEGRAM_CHAT_ID}
  message: "Your message with {field} interpolation"
```

**`firefly`** — requires [Firefly III](https://www.firefly-iii.org/) running on your network
```yaml
- type: firefly
  url: http://firefly:8080
  token: ${FIREFLY_TOKEN}
  account: "Account Name"
```

**`sheet`** — appends a row to Google Sheets
```yaml
- type: sheet
  spreadsheet_id: ${SHEET_ID}
  range: "Sheet1!A:Z"
```

**`webhook`** — sends extracted data as JSON POST to any URL
```yaml
- type: webhook
  url: https://your-service.example.com/hook
  headers:
    Authorization: "Bearer ${YOUR_TOKEN}"
```

**`file`** — appends to a local file on the server
```yaml
- type: file
  path: /data/archive/transactions.jsonl
```

---

## LLM configuration

OpenBasin does not bundle any model. Configure yours in `config.yaml`:

```yaml
llm:
  # OpenAI
  provider: openai
  model: gpt-4o-mini
  api_key: ${OPENAI_API_KEY}

  # Anthropic
  provider: anthropic
  model: claude-haiku-4-5
  api_key: ${ANTHROPIC_API_KEY}

  # Ollama — fully local, no data leaves your machine
  provider: ollama
  model: llama3.2
  base_url: http://ollama:11434/v1
  api_key: ollama

  # Azure OpenAI
  provider: azure
  model: gpt-4o-mini
  api_key: ${AZURE_OPENAI_KEY}
  base_url: https://your-instance.openai.azure.com/openai/deployments/gpt-4o-mini
```

Any provider exposing an OpenAI-compatible `/v1/chat/completions` endpoint works.

---

## Architecture

```
OpenBasin/
├── android/                 # Android agent (Kotlin)
│   ├── agent/
│   │   ├── NotificationCollector.kt   # NotificationListenerService
│   │   ├── SmsReceiver.kt             # BroadcastReceiver
│   │   └── EmailPoller.kt             # IMAP polling
│   └── transport/
│       └── EncryptedUploader.kt       # AES-256 + device auth
│
└── server/                  # Python server
    ├── api/                 # FastAPI — receives device events
    ├── pipeline/            # YAML pipeline engine
    ├── extract/             # LLM extraction layer
    ├── actions/             # Firefly, Telegram, Sheet, Webhook, File
    └── db/                  # SQLite event store + dedup
```

### Signal event schema

Every signal from every source is normalized into a single schema before hitting the pipeline engine:

```python
class SignalEvent(BaseModel):
    event_id: str           # globally unique — used for deduplication
    device_id: str
    signal_type: str        # sms | email | notification
    source_app: str | None  # Android package name
    raw_content: str        # original message content
    sender: str | None
    timestamp: datetime
    content_hash: str       # dedup key
```

---

## Security model

OpenBasin is designed around the assumption that you trust your own infrastructure and nobody else.

- **Device authentication** — each device registers with a unique token; the server rejects unregistered devices
- **Transport encryption** — all device-to-server communication is AES-256 encrypted before leaving the device
- **No telemetry** — OpenBasin never phones home; there are no analytics, no crash reporting, no usage tracking
- **Local LLM option** — configure Ollama to keep all data processing fully offline
- **You control the data** — OpenBasin stores events in SQLite on your server; delete or export anytime

---

## Contributing

OpenBasin is built around three extension points. Pick one and contribute:

**New Source** — add a new signal source (e.g. browser extension, desktop app)
See `server/sources/` and implement the `BaseSource` interface.

**New Action** — add a new action type (e.g. Notion, Obsidian, Home Assistant)
See `server/actions/` and implement the `BaseAction` interface.

**New Extractor Prompt** — contribute extraction prompts for specific apps or banks
See `server/extract/prompts/` — plain YAML files, no code required.

Please read [CONTRIBUTING.md](CONTRIBUTING.md) before opening a PR.

---

## How OpenBasin differs from similar projects

Several open-source projects already handle parts of what OpenBasin does. Here's an honest comparison.

### Signal capture — already solved

Tools like [message-mirror](https://github.com/Dragon-Born/message-mirror) and [SMSForwarder](https://github.com/Spirit532/SMSForwarder) can capture Android notifications and SMS and forward them as raw JSON to an HTTP endpoint. This part of the problem is well-understood, and OpenBasin's Android agent draws on the same underlying Android APIs (`NotificationListenerService`, `READ_SMS`).

### What those tools stop at

They forward raw text. A bank SMS arrives as:

```
Your Chase card ending 6688 was charged $128.50 at Whole Foods on 06/02.
```

It gets POSTed to your server as a JSON string. What happens next is entirely up to you — there is no parsing, no categorization, no action. You're on your own.

### Where OpenBasin picks up

OpenBasin treats the raw signal as the *input*, not the *output*. The pipeline engine passes it to your LLM, extracts structured fields (`merchant`, `amount`, `category`), evaluates conditions, and fires one or more actions — all automatically, with no code.

| | message-mirror / SMSForwarder | OpenClaw | OpenBasin |
|---|---|---|---|
| Passive SMS capture | ✅ | ❌ (send only) | ✅ |
| Passive notification capture | ✅ | ✅ (on demand) | ✅ |
| LLM extraction layer | ❌ | ✅ | ✅ |
| YAML pipeline engine | ❌ | ❌ | ✅ |
| Composable actions | ❌ | via skills | ✅ |
| Trigger model | passive | command-driven | passive |
| Self-hosted | ✅ | ✅ | ✅ |

OpenBasin is not trying to replace any of these tools. The Android capture layer is inspired by message-mirror. The difference is the pipeline engine that sits behind it.

---

## Roadmap

- [x] Android agent: SMS, notifications, email
- [x] Server: pipeline engine, LLM extraction, core actions
- [x] Docker Compose deployment
- [ ] macOS menu bar agent
- [ ] Windows tray agent
- [ ] iOS: IMAP + Shortcuts webhook bridge
- [ ] Web UI: pipeline status, event log, device management
- [ ] Health data: Android Health Connect
- [ ] Browser extension: web push capture
- [ ] Community extractor prompt library

---

## License

MIT — see [LICENSE](LICENSE).

---

*OpenBasin does not collect, transmit, or store your data on any third-party server. Everything runs on infrastructure you control.*
