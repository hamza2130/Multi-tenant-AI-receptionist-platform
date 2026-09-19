"""
call_logging.py

Day 10 (Ops): persists what actually happened on a call or chat —
transcripts, a recording (voice only), and an AI-generated summary —
so a business owner can review it later, and so issues can be
debugged after the fact rather than only while watching a live
terminal.

Used by both channels:
- voice_server.py calls these at call start/end
- (text channel already logs messages turn-by-turn in main.py;
   generate_summary() can be reused there too)
"""

from datetime import datetime, timezone
from sqlalchemy.orm import Session
from twilio.rest import Client as TwilioClient

from config import settings
from models import Conversation, Message, MessageRole
from llm_client import generate


def start_call_recording(call_sid: str) -> str | None:
    """
    Starts recording an in-progress Twilio call via the REST API
    (separate from the Media Stream used for the live audio pipeline).
    Returns the recording SID, or None if it fails — recording failure
    should never break the call itself, so this is caught, not raised.

    The Twilio client is created here, per call, rather than at import:
    Twilio's SDK refuses empty credentials, and building it at import
    stopped the whole voice server from starting without a Twilio
    account — including for WebRTC test calls, which never touch Twilio.
    """
    try:
        twilio_client = TwilioClient(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        recording = twilio_client.calls(call_sid).recordings.create()
        return recording.sid
    except Exception as e:
        print(f"[call_logging] Failed to start recording: {e}")
        return None


def save_transcript(db: Session, conversation_id: str, pipecat_messages: list):
    """
    Persists a Pipecat conversation's message history into the
    Message table, so it's queryable the same way text-channel
    messages already are. Skips the system prompt (role="system") —
    that's configuration, not something that was actually said.
    """
    for msg in pipecat_messages:
        role = msg.get("role")
        content = msg.get("content")
        if role not in ("user", "assistant") or not content:
            continue
        db.add(Message(
            conversation_id=conversation_id,
            role=MessageRole.user if role == "user" else MessageRole.assistant,
            content=content,
        ))
    db.commit()


def generate_summary(transcript_text: str) -> str:
    """
    Asks the LLM for a short summary of the conversation — a few
    sentences a business owner could skim instead of reading the full
    transcript. Kept deliberately simple: no tool-calling needed here.
    """
    if not transcript_text.strip():
        return "(No conversation content to summarize.)"

    system_prompt = (
        "Summarize the following receptionist conversation in 2-3 short sentences, "
        "for a business owner to skim. Note the caller's request, what was resolved "
        "(e.g. booked, escalated, message taken), and anything that needs follow-up."
    )
    return generate(system_prompt, transcript_text)


def close_conversation(db: Session, conversation_id: str, recording_sid: str | None = None):
    """
    Called once a call or chat ends: builds a summary from the
    messages just saved, records the recording reference (if any),
    and marks the conversation as ended.
    """
    conversation = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not conversation:
        return

    messages = db.query(Message).filter(Message.conversation_id == conversation_id).order_by(Message.created_at).all()
    transcript_text = "\n".join(f"{m.role.value}: {m.content}" for m in messages)

    conversation.summary = generate_summary(transcript_text)
    conversation.ended_at = datetime.now(timezone.utc)
    if recording_sid:
        conversation.recording_url = (
            f"https://api.twilio.com/2010-04-01/Accounts/{settings.TWILIO_ACCOUNT_SID}"
            f"/Recordings/{recording_sid}"
        )

    db.commit()
