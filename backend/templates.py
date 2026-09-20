"""
templates.py

Vertical templates — pre-built starting configs + starter knowledge
base content for common business types, so a new tenant isn't
onboarded onto a completely blank Settings page and empty Knowledge
Base. Per the 3-week plan: "upload data → fill config → pick a
vertical template → test in sandbox → publish."

Each template provides sensible DEFAULTS a business owner can edit
afterward — nothing here is locked in.
"""

TEMPLATES = {
    "clinic": {
        "label": "Doctor / Clinic",
        "vertical": "clinic",
        "hours": {
            "monday":    {"open": "09:00", "close": "17:00", "closed": False},
            "tuesday":   {"open": "09:00", "close": "17:00", "closed": False},
            "wednesday": {"open": "09:00", "close": "17:00", "closed": False},
            "thursday":  {"open": "09:00", "close": "17:00", "closed": False},
            "friday":    {"open": "09:00", "close": "12:00", "closed": False},
            "saturday":  {"open": "10:00", "close": "14:00", "closed": False},
            "sunday":    {"open": "00:00", "close": "00:00", "closed": True},
        },
        "services": [
            "General Consultation",
            "Follow-up Visit",
            "Vaccinations",
            "Lab Tests",
            "Minor Procedures",
        ],
        "booking_rules": {"advance_days": 30, "min_notice_hours": 4, "appointment_minutes": 30},
        "persona": (
            "A calm, professional, and reassuring medical receptionist. "
            "Speaks clearly and simply, never gives medical advice, and "
            "always escalates health-related questions to a professional."
        ),
        "starter_knowledge_text": """This clinic offers general consultations, follow-up visits, vaccinations, basic lab tests, and minor outpatient procedures.

Appointments can be booked by phone or through this chat. New patients should arrive 10 minutes early to complete a short intake form. A valid ID is required at check-in.

Consultation fees vary by visit type and are confirmed at the front desk; this receptionist cannot quote exact prices.

For medical emergencies, patients should call emergency services directly rather than using this chat or phone line.

This clinic does not currently offer telehealth/video consultations — all appointments are in-person only.

Please update this Knowledge Base with your clinic's real address, phone number, doctor names/specialties, and actual services before publishing.""",
    },

    "real_estate": {
        "label": "Real Estate Agency",
        "vertical": "real_estate",
        "hours": {
            "monday":    {"open": "10:00", "close": "19:00", "closed": False},
            "tuesday":   {"open": "10:00", "close": "19:00", "closed": False},
            "wednesday": {"open": "10:00", "close": "19:00", "closed": False},
            "thursday":  {"open": "10:00", "close": "19:00", "closed": False},
            "friday":    {"open": "10:00", "close": "19:00", "closed": False},
            "saturday":  {"open": "11:00", "close": "17:00", "closed": False},
            "sunday":    {"open": "00:00", "close": "00:00", "closed": True},
        },
        "services": [
            "Property Viewings",
            "Buying Consultation",
            "Selling Consultation",
            "Rental Listings",
            "Property Valuation",
        ],
        "booking_rules": {"advance_days": 14, "min_notice_hours": 2, "appointment_minutes": 60},
        "persona": (
            "A friendly, knowledgeable, and proactive real estate assistant. "
            "Helps callers book property viewings and consultations, and "
            "captures their interest (budget, area, property type) as a "
            "lead when they're not ready to book yet."
        ),
        "starter_knowledge_text": """This agency helps clients buy, sell, and rent residential and commercial properties, and offers free property valuations for sellers.

Property viewings can be scheduled directly through this chat or by phone. For sellers, an initial consultation is used to discuss listing price and marketing strategy.

This receptionist cannot quote exact property prices, commission rates, or availability of specific listings not yet described to it — these should be confirmed with an agent directly.

Please update this Knowledge Base with your agency's real service areas, current featured listings, agent names, and actual contact details before publishing.""",
    },

    "restaurant": {
        "label": "Restaurant",
        "vertical": "restaurant",
        "hours": {
            "monday":    {"open": "12:00", "close": "23:00", "closed": False},
            "tuesday":   {"open": "12:00", "close": "23:00", "closed": False},
            "wednesday": {"open": "12:00", "close": "23:00", "closed": False},
            "thursday":  {"open": "12:00", "close": "23:00", "closed": False},
            "friday":    {"open": "12:00", "close": "00:00", "closed": False},
            "saturday":  {"open": "12:00", "close": "00:00", "closed": False},
            "sunday":    {"open": "13:00", "close": "22:00", "closed": False},
        },
        "services": [
            "Table Reservations",
            "Takeaway Orders",
            "Private Events",
            "Delivery",
        ],
        "booking_rules": {"advance_days": 21, "min_notice_hours": 1, "appointment_minutes": 90},
        "persona": (
            "A warm, welcoming host taking table reservations. Confirms "
            "party size, date, time, and a contact number for every "
            "booking, and mentions the restaurant is happy to accommodate "
            "dietary requirements if asked."
        ),
        "starter_knowledge_text": """This restaurant accepts table reservations by phone or chat, and offers takeaway and delivery.

Reservations for parties larger than 8 people should be discussed directly with the restaurant, as they may require a deposit or private room booking.

This receptionist cannot quote menu prices — please check the menu directly or ask staff for current pricing.

Please update this Knowledge Base with your restaurant's real cuisine type, signature dishes, dietary accommodation details (halal, vegetarian, allergies), delivery radius, and actual contact details before publishing.""",
    },
}


def get_template(key: str) -> dict | None:
    return TEMPLATES.get(key)


def list_templates() -> list[dict]:
    """Returns template metadata for the picker UI — key + label only."""
    return [{"key": k, "label": v["label"]} for k, v in TEMPLATES.items()]