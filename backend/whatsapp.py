"""
whatsapp.py

Sends WhatsApp alerts via Twilio's WhatsApp API when an escalation or
message is captured, so a business owner is notified immediately
instead of only seeing it later in the Leads page.

Uses Twilio's WhatsApp Sandbox by default (TWILIO_WHATSAPP_FROM) —
works for testing without needing a fully approved WhatsApp Business
Profile. For production, this same code works once a real approved
WhatsApp sender is configured on the Twilio account; only the "from"
number changes.
"""

from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException
from config import settings


def send_whatsapp_alert(to_number: str, message: str) -> bool:
    """
    Sends a WhatsApp message. Returns True on success, False on
    failure — failure is always non-fatal to the caller (an
    escalation must never fail just because the WhatsApp alert
    couldn't be sent).
    """
    if not to_number:
        return False

    try:
        client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        client.messages.create(
            from_=f"whatsapp:{settings.TWILIO_WHATSAPP_FROM}",
            body=message,
            to=f"whatsapp:{to_number}",
        )
        return True
    except TwilioRestException as e:
        print(f"[WhatsApp] Failed to send alert to {to_number}: {e}")
        return False