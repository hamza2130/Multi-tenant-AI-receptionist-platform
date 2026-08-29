"""
auth.py

Week 3: real account ownership. Until now, tenants existed with a
generated API key but no concept of a business owner actually logging
in to manage them — every tenant was created directly via an internal
endpoint. This module adds real signup/login, so the Admin Console can
have an actual "your business, your login" flow.

Password hashing uses bcrypt directly (not passlib) — passlib has a
known compatibility break with modern bcrypt versions, verified during
this build rather than assumed.
"""

import uuid
from datetime import datetime, timedelta, timezone
import bcrypt
from jose import jwt, JWTError
from fastapi import Depends, HTTPException, Header
from sqlalchemy.orm import Session

from config import settings
from database import get_db
from models import User, Tenant, Config
import templates
import ingestion

ALGORITHM = "HS256"
TOKEN_EXPIRE_HOURS = 24 * 7  # 1 week — reasonable for a business owner's console session


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))


def create_access_token(user_id: str) -> str:
    payload = {
        "sub": user_id,
        "exp": datetime.now(timezone.utc) + timedelta(hours=TOKEN_EXPIRE_HOURS),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=ALGORITHM)


def signup(
    db: Session,
    business_name: str,
    vertical: str,
    email: str,
    password: str,
    template_key: str | None = None,
) -> dict:
    """
    Creates both a Tenant (the business) and a User (the login account
    that owns it) together, since in this console a signup always
    represents one business owner setting up their receptionist.

    If template_key is provided and matches a known vertical template
    (see templates.py), the new tenant's Settings (hours, services,
    booking rules, persona) and Knowledge Base are pre-seeded from that
    template — so onboarding is "pick a template, then customize"
    rather than starting from a completely blank slate. This is purely
    a starting point: everything seeded here remains fully editable by
    the business owner afterward, same as if they'd entered it by hand.
    """
    existing = db.query(User).filter(User.email == email).first()
    if existing:
        raise HTTPException(status_code=400, detail="An account with that email already exists.")

    api_key = f"sk_tenant_{uuid.uuid4().hex}"
    tenant = Tenant(name=business_name, vertical=vertical, api_key=api_key)
    db.add(tenant)
    db.flush()  # get tenant.id without committing yet

    user = User(email=email, hashed_password=hash_password(password), tenant_id=tenant.id)
    db.add(user)
    db.flush()  # get user.id without committing yet

    template = templates.get_template(template_key) if template_key else None
    if template:
        config = Config(
            tenant_id=tenant.id,
            hours=template["hours"],
            services=template["services"],
            booking_rules=template["booking_rules"],
            persona=template["persona"],
        )
        db.add(config)

    db.commit()
    db.refresh(user)

    # Starter knowledge base content is ingested as a separate step,
    # after the tenant/user/config are committed, since ingestion.py
    # does its own embedding + Qdrant writes tied to a real tenant.id.
    if template:
        ingestion.ingest_text(db, tenant.id, "doc", template["starter_knowledge_text"])

    token = create_access_token(user.id)
    return {"access_token": token, "tenant_id": tenant.id}


def login(db: Session, email: str, password: str) -> dict:
    user = db.query(User).filter(User.email == email).first()
    if not user or not verify_password(password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect email or password.")

    token = create_access_token(user.id)
    return {"access_token": token, "tenant_id": user.tenant_id}


def get_current_user(
    authorization: str = Header(...),
    db: Session = Depends(get_db),
) -> User:
    """
    FastAPI dependency for console endpoints — resolves the logged-in
    business owner from a Bearer token, distinct from tenant_resolver.py's
    API-key-based resolution (which is for the widget/voice channels,
    not a human logging into the console).
    """
    try:
        scheme, token = authorization.split(" ")
        if scheme.lower() != "bearer":
            raise ValueError
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
    except (ValueError, JWTError):
        raise HTTPException(status_code=401, detail="Invalid or expired session.")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired session.")
    return user
