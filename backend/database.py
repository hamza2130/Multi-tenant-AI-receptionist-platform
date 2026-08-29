"""
database.py

SQLAlchemy engine + session setup, and a FastAPI dependency (get_db)
for handing each request its own database session.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from config import settings
from models import Base

engine = create_engine(settings.DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    """Creates all tables if they don't exist yet. Week 1 shortcut —
    a real deployment would use Alembic migrations instead."""
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
