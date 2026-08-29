"""
main.py

The full FastAPI application: Week 1 (tenants, ingestion, chat, RAG),
Week 2 (skills/tool-calling via agent.py), and Week 3 (auth, the
Admin Console's Knowledge Base routes, and browser-calling tokens).

Run with:
    uvicorn main:app --reload --port 8000
"""

import io
import uuid
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session
from pypdf import PdfReader
from bs4 import BeautifulSoup
import requests as http_requests
from twilio.jwt.access_token import AccessToken
from twilio.jwt.access_token.grants import VoiceGrant

from database import get_db, init_db
from models import Tenant, Conversation, Message, Channel, MessageRole, KnowledgeSource
from tenant_resolver import get_current_tenant
from config import settings
import ingestion
import agent
import auth
import templates

from models import Document
import vector_store

from models import Config
from models import Booking, Lead

app = FastAPI(title="AI Receptionist Platform")

# CORS: the embeddable widget is loaded on ARBITRARY client websites,
# and the Admin Console runs on a different port (3000) than this API
# (8000), so both need permissive CORS. Tenant/user isolation is
# still enforced via API keys and JWTs, not the request origin.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    init_db()


# ==================== Week 1: Tenant management ====================

class CreateTenantRequest(BaseModel):
    name: str
    vertical: str | None = None


@app.post("/admin/tenants")
def create_tenant(req: CreateTenantRequest, db: Session = Depends(get_db)):
    """
    Creates a new tenant with a generated API key. Internal/admin use —
    the real signup flow for a business owner is /auth/signup below.
    """
    api_key = f"sk_tenant_{uuid.uuid4().hex}"
    tenant = Tenant(name=req.name, vertical=req.vertical, api_key=api_key)
    db.add(tenant)
    db.commit()
    db.refresh(tenant)
    return {"tenant_id": tenant.id, "api_key": api_key}


# ==================== Week 1: Ingestion (API-key based) ====================

class IngestTextRequest(BaseModel):
    source_type: str  # "doc" | "url" | "faq"
    text: str


@app.post("/ingest/text")
def ingest_text(
    req: IngestTextRequest,
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
):
    """
    Ingests raw text into this tenant's knowledge base, using the
    tenant's API key. This is the original Week 1 path — the Admin
    Console (Week 3) uses the JWT-authenticated /console/ingest/*
    routes further down instead, since a logged-in owner doesn't need
    to know their own API key.
    """
    source_id = ingestion.ingest_text(db, tenant.id, req.source_type, req.text)
    return {"source_id": source_id, "status": "ready"}


# ==================== Week 1-2: Chat (widget / API-key based) ====================

class ChatRequest(BaseModel):
    message: str
    conversation_id: str | None = None


@app.post("/chat")
def chat(
    req: ChatRequest,
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
):
    """
    The endpoint the embeddable widget calls. Uses agent.py (Week 2),
    which combines RAG-grounded answers with tool-calling (booking,
    leads, messages, escalation) — not just plain Q&A.
    """
    if req.conversation_id:
        conversation = db.query(Conversation).filter(
            Conversation.id == req.conversation_id,
            Conversation.tenant_id == tenant.id,  # never trust a conversation_id blindly
        ).first()
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")
    else:
        conversation = Conversation(tenant_id=tenant.id, channel=Channel.chat)
        db.add(conversation)
        db.flush()

    history = [
        {"role": m.role.value, "content": m.content}
        for m in db.query(Message).filter(Message.conversation_id == conversation.id).order_by(Message.created_at).all()
    ]

    db.add(Message(conversation_id=conversation.id, role=MessageRole.user, content=req.message))

    result = agent.respond(db, tenant, conversation.id, req.message, history)

    db.add(Message(conversation_id=conversation.id, role=MessageRole.assistant, content=result["answer"]))
    db.commit()

    return {"conversation_id": conversation.id, "answer": result["answer"]}


# ==================== Week 3: Browser calling ====================

