"""
test_call_logging.py

Standalone test for Day 10's logging flow — simulates a finished
call's transcript and runs it through save_transcript() and
close_conversation(), against your REAL Postgres database. This
tests everything except starting an actual Twilio recording, which
needs a genuinely live call_sid to exist.

Run with:
    python test_call_logging.py
"""

from database import SessionLocal
from models import Tenant, Conversation, Channel
import call_logging


def main():
    print("=== Call Logging Test ===\n")

    db = SessionLocal()

    tenant = db.query(Tenant).filter(Tenant.name == "Sunrise Clinic").first()
    if not tenant:
        print("❌ Couldn't find the 'Sunrise Clinic' tenant — create it first via /docs.")
        return

    # Simulate a finished call: create a Conversation, same as
    # voice_server.py does when a real call starts.
    conversation = Conversation(tenant_id=tenant.id, channel=Channel.voice)
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    print(f"Created test conversation: {conversation.id}")

    # Simulate what Pipecat's context.messages would look like at
    # the end of a real call.
    fake_transcript = [
        {"role": "system", "content": "You are the receptionist..."},
        {"role": "user", "content": "Hi, what are your hours?"},
        {"role": "assistant", "content": "We're open Monday to Saturday, 9am to 6pm."},
        {"role": "user", "content": "Great, can you book me for tomorrow at 3pm? My name is Sara."},
        {"role": "assistant", "content": "You're booked for tomorrow at 3pm, Sara!"},
    ]

    print("\nSaving transcript...")
    call_logging.save_transcript(db, conversation.id, fake_transcript)

    print("Generating summary and closing conversation...")
    call_logging.close_conversation(db, conversation.id, recording_sid=None)

    db.refresh(conversation)
    print(f"\n✅ Summary: {conversation.summary}")
    print(f"✅ Ended at: {conversation.ended_at}")
    print(f"   (Recording URL is None — expected, since no real Twilio call happened)")

    db.close()


if __name__ == "__main__":
    main()
