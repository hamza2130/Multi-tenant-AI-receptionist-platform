"""
tenant_resolver.py

Resolves which tenant a request belongs to, based on their API key.
This is the multi-tenancy security boundary — every other file that
touches tenant data MUST go through this, and MUST filter every
database/vector query by the resulting tenant_id.

Per the plan: "cross-tenant leakage is a launch blocker." Treat this
file as the single most security-critical file in the codebase.
"""

from fastapi import Header, HTTPException, Depends
from sqlalchemy.orm import Session
from database import get_db
from models import Tenant


def get_current_tenant(
    x_api_key: str = Header(..., description="Tenant's API key"),
    db: Session = Depends(get_db),
) -> Tenant:
    """
    FastAPI dependency — inject this into any endpoint that handles
    tenant-specific data (chat, ingestion, config, bookings, etc.):

        @app.post("/chat")
        def chat(request: ChatRequest, tenant: Tenant = Depends(get_current_tenant)):
            ...

    Every query inside that endpoint must then filter by tenant.id.
    Never trust a tenant_id passed in the request body — always use
    the one resolved here from the authenticated API key.
    """
    tenant = db.query(Tenant).filter(Tenant.api_key == x_api_key).first()
    if not tenant:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return tenant
