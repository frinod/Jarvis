from __future__ import annotations
import os
from pydantic import BaseSettings
from typing import Optional

# Resolve .env path relative to this file — works regardless of where uvicorn is launched from
_ENV_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), ".env")


class Settings(BaseSettings):
    app_name: str = "Frino OS"
    version: str = "1.0.0"
    debug: bool = False

    # Database
    database_url: str = "sqlite:///jarvis.db"
    redis_url: str = "redis://localhost:6379/0"
    qdrant_url: str = "http://localhost:6333"

    # AI Providers (set any ONE key to enable that provider)
    gemini_api_key: Optional[str] = None
    groq_api_key: Optional[str] = None
    deepseek_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None
    openrouter_api_key: Optional[str] = None

    # Model names (defaults work great, change if needed)
    gemini_model: str = "gemini-2.0-flash"
    groq_model: str = "llama-3.3-70b-versatile"
    deepseek_model: str = "deepseek-chat"
    openai_model: str = "gpt-4o-mini"

    # Ollama (local)
    local_model_path: Optional[str] = None
    ollama_model: str = "llama3.1"

    # Embedding
    embedding_model: str = "all-MiniLM-L6-v2"

    # Security
    secret_key: str = "change-me-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440

    # Voice
    wake_word: str = "frino"
    tts_engine: str = "pyttsx3"

    class Config:
        env_file = _ENV_FILE
        env_file_encoding = "utf-8"


settings = Settings()
print(f"[JARVIS] Config loaded from: {_ENV_FILE}")
print(f"[JARVIS] Groq key present: {'YES' if (settings.groq_api_key or '').strip().startswith('gsk_') else 'NO'}")
print(f"[JARVIS] Gemini key present: {'YES' if (settings.gemini_api_key or '').strip().startswith('AIza') else 'NO'}")
