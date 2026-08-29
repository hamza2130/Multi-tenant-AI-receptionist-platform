"""
skills.py

The receptionist's actions — booking, lead capture, message-taking,
and escalation. Same role as calendar_tools.py in the voice
receptionist project, but every function here is tenant-scoped:
every write includes tenant_id, so Tenant A's bookings/leads can
never be seen or affected by Tenant B.

These functions are called by the LLM via tool-calling (see agent.py).
They must NEVER be described to the caller in raw form — the LLM
always turns the return value into a natural sentence before it
reaches the caller. This is the plan's "no raw tool-call output"
guardrail.
"""

from datetime import datetime
from models import Config
from sqlalchemy.orm import Session
from models import Booking, Lead, Message
from zoneinfo import ZoneInfo
TENANT_TIMEZONE = ZoneInfo("Asia/Karachi")
from whatsapp import send_whatsapp_alert

# In skills.py, replace the existing book_appointment() function with
# this version — it now checks for a conflicting booking at the exact
# same date/time for this tenant BEFORE creating a new one, instead of
# blindly booking every request regardless of what's already taken.

def _check_hours(db: Session, tenant_id: str, dt: datetime) -> str | None:
    """
    Checks the requested booking time against the tenant's actual
    Settings (hours), deterministically in code — not left to the
    LLM's own date/day-of-week reasoning, which can be wrong (as
    observed: the model once said a date was "Sunday" and "closed",
    then booked it anyway as "Saturday" in the same reply).

    Returns an error message if the slot falls outside business
    hours, or None if it's fine.
    """
    config = db.query(Config).filter(Config.tenant_id == tenant_id).first()
    if not config or not config.hours:
        return None  # no hours configured yet — don't block bookings

    day_name = dt.strftime("%A").lower()  # e.g. "saturday" — computed by Python, not guessed by the LLM
    day_hours = config.hours.get(day_name)
    if not day_hours:
        return None

    if day_hours.get("closed"):
        return f"We're closed on {day_name.capitalize()}s — could you pick a different day?"

    requested_time = dt.strftime("%H:%M")
    if requested_time < day_hours.get("open", "00:00") or requested_time > day_hours.get("close", "23:59"):
        return f"That's outside our hours on {day_name.capitalize()} ({day_hours.get('open')}–{day_hours.get('close')}) — could you pick a different time?"

    return None


 
def book_appointment(db: Session, tenant_id: str, conversation_id: str,
                      datetime_str: str, name: str, phone: str = "") -> dict:
    """
    Books an appointment for this tenant only — now checks for a
    conflicting booking at the same date/time first, so two callers
    (or the same caller through two different channels) can't
    silently double-book the same slot.
    """
    try:
        dt_naive = datetime.fromisoformat(datetime_str)
        dt = dt_naive.replace(tzinfo=TENANT_TIMEZONE)
        hours_error = _check_hours(db, tenant_id, dt)
        if hours_error:
            return {"success": False, "message": hours_error}

    except ValueError:
        return {"success": False, "message": "I didn't understand that date/time — could you repeat it?"}

 
    existing = db.query(Booking).filter(
        Booking.tenant_id == tenant_id,
        Booking.datetime_value == dt,
    ).first()
 
    if existing:
        existing_name = (existing.contact or {}).get("name", "another caller")
        return {
            "success": False,
            "message": f"That slot is already booked (for {existing_name}). Could you pick a different time?",
        }
 
    booking = Booking(
        tenant_id=tenant_id,
        conversation_id=conversation_id,
        datetime_value=dt,
        contact={"name": name, "phone": phone},
    )
    db.add(booking)
    db.commit()
 
    return {
        "success": True,
        "message": f"Booked for {name} on {dt.strftime('%B %d at %I:%M %p')}.",
    }

def capture_lead(db: Session, tenant_id: str, conversation_id: str,
                  name: str, phone: str, intent: str) -> dict:
    """
    Saves a lead — someone interested but not booking yet (e.g. asking
    about pricing, availability of a service not currently offered,
    or just browsing).
    """
    lead = Lead(
        tenant_id=tenant_id,
        conversation_id=conversation_id,
        name=name,
        phone=phone,
        intent=intent,
    )
    db.add(lead)
    db.commit()

    return {"success": True, "message": "Got it — I've noted your interest and someone will follow up."}


def take_message(db: Session, tenant_id: str, conversation_id: str,
                  name: str, phone: str, message: str) -> dict:
    """
    Logs a message for the business to follow up on — used for
    anything the agent can't directly resolve (complaints, requests
    outside its tools, questions it doesn't have grounded data for).
    Reuses the Lead table with the message stored in `intent`, since
    the plan's data model doesn't define a separate messages table —
    tag it clearly so it's distinguishable in reporting.
    """
    lead = Lead(
        tenant_id=tenant_id,
        conversation_id=conversation_id,
        name=name,
        phone=phone,
        intent=f"[MESSAGE] {message}",
    )
    db.add(lead)
    db.commit()

    return {"success": True, "message": "I've passed that along to the team — they'll get back to you."}


def escalate(db: Session, tenant_id: str, conversation_id: str, reason: str, name: str = "", phone: str = "") -> dict:
    """
    Flags a conversation for human escalation — used for the hard
    safety cases (pricing, medical/sensitive topics, anything the
    agent shouldn't attempt) as well as caller-requested "talk to a
    human." Logged the same way as take_message, tagged distinctly.
    Also sends a WhatsApp alert to the business owner's configured
    number, if one is set, so they're notified immediately.
    """
    lead = Lead(
        tenant_id=tenant_id,
        conversation_id=conversation_id,
        name=name,
        phone=phone,
        intent=f"[ESCALATION] {reason}",
    )
    db.add(lead)
    db.commit()

    config = db.query(Config).filter(Config.tenant_id == tenant_id).first()
    if config and config.whatsapp_number:
        contact_line = f"\n\nFrom: {name}, {phone}" if name or phone else ""
        send_whatsapp_alert(
            config.whatsapp_number,
            f"🚨 New escalation from your AI receptionist:\n\n{reason}{contact_line}"
        )
    return {"success": True, "message": "I'll have someone from the team reach out to you directly about that."}


def get_day_of_week(date_str: str) -> dict:
    try:
        dt = datetime.fromisoformat(date_str)
        return {"success": True, "day_of_week": dt.strftime("%A")}
    except ValueError:
        return {"success": False, "message": "Invalid date format."}


def get_current_date() -> dict:
    from datetime import datetime
    now = datetime.now(TENANT_TIMEZONE)
    return {"success": True, "date": now.strftime("%Y-%m-%d"), "day_of_week": now.strftime("%A")}    