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

from datetime import datetime, time, timedelta
from models import Config
from sqlalchemy.orm import Session
from models import Booking, Lead, Message
from zoneinfo import ZoneInfo
TENANT_TIMEZONE = ZoneInfo("Asia/Karachi")
from whatsapp import send_whatsapp_alert

DEFAULT_APPOINTMENT_MINUTES = 30


def _number(value) -> float | None:
    """A positive number from Settings, or None if it's missing or unusable."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def _tidy(number: float) -> str:
    """4.0 -> "4", 1.5 -> "1.5" — for reading a rule back to a caller."""
    return str(int(number)) if number.is_integer() else str(number)


def _parse_time(value, fallback: str) -> time:
    try:
        return datetime.strptime(value, "%H:%M").time()
    except (TypeError, ValueError):
        return datetime.strptime(fallback, "%H:%M").time()


def _is_open_at(requested: time, opens: time, closes: time) -> bool:
    """
    Whether a time falls inside one day's opening window.

    A closing time at or before the opening time means the day runs past
    midnight — a restaurant open 12:00 to 00:00, or to 02:00 — so the window
    is "opens until midnight" plus "midnight until closes". These used to be
    compared as text, which made "19:30" greater than "00:00" and so turned
    away every Friday and Saturday evening booking at a restaurant, the two
    busiest nights of its week.
    """
    if opens == closes:
        return True                       # open all day
    if closes > opens:
        return opens <= requested <= closes
    return requested >= opens or requested <= closes


def _check_booking_time(config: Config | None, dt: datetime) -> str | None:
    """
    Checks a requested slot against everything the business set in Settings:
    that it hasn't already passed, gives enough notice, isn't too far ahead,
    and falls on an open day and hour.

    All of it is decided here in code, never left to the model's own
    reasoning, which can be wrong (as observed: the model once called a date
    "Sunday" and "closed", then booked it anyway as "Saturday" in the same
    reply). Only hours were enforced before; notice and how-far-ahead were
    described in the prompt and never actually checked.

    Returns a sentence to say back to the caller, or None if the slot is fine.
    """
    now = datetime.now(TENANT_TIMEZONE)
    if dt <= now:
        return "That time has already passed — which day did you have in mind?"

    rules = (config.booking_rules if config else None) or {}

    notice_hours = _number(rules.get("min_notice_hours"))
    if notice_hours and dt < now + timedelta(hours=notice_hours):
        unit = "hour" if notice_hours == 1 else "hours"
        return f"We need at least {_tidy(notice_hours)} {unit} of notice — could you pick a later time?"

    advance_days = _number(rules.get("advance_days"))
    if advance_days and dt > now + timedelta(days=advance_days):
        unit = "day" if advance_days == 1 else "days"
        return f"We can only book up to {_tidy(advance_days)} {unit} ahead — could you pick a nearer date?"

    hours = (config.hours if config else None) or {}
    day_hours = hours.get(dt.strftime("%A").lower())  # the day, computed by Python, not guessed by the model
    if not day_hours:
        return None  # no hours set for that day — don't block the booking

    if day_hours.get("closed"):
        return f"We're closed on {dt.strftime('%A')}s — could you pick a different day?"

    opens = _parse_time(day_hours.get("open"), "00:00")
    closes = _parse_time(day_hours.get("close"), "23:59")
    if not _is_open_at(dt.time(), opens, closes):
        return (f"That's outside our hours on {dt.strftime('%A')} "
                f"({day_hours.get('open')}–{day_hours.get('close')}) — could you pick a different time?")

    return None


def book_appointment(db: Session, tenant_id: str, conversation_id: str,
                      datetime_str: str, name: str, phone: str = "") -> dict:
    """
    Books an appointment for this tenant only, once the requested slot has
    passed every rule in Settings and doesn't run into a nearby appointment.
    """
    try:
        dt = datetime.fromisoformat(datetime_str).replace(tzinfo=TENANT_TIMEZONE)
    except ValueError:
        return {"success": False, "message": "I didn't understand that date/time — could you repeat it?"}

    config = db.query(Config).filter(Config.tenant_id == tenant_id).first()

    problem = _check_booking_time(config, dt)
    if problem:
        return {"success": False, "message": problem}

    # Appointments take time, so two of them clash whenever they start
    # closer together than one appointment's length. Matching only identical
    # start times let a 10:15 booking through while 10:00 was still running.
    rules = (config.booking_rules if config else None) or {}
    length = timedelta(minutes=_number(rules.get("appointment_minutes")) or DEFAULT_APPOINTMENT_MINUTES)
    clash = db.query(Booking).filter(
        Booking.tenant_id == tenant_id,
        Booking.datetime_value > dt - length,
        Booking.datetime_value < dt + length,
    ).first()

    if clash:
        # Never name the other caller: a stranger on the phone shouldn't
        # learn who else has an appointment, which the old message told them.
        return {
            "success": False,
            "message": "Sorry, we're already booked around then — could you pick a different time?",
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