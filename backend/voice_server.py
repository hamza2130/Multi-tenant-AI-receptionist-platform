"""
voice_server.py

The real-time voice pipeline: a caller connects, and Pipecat runs
VAD -> STT -> LLM (with tools) -> TTS in real time.

Three ways in, one shared pipeline (run_receptionist):
  - Real phone calls: Twilio Media Streams over a WebSocket (/voice then
    /ws), resolved from the dialed number ("To" field).
  - Embedded widget calls: also via Twilio (browser -> TwiML App -> /voice),
    resolved from the tenant's API key.
  - Test Sandbox calls: peer-to-peer WebRTC straight from the Admin Console
    (/webrtc/offer), resolved from the logged-in owner's session. No Twilio
    account, phone number, or ngrok needed — this is the free way to test
    the whole voice pipeline.

Day 10 (Ops): every call is logged — transcript, recording (Twilio calls
only), and an AI-generated summary — via call_logging.py.

Run with:
    uvicorn voice_server:app --reload --port 8001
"""

import json
from fastapi import FastAPI, WebSocket, Request, Response, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session

from config import settings
from database import SessionLocal
from models import Tenant, Conversation, Channel, Config, Document, KnowledgeSource
import auth
import skills
from call_logging import start_call_recording, save_transcript, close_conversation
from agent import _format_settings
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.task import PipelineTask
from pipecat.pipeline.runner import PipelineRunner
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.frames.frames import TTSSpeakFrame
from pipecat.serializers.twilio import TwilioFrameSerializer
from pipecat.transports.base_transport import BaseTransport, TransportParams
from pipecat.transports.websocket.fastapi import FastAPIWebsocketTransport, FastAPIWebsocketParams
from pipecat.transports.smallwebrtc.connection import SmallWebRTCConnection
from pipecat.transports.smallwebrtc.request_handler import SmallWebRTCRequest, SmallWebRTCRequestHandler
from pipecat.transports.smallwebrtc.transport import SmallWebRTCTransport
from pipecat.services.deepgram.stt import DeepgramSTTService
from pipecat.services.elevenlabs.tts import ElevenLabsTTSService
from pipecat.services.groq.llm import GroqLLMService
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import (
    LLMContextAggregatorPair,
    LLMUserAggregatorParams,
)
from pipecat.adapters.schemas.function_schema import FunctionSchema
from pipecat.adapters.schemas.tools_schema import ToolsSchema

app = FastAPI(title="AI Receptionist Platform — Voice")

# The Admin Console (port 3000) calls /webrtc/offer straight from the
# browser. Who may start a call is decided by the owner's session token,
# not by the request's origin — same reasoning as main.py.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Tracks every live Test Sandbox peer connection until it closes. No ICE
# servers: host candidates are enough when the console and this server
# run on the same machine or LAN. Testing against a remote server would
# need STUN/TURN servers passed in here.
webrtc_handler = SmallWebRTCRequestHandler()


def _get_tenant_by_phone(db: Session, phone_number: str) -> Tenant | None:
    """Resolves a tenant by their real Twilio phone number — used for real phone calls."""
    return db.query(Tenant).filter(Tenant.phone_number == phone_number).first()


def _knowledge_context(db: Session, tenant_id: str) -> str:
    """
    The tenant's knowledge base as one block of text, in reading order:
    oldest source first, and each source's chunks in their original
    sequence. Ordering by chunk_index alone would interleave sources
    (every source's first chunk, then every source's second chunk...).
    """
    documents = (
        db.query(Document)
        .join(KnowledgeSource, Document.source_id == KnowledgeSource.id)
        .filter(Document.tenant_id == tenant_id)
        .order_by(KnowledgeSource.created_at, KnowledgeSource.id, Document.chunk_index)
        .all()
    )
    knowledge_context = "\n\n".join(d.chunk_text for d in documents)[:4000]
    return knowledge_context or "(No knowledge base content added yet.)"


