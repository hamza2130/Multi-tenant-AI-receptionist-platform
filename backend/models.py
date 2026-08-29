"""
models.py

SQLAlchemy models matching the data model from the 3-week plan.
This is the single source of truth for the platform's database schema.

Multi-tenancy note: almost every table has a tenant_id foreign key.
Every query in this codebase MUST filter by tenant_id — this is the
hard security boundary the plan calls a launch blocker if violated.
"""

import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column, String, Text,Integer, DateTime, ForeignKey, JSON, Enum as SAEnum
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base, relationship
import enum

Base = declarative_base()


def gen_uuid():
    return str(uuid.uuid4())


def utcnow():
    return datetime.now(timezone.utc)


class TenantStatus(str, enum.Enum):
    sandbox = "sandbox"
    published = "published"
    suspended = "suspended"


class SourceType(str, enum.Enum):
    doc = "doc"
    url = "url"
    faq = "faq"


class Channel(str, enum.Enum):
    voice = "voice"
    chat = "chat"


class MessageRole(str, enum.Enum):
    user = "user"
    assistant = "assistant"
    tool = "tool"


class Tenant(Base):
    __tablename__ = "tenants"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    name = Column(String, nullable=False)
    vertical = Column(String, nullable=True)
    status = Column(SAEnum(TenantStatus), default=TenantStatus.sandbox, nullable=False)
    api_key = Column(String, unique=True, nullable=False, index=True)
    phone_number = Column(String, unique=True, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)

    knowledge_sources = relationship("KnowledgeSource", back_populates="tenant")
    config = relationship("Config", back_populates="tenant", uselist=False)
    owner = relationship("User", back_populates="tenant", uselist=False)   # ← add this line


class KnowledgeSource(Base):
    __tablename__ = "knowledge_sources"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    tenant_id = Column(UUID(as_uuid=False), ForeignKey("tenants.id"), nullable=False, index=True)
    type = Column(SAEnum(SourceType), nullable=False)
    status = Column(String, default="pending")  # pending | processing | ready | failed
    created_at = Column(DateTime(timezone=True), default=utcnow)

    tenant = relationship("Tenant", back_populates="knowledge_sources")
    documents = relationship("Document", back_populates="source")


class Document(Base):
    """A single chunk of text from a knowledge source, ready for embedding."""
    __tablename__ = "documents"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    source_id = Column(UUID(as_uuid=False), ForeignKey("knowledge_sources.id"), nullable=False, index=True)
    tenant_id = Column(UUID(as_uuid=False), ForeignKey("tenants.id"), nullable=False, index=True)
    chunk_text = Column(Text, nullable=False)
    doc_metadata = Column(JSON, default=dict)
    chunk_index = Column(Integer, default=0)
    source = relationship("KnowledgeSource", back_populates="documents")


class Config(Base):
    __tablename__ = "configs"

    tenant_id = Column(UUID(as_uuid=False), ForeignKey("tenants.id"), primary_key=True)
    hours = Column(JSON, default=dict)
    services = Column(JSON, default=list)
    booking_rules = Column(JSON, default=dict)
    persona = Column(Text, default="A friendly, professional receptionist.")
    whatsapp_number = Column(String, nullable=True)  # e.g. "+923001234567" — receives escalation alerts
    tenant = relationship("Tenant", back_populates="config")


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    tenant_id = Column(UUID(as_uuid=False), ForeignKey("tenants.id"), nullable=False, index=True)
    channel = Column(SAEnum(Channel), nullable=False)
    started_at = Column(DateTime(timezone=True), default=utcnow)
    ended_at = Column(DateTime(timezone=True), nullable=True)
    recording_url = Column(String, nullable=True)  # voice channel only — Twilio recording URL
    summary = Column(Text, nullable=True)  # AI-generated summary, filled in after the call/chat ends

    messages = relationship("Message", back_populates="conversation")


class Message(Base):
    __tablename__ = "messages"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    conversation_id = Column(UUID(as_uuid=False), ForeignKey("conversations.id"), nullable=False, index=True)
    role = Column(SAEnum(MessageRole), nullable=False)
    content = Column(Text, nullable=False)
    tool_calls = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)

    conversation = relationship("Conversation", back_populates="messages")


class Booking(Base):
    __tablename__ = "bookings"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    tenant_id = Column(UUID(as_uuid=False), ForeignKey("tenants.id"), nullable=False, index=True)
    conversation_id = Column(UUID(as_uuid=False), ForeignKey("conversations.id"), nullable=True)
    datetime_value = Column(DateTime(timezone=True), nullable=False)
    contact = Column(JSON, default=dict)  # {"name": ..., "phone": ...}


class Lead(Base):
    __tablename__ = "leads"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    tenant_id = Column(UUID(as_uuid=False), ForeignKey("tenants.id"), nullable=False, index=True)
    conversation_id = Column(UUID(as_uuid=False), ForeignKey("conversations.id"), nullable=True)
    name = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    intent = Column(Text, nullable=True)


class User(Base):
    __tablename__ = "users"
 
    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    email = Column(String, unique=True, nullable=False, index=True)
    hashed_password = Column(String, nullable=False)
    tenant_id = Column(UUID(as_uuid=False), ForeignKey("tenants.id"), nullable=False, unique=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)
 
    tenant = relationship("Tenant", back_populates="owner")
 
 

     
