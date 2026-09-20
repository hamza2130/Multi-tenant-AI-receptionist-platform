"""
config.py

Central settings, loaded from .env. Same pattern as the voice
receptionist project's config.py — one place every other file
imports credentials from.
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str
    QDRANT_URL: str = "http://localhost:6333"

    LLM_PROVIDER: str = "groq"
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "openai/gpt-oss-120b"

    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"
    JWT_SECRET: str = "change-this-to-a-real-random-secret-in-your-env-file"
    ADMIN_API_KEY: str = ""  # turns on POST /admin/tenants (sent as X-Admin-Key); blank keeps it off

    # Voice pipeline (Week 2) — same services/keys as the voice receptionist project
    DEEPGRAM_API_KEY: str = ""
    ELEVENLABS_API_KEY: str = ""
    ELEVENLABS_VOICE_ID: str = ""
    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    PUBLIC_BASE_URL: str = ""  # e.g. your ngrok URL, no trailing slash
    TWILIO_API_KEY_SID: str = ""
    TWILIO_API_KEY_SECRET: str = ""
    TWILIO_TWIML_APP_SID: str = ""

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()