@app.get("/token")
def token():
    """
    Issues a short-lived Access Token so a webpage can call a tenant's
    receptionist over WebRTC (browser calling) — no phone number,
    carrier, or IDD/verification restrictions involved. Uses the
    TwiML App whose Voice Request URL points at voice_server.py's
    /voice endpoint.
    """
    access_token = AccessToken(
        settings.TWILIO_ACCOUNT_SID,
        settings.TWILIO_API_KEY_SID,
        settings.TWILIO_API_KEY_SECRET,
        identity="browser_caller",
    )
    voice_grant = VoiceGrant(
        outgoing_application_sid=settings.TWILIO_TWIML_APP_SID,
        incoming_allow=False,
    )
    access_token.add_grant(voice_grant)
    return {"token": access_token.to_jwt()}


# ==================== Week 3: Auth (Admin Console login) ====================

class SignupRequest(BaseModel):
    business_name: str
    vertical: str
    email: str
    password: str
    template_key: str | None = None  # e.g. "clinic", "real_estate", "restaurant" — optional


class LoginRequest(BaseModel):
    email: str
    password: str

class DayHours(BaseModel):
    open: str = "09:00"
    close: str = "17:00"
    closed: bool = False


class UpdateSettingsRequest(BaseModel):
    hours: dict[str, DayHours]
    services: list[str]
    booking_rules: dict
    persona: str
    whatsapp_number: str | None = None  


@app.post("/auth/signup")
def signup(req: SignupRequest, db: Session = Depends(get_db)):
    """
    Creates a business owner's account AND their tenant together —
    the real entry point for the Admin Console. If template_key is
    given, Settings and Knowledge Base are pre-seeded from that
    vertical template (see templates.py) so onboarding isn't a
    completely blank slate.
    """
    return auth.signup(db, req.business_name, req.vertical, req.email, req.password, req.template_key)


@app.post("/auth/login")
def login(req: LoginRequest, db: Session = Depends(get_db)):
    return auth.login(db, req.email, req.password)


@app.get("/auth/me")
def me(user=Depends(auth.get_current_user), db: Session = Depends(get_db)):
    """Returns the logged-in owner's tenant info — what the dashboard calls on load."""
    tenant = db.query(Tenant).filter(Tenant.id == user.tenant_id).first()
    return {
        "email": user.email,
        "tenant_id": tenant.id,
        "business_name": tenant.name,
        "vertical": tenant.vertical,
        "api_key": tenant.api_key,
        "phone_number": tenant.phone_number,
    }


# ==================== Week 3: Knowledge Base (Admin Console, JWT-based) ====================

class ConsoleIngestTextRequest(BaseModel):
    text: str


