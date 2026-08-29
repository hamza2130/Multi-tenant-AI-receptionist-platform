"""
voice_server.py

The real-time voice pipeline: a caller (real phone OR the Admin
Console's Test Sandbox, via browser) connects, and Pipecat runs
VAD -> STT -> LLM (with tools) -> TTS in real time, streamed over a
WebSocket (Twilio Media Streams).

Tenant resolution — two paths:
  - Real phone calls: resolved from the dialed number ("To" field).
  - Test Sandbox (browser) calls: resolved from an explicit tenant_id
    custom parameter, sent by the console for the logged-in owner's
    own business — this does NOT affect real phone call resolution,
    which is untouched and works exactly as before.

Day 10 (Ops): every call is logged — transcript, recording, and an
AI-generated summary — via call_logging.py.

Run with:
    uvicorn voice_server:app --reload --port 8001
"""

import json
from fastapi import FastAPI, WebSocket, Request, Response
from sqlalchemy.orm import Session

from config import settings
from database import SessionLocal
from models import Tenant, Conversation, Channel, Config, Document
import skills
from call_logging import start_call_recording, save_transcript, close_conversation
from agent import _format_settings
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.task import PipelineTask, PipelineParams
from pipecat.pipeline.runner import PipelineRunner
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.serializers.twilio import TwilioFrameSerializer
from pipecat.transports.websocket.fastapi import FastAPIWebsocketTransport, FastAPIWebsocketParams
from pipecat.services.deepgram.stt import DeepgramSTTService
from pipecat.services.elevenlabs.tts import ElevenLabsTTSService
from pipecat.services.groq.llm import GroqLLMService
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import LLMContextAggregatorPair
from pipecat.adapters.schemas.function_schema import FunctionSchema
from pipecat.adapters.schemas.tools_schema import ToolsSchema

app = FastAPI(title="AI Receptionist Platform — Voice")


def _get_tenant_by_phone(db: Session, phone_number: str) -> Tenant | None:
    """Resolves a tenant by their real Twilio phone number — used for real phone calls."""
    return db.query(Tenant).filter(Tenant.phone_number == phone_number).first()


@app.post("/voice")
async def voice_webhook(request: Request):
    """
    Twilio calls this the moment a call connects — either a real
    phone call (dialed number present) or a Test Sandbox browser call
    (an explicit tenant_id custom parameter present instead).
    """
    form = await request.form()
    dialed_number = form.get("To", "")
    tenant_id_param = form.get("tenant_id", "")  # present only for Test Sandbox calls
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
        # Test Sandbox (browser) call — resolve by the exact tenant_id
        # sent from the console, scoped to whichever business owner
        # is actually logged in.
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
            vad_analyzer=SileroVADAnalyzer(),
            serializer=serializer,
        ),
    )

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

    knowledge_docs = (
        db.query(Document)
        .filter(Document.tenant_id == tenant.id)
        .order_by(Document.chunk_index)
        .all()
    )
    knowledge_context = "\n\n".join(d.chunk_text for d in knowledge_docs)[:4000]
    if not knowledge_context:
        knowledge_context = "(No knowledge base content added yet.)"

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
    context_aggregator = LLMContextAggregatorPair(context)

    pipeline = Pipeline([
        transport.input(),
        stt,
        context_aggregator.user(),
        llm,
        tts,
        transport.output(),
        context_aggregator.assistant(),
    ])

    task = PipelineTask(pipeline, params=PipelineParams(allow_interruptions=True))
    runner = PipelineRunner()

    # Deterministic greeting — templated from the tenant's own data,
    # never LLM-generated, so it's instant (no generation latency),
    # costs nothing per call, and is always consistent and on-brand.
    #
    # Consent notice: every call is recorded (start_call_recording
    # above), so callers must be told this before anything else
    # happens — required in many jurisdictions, and standard practice
    # regardless. Kept as a separate, fixed sentence before the
    # greeting, not merged into it, so it reads as a clear, standard
    # disclosure rather than part of the friendly welcome message.
    from pipecat.frames.frames import TTSSpeakFrame
    consent_notice = "This call may be recorded for quality and training purposes."
    greeting = f"Thanks for calling {tenant.name}. How can I help you today?"
    await task.queue_frames([
        TTSSpeakFrame(consent_notice),
        TTSSpeakFrame(greeting),
    ])
    try:
        await runner.run(task)
    finally:
        # Day 10 (Ops): persist the transcript and generate a summary
        # now that the call has ended.
        save_transcript(db, conversation.id, context.messages)
        close_conversation(db, conversation.id, recording_sid)
        db.close()