async def run_receptionist(
    transport: BaseTransport,
    db: Session,
    tenant: Tenant,
    conversation: Conversation,
    recording_sid: str | None = None,
):
    """
    Runs one call from greeting to hang-up, on any transport. Phone,
    widget, and Test Sandbox calls all go through here, so a prompt rule,
    skill, or tool schema can't drift between them. Owns `db` for the
    call's lifetime and closes it when the call ends.
    """
    stt = DeepgramSTTService(
        api_key=settings.DEEPGRAM_API_KEY,
        settings=DeepgramSTTService.Settings(
            model="nova-2-general",
            language="multi",
            keywords=["Alishba", "Hafeez", "Kashaf", "Fatima", "Rahila", "Alyar"],
            smart_format=True,
        ),
    )
    tts = ElevenLabsTTSService(api_key=settings.ELEVENLABS_API_KEY, voice_id=settings.ELEVENLABS_VOICE_ID)
    llm = GroqLLMService(api_key=settings.GROQ_API_KEY, model=settings.GROQ_MODEL)

    # Ground the voice channel in this tenant's real data, same as the
    # text channel already does — previously this system prompt only
    # had tenant.name/vertical, meaning voice answers (and the
    # escalate-vs-say-honestly decision) were based on the LLM's own
    # guesswork about the business, not its actual Settings/Knowledge
    # Base. Fetched once at call start (not per-turn RAG, since this
    # pipeline doesn't have a retrieval step between STT and LLM) —
    # good enough to ground the whole call, and far better than none.
    config = db.query(Config).filter(Config.tenant_id == tenant.id).first()
    settings_section = _format_settings(config)
    knowledge_context = _knowledge_context(db, tenant.id)

    # Register the same four skills as the text channel (agent.py),
    # so booking/leads/messages/escalation behave identically on
    # both channels.
    async def _make_handler(skill_fn):
        async def handler(params):
            result = skill_fn(db, tenant.id, conversation.id, **params.arguments)
            await params.result_callback(result)
        return handler

    llm.register_function("book_appointment", await _make_handler(skills.book_appointment))
    llm.register_function("capture_lead", await _make_handler(skills.capture_lead))
    llm.register_function("take_message", await _make_handler(skills.take_message))
    llm.register_function("escalate", await _make_handler(skills.escalate))

    async def _handle_get_day_of_week(params):
        result = skills.get_day_of_week(**params.arguments)
        await params.result_callback(result)

    async def _handle_get_current_date(params):
        result = skills.get_current_date()
        await params.result_callback(result)

    llm.register_function("get_day_of_week", _handle_get_day_of_week)
    llm.register_function("get_current_date", _handle_get_current_date)

    tools = ToolsSchema(standard_tools=[
        FunctionSchema(
            name="book_appointment", description="Book an appointment for the caller.",
            properties={
                "datetime_str": {"type": "string", "description": "ISO format, e.g. 2026-07-30T14:00:00"},
                "name": {"type": "string"}, "phone": {"type": "string"},
            },
            required=["datetime_str", "name"],
        ),
        FunctionSchema(
            name="capture_lead", description="Log a caller's interest when they're not ready to book yet.",
            properties={"name": {"type": "string"}, "phone": {"type": "string"}, "intent": {"type": "string"}},
            required=["name", "intent"],
        ),
        FunctionSchema(
            name="take_message", description="Log a message for the business to follow up on.",
            properties={"name": {"type": "string"}, "phone": {"type": "string"}, "message": {"type": "string"}},
            required=["name", "message"],
        ),
        FunctionSchema(
            name="escalate", description="Flag this conversation for a human — pricing, medical/sensitive topics, or anything you should not answer.",
            properties={"reason": {"type": "string"}},
            required=["reason"],
        ),
        FunctionSchema(
            name="get_day_of_week", description="Get the exact day of the week for a given date. ALWAYS use this instead of calculating the day of week yourself.",
            properties={"date_str": {"type": "string", "description": "Date in YYYY-MM-DD format"}},
            required=["date_str"],
        ),
        FunctionSchema(
            name="get_current_date", description="Get today's actual current date and day of week. ALWAYS use this first if the caller references 'today', 'tomorrow', 'this Friday', or any relative date — never assume or guess today's date yourself.",
            properties={},
            required=[],
        ),
    ])
    system_prompt = f"""You are the AI receptionist for {tenant.name}, a {tenant.vertical or "general"} business, speaking on a live phone call.

{settings_section}

Answer using the STRUCTURED DETAILS above as the authoritative source
for hours, services, and booking rules. For anything not covered
there, use the CONTEXT below, drawn from this business's own
knowledge base. Never guess or use outside knowledge about what this
business does.

Keep responses short and natural — this is spoken aloud, not read as text.

HARD RULES:
1. NEVER state a price. If asked about cost, use the escalate tool.
2. NEVER discuss medical/health details or give advice yourself. If a
   caller describes symptoms or a medical concern, first judge whether
   this business's own STRUCTURED DETAILS/CONTEXT actually relate to
   medical or health matters. If they do, use the escalate tool. If
   not, say so directly and politely, and suggest the caller consult
   a doctor — do not escalate or take a message implying this
   business will follow up on something it has no connection to.
3. Before escalating or taking a message for any unanswered question,
   judge whether it's genuinely something this business could
   plausibly follow up on, versus something clearly outside what this
   business does per STRUCTURED DETAILS/CONTEXT. If it's clearly
   unrelated to this business entirely, say so honestly instead of
   escalating.
4. Before calling book_appointment, always repeat the caller's name, phone
   number, and requested date/time back to them out loud and get explicit
   confirmation ("just to confirm, that's [name], [date] at [time] — is
   that right?"). Only call the tool after they confirm. Phone audio and
   speech recognition can mishear names and numbers, so this confirmation
   step is mandatory, not optional.
5. Never read tool results back as raw data — always respond in natural spoken language.
6. Always ask for a contact phone number before finalizing a booking,
   even though it is not a strictly required field — the business
   needs a way to reach the caller.
7. When a tool call fails, explain the reason based only on what the
   tool actually told you — never invent or guess a reason (not the
   day of week, not business hours, nothing you weren't explicitly given).
8. NEVER compute or guess a day of the week yourself — always call
   get_day_of_week for any date you need to reference.
9. NEVER assume or guess today's date. For "today", "tomorrow", "this
   Friday", or any relative date, call get_current_date first.
10. Whenever you use the escalate tool, you must first collect the
    caller's name and phone number out loud if you don't already have
    them in this conversation — never escalate without contact info.
    Pass the FULL context of what they need (not just a short label)
    as the reason, so the business owner has everything they need to
    follow up without re-contacting the customer. After escalating,
    always tell the caller clearly that a team member will contact
    them shortly.

CONTEXT:
{knowledge_context}
"""

    context = LLMContext(messages=[{"role": "system", "content": system_prompt}], tools=tools)
    # Voice activity detection belongs on the user aggregator in Pipecat
    # 1.x. It used to be passed in the transport params, which silently
    # ignore unknown fields — so calls ran with no VAD, which both turn
    # detection and barge-in (interrupting the bot) rely on.
    context_aggregator = LLMContextAggregatorPair(
        context,
        user_params=LLMUserAggregatorParams(vad_analyzer=SileroVADAnalyzer()),
    )

    pipeline = Pipeline([
        transport.input(),
        stt,
        context_aggregator.user(),
        llm,
        tts,
        transport.output(),
        context_aggregator.assistant(),
    ])

    # RTVI is the message protocol of Pipecat's own client SDKs, which no
    # caller here uses (the console speaks plain WebRTC, phones speak Twilio).
    # Left on, it logs a warning for every console message, like "hangup".
    task = PipelineTask(pipeline, enable_rtvi=False)

    # Deterministic greeting — templated from the tenant's own data,
    # never LLM-generated, so it's instant (no generation latency),
    # costs nothing per call, and is always consistent and on-brand.
    # Queued once the caller is actually connected, so a WebRTC caller
    # whose audio isn't flowing yet doesn't miss the start of it.
    #
    # Consent notice: Twilio calls are recorded (start_call_recording),
    # so callers must be told this before anything else happens —
    # required in many jurisdictions, and standard practice regardless.
    # Kept as a separate, fixed sentence before the greeting, not merged
    # into it, so it reads as a clear, standard disclosure rather than
    # part of the friendly welcome message.
    consent_notice = "This call may be recorded for quality and training purposes."
    greeting = f"Thanks for calling {tenant.name}. How can I help you today?"

    @transport.event_handler("on_client_connected")
    async def on_client_connected(transport, client):
        await task.queue_frames([
            TTSSpeakFrame(consent_notice),
            TTSSpeakFrame(greeting),
        ])

    # Without this the pipeline outlives the caller until Pipecat's idle
    # timeout (5 minutes), and the transcript and summary wait with it.
    @transport.event_handler("on_client_disconnected")
    async def on_client_disconnected(transport, client):
        await task.cancel()

    # Many calls share this one uvicorn process, so no call should take
    # over Ctrl+C — that's the server's to handle.
    runner = PipelineRunner(handle_sigint=False)
    try:
        await runner.run(task)
    finally:
        # Day 10 (Ops): persist the transcript and generate a summary
        # now that the call has ended.
        save_transcript(db, conversation.id, context.messages)
        close_conversation(db, conversation.id, recording_sid)
        db.close()