@app.post("/console/ingest/text")
def console_ingest_text(
    req: ConsoleIngestTextRequest,
    user=Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    print(f"[DEBUG] raw text repr (first 300 chars): {req.text[:300]!r}")
    source_id = ingestion.ingest_text(db, user.tenant_id, "doc", req.text)
    return {"source_id": source_id, "status": "ready"}

@app.post("/console/ingest/file")
async def console_ingest_file(
    file: UploadFile = File(...),
    user=Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    """Accepts a PDF upload, extracts its text, and runs it through the ingestion pipeline."""
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported right now.")

    contents = await file.read()
    try:
        reader = PdfReader(io.BytesIO(contents))
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
    except Exception:
        raise HTTPException(status_code=400, detail="Couldn't read that PDF — it may be corrupted or scanned/image-only.")

    if not text.strip():
        raise HTTPException(status_code=400, detail="No readable text found in that PDF.")

    source_id = ingestion.ingest_text(db, user.tenant_id, "doc", text)
    return {"source_id": source_id, "status": "ready", "characters_extracted": len(text)}


class ConsoleIngestUrlRequest(BaseModel):
    url: str


@app.post("/console/ingest/url")
def console_ingest_url(
    req: ConsoleIngestUrlRequest,
    user=Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    """Fetches a business's own webpage and extracts its readable text for ingestion."""
    try:
        response = http_requests.get(req.url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        response.raise_for_status()
    except Exception:
        raise HTTPException(status_code=400, detail="Couldn't reach that URL — check it's correct and publicly accessible.")

    soup = BeautifulSoup(response.text, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()
    text = soup.get_text(separator=" ", strip=True)

    if not text.strip():
        raise HTTPException(status_code=400, detail="No readable text found on that page.")

    source_id = ingestion.ingest_text(db, user.tenant_id, "url", text)
    return {"source_id": source_id, "status": "ready", "characters_extracted": len(text)}


@app.get("/console/knowledge-sources")
def list_knowledge_sources(user=Depends(auth.get_current_user), db: Session = Depends(get_db)):
    """Lists everything this tenant has ingested so far, for the Knowledge Base page."""
    sources = (
        db.query(KnowledgeSource)
        .filter(KnowledgeSource.tenant_id == user.tenant_id)
        .order_by(KnowledgeSource.created_at.desc())
        .all()
    )
    return [
        {"id": s.id, "type": s.type.value, "status": s.status, "created_at": s.created_at.isoformat()}
        for s in sources
    ]


# ==================== Health check ====================

@app.get("/health")
def health():
    return {"status": "ok"}

@app.delete("/console/knowledge-sources/{source_id}")
def delete_knowledge_source(
    source_id: str,
    user=Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    """
    Removes a knowledge source entirely — from Postgres (the source
    record and its chunks) AND from Qdrant (the actual embedded
    vectors), so outdated business info stops being retrievable, not
    just hidden from the console's list.
    """
    source = db.query(KnowledgeSource).filter(
        KnowledgeSource.id == source_id,
        KnowledgeSource.tenant_id == user.tenant_id,  # never trust source_id blindly — must belong to this tenant
    ).first()
    if not source:
        raise HTTPException(status_code=404, detail="Knowledge source not found.")

    documents = db.query(Document).filter(Document.source_id == source_id).all()
    point_ids = [doc.id for doc in documents]

    vector_store.delete_points(user.tenant_id, point_ids)

    for doc in documents:
        db.delete(doc)
    db.delete(source)
    db.commit()

    return {"deleted": True, "source_id": source_id, "chunks_removed": len(point_ids)}

@app.get("/console/knowledge-sources/{source_id}")
def get_knowledge_source_content(
    source_id: str,
    user=Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    """
    Returns a knowledge source's actual stored text content — what
    was pasted, or what got extracted from a PDF/webpage — so a
    business owner can verify exactly what their receptionist is
    answering from, not just see a metadata row.
    """
    source = db.query(KnowledgeSource).filter(
        KnowledgeSource.id == source_id,
        KnowledgeSource.tenant_id == user.tenant_id,  # never trust source_id blindly
    ).first()
    if not source:
        raise HTTPException(status_code=404, detail="Knowledge source not found.")

    documents = (
        db.query(Document)
        .filter(Document.source_id == source_id)
        .order_by(Document.chunk_index)  # preserves original text order — Document.id is a random UUID, not sequential
        .all()
    )

    return {
        "id": source.id,
        "type": source.type.value,
        "status": source.status,
        "created_at": source.created_at.isoformat(),
        "full_text": "\n\n".join(doc.chunk_text for doc in documents),
        "chunk_count": len(documents),
    }

class ConsoleUpdateKnowledgeSourceRequest(BaseModel):
    text: str


@app.put("/console/knowledge-sources/{source_id}")
def update_knowledge_source(
    source_id: str,
    req: ConsoleUpdateKnowledgeSourceRequest,
    user=Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    """
    Edits an existing knowledge source's content in place. Internally
    this removes the old chunks/vectors and re-ingests the new text
    fresh (reusing the same delete + ingest logic as elsewhere) — so
    from the business owner's side it behaves like a normal edit, but
    under the hood it's a clean replace, ensuring re-chunking and
    re-embedding stay correct rather than trying to patch existing
    chunks in place.
    """
    source = db.query(KnowledgeSource).filter(
        KnowledgeSource.id == source_id,
        KnowledgeSource.tenant_id == user.tenant_id,  # never trust source_id blindly
    ).first()
    if not source:
        raise HTTPException(status_code=404, detail="Knowledge source not found.")

    source_type = source.type.value

    documents = db.query(Document).filter(Document.source_id == source_id).all()
    point_ids = [doc.id for doc in documents]
    vector_store.delete_points(user.tenant_id, point_ids)
    for doc in documents:
        db.delete(doc)
    db.delete(source)
    db.commit()

    new_source_id = ingestion.ingest_text(db, user.tenant_id, source_type, req.text)
    return {"source_id": new_source_id, "status": "ready"}


@app.get("/console/settings")
def get_settings(user=Depends(auth.get_current_user), db: Session = Depends(get_db)):
    """
    Returns this tenant's structured settings.
    Creates sensible defaults on first visit.
    """

    config = db.query(Config).filter(
        Config.tenant_id == user.tenant_id
    ).first()

    if not config:
        default_hours = {
            day: {
                "open": "09:00",
                "close": "17:00",
                "closed": day in ("saturday", "sunday"),
            }
            for day in [
                "monday",
                "tuesday",
                "wednesday",
                "thursday",
                "friday",
                "saturday",
                "sunday",
            ]
        }

        config = Config(
            tenant_id=user.tenant_id,
            hours=default_hours,
            services=[],
            booking_rules={
                "advance_days": 30,
                "min_notice_hours": 2,
            },
            persona="A friendly, professional receptionist.",
            whatsapp_number=None,
        )

        db.add(config)
        db.commit()
        db.refresh(config)

    # IMPORTANT:
    # Return settings whether the config was newly created
    # OR already existed.
    return {
        "hours": config.hours,
        "services": config.services,
        "booking_rules": config.booking_rules,
        "persona": config.persona,
        "whatsapp_number": config.whatsapp_number,
    }


@app.put("/console/settings")
def update_settings(
    req: UpdateSettingsRequest,
    user=Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    config = db.query(Config).filter(
        Config.tenant_id == user.tenant_id
    ).first()

    if not config:
        config = Config(tenant_id=user.tenant_id)
        db.add(config)

    config.hours = {
        day: hours.model_dump()
        for day, hours in req.hours.items()
    }

    config.services = req.services
    config.booking_rules = req.booking_rules
    config.persona = req.persona
    config.whatsapp_number = req.whatsapp_number

    db.commit()
    db.refresh(config)

    return {
        "hours": config.hours,
        "services": config.services,
        "booking_rules": config.booking_rules,
        "persona": config.persona,
        "whatsapp_number": config.whatsapp_number,
    }


@app.get("/console/bookings")
def list_bookings(user=Depends(auth.get_current_user), db: Session = Depends(get_db)):
    """Everything booked through the receptionist — this is how the
    business owner actually sees appointments, since there's no
    calendar sync yet (deliberately out of scope for this MVP)."""
    bookings = (
        db.query(Booking)
        .filter(Booking.tenant_id == user.tenant_id)
        .order_by(Booking.datetime_value.desc())
        .all()
    )
    return [
        {
            "id": b.id,
            "datetime": b.datetime_value.isoformat(),
            "name": (b.contact or {}).get("name", "Unknown"),
            "phone": (b.contact or {}).get("phone", ""),
        }
        for b in bookings
    ]


@app.get("/console/leads")
def list_leads(user=Depends(auth.get_current_user), db: Session = Depends(get_db)):
    """
    Leads, messages, and escalations — all captured via the same Lead
    table (skills.py tags them with a prefix: [MESSAGE] or
    [ESCALATION], or no prefix for a plain captured lead).
    """
    leads = (
        db.query(Lead)
        .filter(Lead.tenant_id == user.tenant_id)
        .order_by(Lead.id.desc())
        .all()
    )

    def categorize(intent: str) -> str:
        if intent and intent.startswith("[ESCALATION]"):
            return "escalation"
        if intent and intent.startswith("[MESSAGE]"):
            return "message"
        return "lead"

    return [
        {
            "id": l.id,
            "name": l.name or "Unknown",
            "phone": l.phone or "",
            "intent": (l.intent or "").replace("[ESCALATION] ", "").replace("[MESSAGE] ", ""),
            "category": categorize(l.intent or ""),
        }
        for l in leads
    ]


@app.get("/console/stats")
def get_stats(user=Depends(auth.get_current_user), db: Session = Depends(get_db)):
    """
    Real counts for the Overview page's stat cards — replaces the
    hardcoded zeros from the first version of the dashboard.
    """
    return {
        "bookings": db.query(Booking).filter(Booking.tenant_id == user.tenant_id).count(),
        "leads": db.query(Lead).filter(Lead.tenant_id == user.tenant_id).count(),
        "conversations": db.query(Conversation).filter(Conversation.tenant_id == user.tenant_id).count(),
    }


@app.get("/auth/templates")
def get_templates():
    """
    Returns the available vertical templates for the signup page's
    template picker — key + display label only, not the full template
    content (which stays server-side).
    """
    return templates.list_templates()