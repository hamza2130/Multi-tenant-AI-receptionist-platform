# AI Receptionist Platform

A multi-tenant, config-driven AI receptionist. Any business signs up, picks a vertical template (or starts blank), uploads its own information, and gets a working AI receptionist that answers questions, books appointments, captures leads, and escalates anything it can't handle — over text chat, an embeddable website widget, and phone calls.

One shared codebase serves every business. Each tenant's data (knowledge base, settings, bookings, leads, conversations) is strictly isolated from every other tenant.

---

## Table of Contents

- [Architecture Overview](#architecture-overview)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Prerequisites](#prerequisites)
- [Environment Variables](#environment-variables)
- [Running the Project](#running-the-project)
- [Docker (Postgres & Qdrant)](#docker-postgres--qdrant)
- [Feature Overview](#feature-overview)
- [Test Calls and Browser Calling](#test-calls-and-browser-calling)
- [Known Limitations & Next Steps](#known-limitations--next-steps)

---

## Architecture Overview

```
                         ┌─────────────────────┐
                         │   Admin Console      │  (Next.js, port 3000)
                         │   business owner UI  │
                         └──────────┬───────────┘
                                    │ JWT auth
                                    ▼
┌──────────────┐          ┌─────────────────────┐          ┌──────────────┐
│  Widget /     │  API key │      main.py         │          │  PostgreSQL   │
│  Website      │─────────▶│   FastAPI backend     │◀────────▶│  (tenants,    │
│  (embedded)   │          │   port 8000           │          │   bookings,   │
└──────────────┘          └──────────┬───────────┘          │   leads, etc.)│
                                    │                        └──────────────┘
                          ┌──────────┴───────────┐
                          │   agent.py            │
                          │   RAG + tool-calling  │──────▶ Qdrant (per-tenant
                          │   brain (text/chat)   │        vector collections)
                          └────────────────────────┘

┌──────────────┐          ┌─────────────────────┐
│  Phone call / │  Twilio  │   voice_server.py    │
│  Widget call  │─────────▶│   Pipecat voice       │──▶ Deepgram (STT)
└──────────────┘          │   pipeline, port 8001 │──▶ Groq (LLM)
┌──────────────┐  WebRTC  │                       │──▶ ElevenLabs (TTS)
│ Test Sandbox  │─────────▶│                       │
│ call (free)   │          └───────────────────────┘
└──────────────┘
```

**Multi-tenancy rule:** every request resolves a `tenant_id` (via API key, JWT session, or dialed phone number). All retrieval, config, and tool calls are scoped to that tenant. There are no shared Qdrant collections — this is a hard security boundary, not a convention.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend API | FastAPI (Python) |
| Voice pipeline | Pipecat 1.6.0 |
| Telephony | Twilio (SIP/Voice + WhatsApp) |
| Test calls | WebRTC via Pipecat's SmallWebRTC (peer-to-peer, free) |
| STT | Deepgram (Nova-2) |
| LLM | Groq |
| TTS | ElevenLabs |
| Vector DB | Qdrant (per-tenant collections) |
| Embeddings | `sentence-transformers` (all-MiniLM-L6-v2, local, no API key needed) |
| Relational DB | PostgreSQL |
| Admin Console | Next.js + TypeScript + Tailwind CSS |
| Widget | Plain HTML/JS |

---

## Project Structure

```
ai-receptionist-platform/
├── backend/
│   ├── main.py              # All API routes: auth, tenants, ingestion, chat, console, tokens
│   ├── voice_server.py      # Real-time voice pipeline (Pipecat) — phone + browser calls
│   ├── agent.py             # Text-channel brain: RAG + tool-calling
│   ├── skills.py            # Tool functions: book_appointment, capture_lead, take_message, escalate
│   ├── templates.py         # Vertical onboarding templates (clinic, restaurant, real_estate)
│   ├── whatsapp.py          # WhatsApp escalation alerts via Twilio
│   ├── ingestion.py         # Knowledge base training pipeline (clean → chunk → embed)
│   ├── vector_store.py      # Qdrant wrapper, per-tenant collection isolation
│   ├── embeddings.py        # Local embedding model wrapper
│   ├── models.py            # SQLAlchemy schema
│   ├── database.py          # DB session handling
│   ├── auth.py               # JWT-based signup/login for the Admin Console
│   ├── tenant_resolver.py   # API-key-based tenant resolution (widget/chat)
│   ├── call_logging.py      # Call transcripts, recordings, summaries
│   ├── config.py            # Settings, reads .env
│   └── requirements.txt
├── admin-console/            # Next.js Admin Console
│   └── app/
│       ├── signup/, login/
│       └── dashboard/
│           ├── knowledge-base/
│           ├── test-sandbox/
│           ├── settings/
│           ├── bookings/
│           ├── leads/
│           └── publish/
├── widget/
│   └── widget_combined.html  # Embeddable chat + call widget
└── dummy_site/                # A fake business homepage, for testing the embed — not part of the product
|
|___.gitignore                # Excludes secrets (.env), venv/, node_modules/, and build artifacts from git
```

---

## Prerequisites

- Python 3.11+ and a virtual environment
- Node.js + npm
- Docker Desktop
- Accounts/API keys for: Twilio, Deepgram, Groq, ElevenLabs

---

## Environment Variables

Create `backend/.env` with:

```
DATABASE_URL=postgresql://receptionist:<password>@localhost:5432/receptionist_platform
QDRANT_URL=http://localhost:6333

JWT_SECRET=<your-secret>
ADMIN_API_KEY=                          # optional — turns on POST /admin/tenants; blank keeps it off

GROQ_API_KEY=<your-key>
GROQ_MODEL=<model-name>

DEEPGRAM_API_KEY=<your-key>

ELEVENLABS_API_KEY=<your-key>
ELEVENLABS_VOICE_ID=<voice-id>

TWILIO_ACCOUNT_SID=<your-sid>
TWILIO_AUTH_TOKEN=<your-token>
TWILIO_API_KEY_SID=<your-key-sid>       # used for widget browser calling only — see note below
TWILIO_API_KEY_SECRET=<your-key-secret> # used for widget browser calling only
TWILIO_TWIML_APP_SID=<your-app-sid>     # used for widget browser calling only
TWILIO_WHATSAPP_FROM=+14155238886       # Twilio's shared Sandbox number by default

PUBLIC_BASE_URL=https://your-ngrok-url.ngrok-free.dev  # updates every time ngrok restarts on a free plan
```

---

## Fresh Machine Setup (First Time Only)

Do this once, when setting up the project on a new machine. After this, use the [Running the Project](#running-the-project) section every time.

### 1. Clone the repository
```bash
git clone https://github.com/Kshaf-Fatima/Multi-tenant-AI-receptionist-platform.git
cd Multi-tenant-AI-receptionist-platform
```

### 2. Set up the backend (Python)
```bash
cd backend
python -m venv venv

# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

pip install -r requirements.txt
```

### 3. Create your `.env` file
```bash
# Windows:
copy .env.example .env
# macOS/Linux:
cp .env.example .env
```
Then open `backend/.env` and fill in your own real values — API keys for Twilio, Deepgram, Groq, ElevenLabs, and a JWT secret (see [Environment Variables](#environment-variables) for the full list and what each one is for). None of these are provided in the repo — they're personal/account-specific and must never be committed to git.

### 4. Set up the frontend (Node)
```bash
cd admin-console
npm run dev
```

### 5. Set up Docker containers (Postgres & Qdrant)
See [Docker (Postgres & Qdrant)](#docker-postgres--qdrant) below — the "first-time setup" commands create the containers; you only need to do this once per machine.

Once all five steps are done, follow [Running the Project](#running-the-project) to start everything.

## Running the Project

Every process below runs in its **own terminal window** and must be left running.

### 1. Start Docker containers (Postgres + Qdrant)

```bash
docker start receptionist_postgres receptionist_qdrant
```

Confirm both are running:

```bash
docker ps
```

If the containers don't exist yet (first-time setup), see [Docker (Postgres & Qdrant)](#docker-postgres--qdrant) below.

### 2. Start the backend API

```bash
cd backend
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

uvicorn main:app --reload --port 8000
```

### 3. Start the voice server

In a separate terminal:

```bash
cd backend
venv\Scripts\activate   # or source venv/bin/activate
uvicorn voice_server:app --reload --port 8001
```

This is all the Test Sandbox's **Call** tab needs. It connects straight to this server over WebRTC, so test calls need no Twilio account, phone number or ngrok. You still need the Deepgram, Groq and ElevenLabs keys, since those do the listening, thinking and speaking. If you installed the backend before WebRTC support was added, re-run `pip install -r requirements.txt` to get it.

### 4. Start the Admin Console

In a separate terminal:

```bash
cd admin-console
npm install   # first time only
npm run dev
```

Visit `http://localhost:3000`.

### 5. (Optional) Serve the embeddable widget

Only needed when testing the widget outside the Admin Console (e.g. embedded on a real website):

```bash
cd widget
python -m http.server 5500
```

### 6. (Optional) ngrok — required only for real phone calls and widget calls

Twilio needs a public URL to reach your local `/voice` webhook. Test Sandbox calls don't go through Twilio, so they don't need this.

```bash
ngrok http 8001
```

Copy the forwarding URL into `PUBLIC_BASE_URL` in `.env`, and set it as the Voice webhook on your Twilio phone number (and/or TwiML App, if using widget browser calling — see below).

**Note:** ngrok's URL changes every time you restart it on the free plan. You'll need to update `PUBLIC_BASE_URL` and your Twilio number's webhook each time, unless you have a paid ngrok plan with a reserved domain.

---

## Docker (Postgres & Qdrant)

### First-time setup (containers don't exist yet)

```bash
docker run -d --name receptionist_postgres \
  -e POSTGRES_USER=receptionist \
  -e POSTGRES_PASSWORD=<your-password> \
  -e POSTGRES_DB=receptionist_platform \
  -p 5432:5432 postgres:16

docker run -d --name receptionist_qdrant \
  -p 6333:6333 -p 6334:6334 qdrant/qdrant
```

Make sure `DATABASE_URL` and `QDRANT_URL` in `.env` match these.

### Every time after that

Just start the existing containers — no need to recreate them:

```bash
docker start receptionist_postgres receptionist_qdrant
```

Docker Desktop itself needs to be running in the background for any `docker` command to work at all (check for the whale icon in your system tray, or open the Docker Desktop app and wait for it to say "Engine running").

### Inspecting the database directly

Useful for debugging without building a UI for everything:

```bash
docker exec receptionist_postgres psql -U receptionist -d receptionist_platform -c "SELECT id, name, phone_number FROM tenants;"
```

---

## Feature Overview

- **Multi-tenant onboarding** — signup with a vertical template (clinic, restaurant, real estate) pre-fills Settings and Knowledge Base, or start from a blank slate
- **Knowledge Base** — paste text, upload a PDF, or pull from a URL; view, edit, or remove any entry
- **Grounded answers** — chat and phone calls both look up the business's own knowledge base for each question asked, so answers come from its data and aren't invented
- **Booking, lead capture, message-taking, escalation** — via tool-calling, with confirm-before-booking and confirm-before-escalating safety checks against speech/text mishearing. Every booking rule a business sets — opening hours, how much notice it needs, how far ahead it takes bookings, how long an appointment runs — is enforced in code, not left to the model
- **WhatsApp escalation alerts** — business owners get an instant WhatsApp message when something is escalated (requires completing Twilio's WhatsApp Sandbox setup — see `backend/whatsapp.py`)
- **Embeddable widget** — a small floating chat bubble any business can paste onto their own website (`Publish` page in the Admin Console generates the exact snippet)
- **Phone calls** — real inbound calls via Twilio, routed to the right business by the dialed number, which each owner sets under **Settings → Phone Number**
- **Free test calls** — talk to your receptionist from the Test Sandbox over WebRTC, through the same pipeline a phone caller reaches (see next section)
- **Widget calling** — website visitors can call from the embedded widget, via Twilio browser calling

---

## Test Calls and Browser Calling

**Real phone calls (the actual product requirement) work independently of everything below.** `voice_server.py` routes a real inbound call by the dialed phone number (`Tenant.phone_number`), separately from both kinds of browser call.

There are two ways to call the receptionist from a browser. Both reach the *same* voice pipeline a phone caller reaches (`run_receptionist()` in `voice_server.py`), so what you hear is what callers get.

### Test Sandbox calls (free, WebRTC)

The Admin Console's Test Sandbox **Call** tab connects your microphone straight to `voice_server.py` over peer-to-peer WebRTC (`POST /webrtc/offer`). There's no Twilio in the path, so it costs nothing beyond your Deepgram, Groq and ElevenLabs usage, and it needs no phone number, Twilio account or ngrok. The call is tied to your login, so it always reaches your own business's receptionist.

What it doesn't test: phone-network audio (8kHz, compressed) and carrier latency. Before going live, still place one real phone call. It also assumes the console and the voice server share a machine or local network, because no STUN/TURN servers are configured.

### Widget calls (Twilio browser calling)

The embeddable widget's **Call** tab uses Twilio's Voice SDK. It gets a token from `GET /token` on `main.py`, sending the business's API key (the same one it uses for chat), and Twilio then connects the call to `voice_server.py` through a TwiML App. This needs the Twilio browser-calling keys, and ngrok when running locally.

**If you want to remove widget calling**, here is exactly what to delete or revert, file by file:

### Backend

**`backend/main.py`**
- Remove the `GET /token` route entirely (issues Twilio Access Tokens — used only by widget calling)

**`backend/voice_server.py`**
- In `voice_webhook()`: remove the `tenant_id_param` and `tenant_api_key_param` handling — real calls only ever use `dialed_number`
- In `websocket_endpoint()`: remove the `if tenant_id_param:` and `elif tenant_api_key_param:` branches — keep only the `else: tenant = _get_tenant_by_phone(...)` path. (Nothing sends `tenant_id` anymore; the Test Sandbox used to, before it moved to WebRTC.)
- These two params can also be removed from the `<Parameter>` tags in the TwiML response

### Frontend

**`widget/widget_combined.html`**
- Remove the Twilio Voice SDK `<script>` tag
- Remove the `#call-panel` HTML block and the "Call" tab button
- Remove the entire "Call" JavaScript section (`device`, `activeCall`, `setupCalling()`, `callBtn`/`hangupBtn` listeners)
- Keep the chat panel and its script section

### Also remove (optional cleanup)
- `TWILIO_API_KEY_SID`, `TWILIO_API_KEY_SECRET`, `TWILIO_TWIML_APP_SID` from `.env` and `config.py` (only used by the `/token` route)
- Any TwiML App configured in the Twilio console (not needed once nothing calls `/token`)

---

## Known Limitations & Next Steps

This section is intentionally honest about what's not finished, so anyone picking this up knows exactly where things stand.

- **Real inbound phone-call testing is not yet fully verified**, and **WhatsApp escalation alerts have not been live-tested**, because both require a working Twilio account with a purchased phone number (for calls) and a completed WhatsApp Sandbox/Business setup (for alerts) — this has been blocked by external Twilio account access issues during development (trial verification restrictions, and a suspected carrier-level call-blocking issue). The backend logic for both is complete and correct; what remains is Twilio account setup, not code.
- **Some tenants' Knowledge Base content needs re-ingesting.** Two ingestion bugs were found and fixed. Paragraph boundaries were being silently destroyed before chunking ran, and every chunk was stored with the same position (`chunk_index` 0), so a source's text could read back, be edited, and reach voice calls out of order. Both fixes apply only to newly ingested content, and the lost order can't be recovered from the database. Delete and re-add any Knowledge Base entry added before these fixes.
- **Automatic phone number provisioning** (a "Get a phone number" button for business owners) is not built. It requires a real billing/subscription system first — without one, provisioned numbers would be charged to the platform's own account with no way to bill the business owner. Deliberately out of scope for now.
- **Phone numbers are self-declared.** An owner types their number into Settings. The platform checks that it's well formed and not used by another business, but not that the business owns it. A number only works if it belongs to the platform's Twilio account with its Voice webhook pointing at `/voice`. Fine for a pilot run by the platform operator; before open signups, number assignment should move to the operator or to provisioning.
- **PII/consent for call recording is notice-only, not interactive consent.** Every call plays a fixed "this call may be recorded" notice before the greeting, but the call proceeds regardless of the caller's reaction. Whether this is sufficient depends on local regulations, which haven't been formally researched for every jurisdiction this might be deployed in.
- **Voice latency has not been formally measured** (time-to-first-audio, turn-taking latency) — only judged informally during testing.
- **Formal intent-coverage testing** (systematically verifying each vertical's most common questions) has been done ad-hoc through manual testing, not as a structured checklist.