# ==================== Twilio: phone and widget calls ====================

@app.post("/voice")
async def voice_webhook(request: Request):
    """
    Twilio calls this the moment a call connects — either a real
    phone call (dialed number present) or an embedded widget browser
    call (the tenant's API key as a custom parameter instead).
    """
    form = await request.form()
    dialed_number = form.get("To", "")
    tenant_id_param = form.get("tenant_id", "")  # legacy Test Sandbox calls only — see websocket_endpoint
    tenant_api_key_param = form.get("tenant_api_key", "")  # present only for widget calls

    ws_url = f"{settings.PUBLIC_BASE_URL.replace('https://', 'wss://').replace('http://', 'ws://')}/ws"

    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Connect>
    <Stream url="{ws_url}">
      <Parameter name="dialed_number" value="{dialed_number}" />
      <Parameter name="tenant_id" value="{tenant_id_param}" />
      <Parameter name="tenant_api_key" value="{tenant_api_key_param}" />
    </Stream>
  </Connect>
</Response>"""
    return Response(content=twiml, media_type="text/xml")


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()

    # Twilio's Media Stream protocol sends "connected" then "start"
    # as the first two JSON messages before any audio.
    start_data = websocket.iter_text()
    await start_data.__anext__()  # "connected" event, not needed
    call_data = json.loads(await start_data.__anext__())  # "start" event

    stream_sid = call_data["start"]["streamSid"]
    call_sid = call_data["start"]["callSid"]
    custom_params = call_data["start"]["customParameters"]
    dialed_number = custom_params.get("dialed_number", "")
    tenant_id_param = custom_params.get("tenant_id", "")
    tenant_api_key_param = custom_params.get("tenant_api_key", "")

    db = SessionLocal()

    if tenant_id_param:
        # Legacy Twilio-based Test Sandbox call. The console now tests
        # over WebRTC (/webrtc/offer) instead, so nothing sends this
        # parameter anymore — and it isn't authenticated.
        tenant = db.query(Tenant).filter(Tenant.id == tenant_id_param).first()
    elif tenant_api_key_param:
        # Embedded widget (browser) call — resolve by the tenant's API
        # key, the same identifier the widget already uses for chat.
        tenant = db.query(Tenant).filter(Tenant.api_key == tenant_api_key_param).first()
    else:
        # Real phone call — resolve by the dialed number, unchanged
        # from how this has always worked.
        tenant = _get_tenant_by_phone(db, dialed_number)

    print(f"[DEBUG] tenant_id_param={tenant_id_param!r} tenant_api_key_param={tenant_api_key_param!r} dialed_number={dialed_number!r} resolved_tenant={tenant}")

    if not tenant:
        await websocket.close()
        db.close()
        return

    # Day 10 (Ops): log this call as a Conversation, and start a
    # Twilio recording via the REST API (separate from the Media
    # Stream used for the live audio pipeline). Recording failure is
    # non-fatal — it should never block the call itself.
    conversation = Conversation(tenant_id=tenant.id, channel=Channel.voice)
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    recording_sid = start_call_recording(call_sid)

    serializer = TwilioFrameSerializer(
        stream_sid=stream_sid,
        call_sid=call_sid,
        account_sid=settings.TWILIO_ACCOUNT_SID,
        auth_token=settings.TWILIO_AUTH_TOKEN,
    )

    transport = FastAPIWebsocketTransport(
        websocket=websocket,
        params=FastAPIWebsocketParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
            add_wav_header=False,
            serializer=serializer,
        ),
    )

    await run_receptionist(transport, db, tenant, conversation, recording_sid)


# ==================== WebRTC: Test Sandbox calls ====================

class WebRTCOffer(BaseModel):
    sdp: str
    type: str


@app.post("/webrtc/offer")
async def webrtc_offer(
    offer: WebRTCOffer,
    background_tasks: BackgroundTasks,
    user=Depends(auth.get_current_user),
):
    """
    Starts a Test Sandbox call. The console sends its WebRTC offer with
    the owner's session token and gets an answer back; audio then flows
    browser-to-server directly. The call always reaches the logged-in
    owner's own receptionist — the tenant comes from the token, never
    from the request body.
    """
    tenant_id = user.tenant_id

    async def start_call(connection: SmallWebRTCConnection):
        # The handler awaits this before returning the answer, so the
        # call itself has to run after the response, not inline.
        background_tasks.add_task(_run_webrtc_call, connection, tenant_id)

    return await webrtc_handler.handle_web_request(
        SmallWebRTCRequest(sdp=offer.sdp, type=offer.type),
        start_call,
    )


async def _run_webrtc_call(connection: SmallWebRTCConnection, tenant_id: str):
    db = SessionLocal()
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        await connection.disconnect()
        db.close()
        return

    conversation = Conversation(tenant_id=tenant.id, channel=Channel.voice)
    db.add(conversation)
    db.commit()
    db.refresh(conversation)

    transport = SmallWebRTCTransport(
        webrtc_connection=connection,
        params=TransportParams(audio_in_enabled=True, audio_out_enabled=True),
    )

    # The console sends {"type": "hangup"} over the data channel when the
    # owner hangs up, so the call ends on an explicit signal. A browser that
    # closes its connection cleanly (tab closed) is noticed within a second
    # anyway; this matters most when that close never arrives. Closing our
    # side fires on_client_disconnected, which ends the call.
    @transport.event_handler("on_app_message")
    async def on_app_message(transport, message, sender):
        if isinstance(message, dict) and message.get("type") == "hangup":
            await connection.disconnect()

    await run_receptionist(transport, db, tenant, conversation)
