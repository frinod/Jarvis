from __future__ import annotations
import os
from pydantic import BaseSettings
from typing import Optional

# Resolve .env path relative to this file — works regardless of where uvicorn is launched from
_ENV_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), ".env")

# Placeholder fragments that indicate a key has NOT been replaced by the user.
# A key matching any of these is treated as NOT_CONFIGURED, not ACTIVE.
_PLACEHOLDER_FRAGMENTS = (
    "PASTE", "YOUR_KEY", "YOUR_KEY_HERE", "CHANGE_ME",
    "INSERT", "REPLACE", "EXAMPLE", "PLACEHOLDER",
)


def _is_valid_key(key: Optional[str], prefix: str = "") -> bool:
    """
    Return True only when key is a non-empty string that:
      - starts with the expected prefix (if given)
      - does not contain any placeholder fragment
    This prevents placeholder values from silently activating providers.
    """
    if not key:
        return False
    k = key.strip()
    if not k:
        return False
    if prefix and not k.startswith(prefix):
        return False
    upper = k.upper()
    if any(frag in upper for frag in _PLACEHOLDER_FRAGMENTS):
        return False
    return True


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
    gemini_model: str = "gemini-2.5-flash-preview-05-20"
    groq_model: str = "qwen/qwen3.8-27b"
    deepseek_model: str = "deepseek-chat"
    openai_model: str = "gpt-4o-mini"
    openrouter_model: str = "qwen/qwen3.8-27b:free"
    openrouter_base_url: str = "https://openrouter.ai/api/v1"

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
    sprag_api_key: Optional[str] = None
    sprag_base_url: str = "https://api.sprag.ai/v1"

    class Config:
        env_file = _ENV_FILE
        env_file_encoding = "utf-8"


settings = Settings()
print(f"[JARVIS] Config loaded from: {_ENV_FILE}")
print(f"[JARVIS] Groq key:        {'ACTIVE' if _is_valid_key(settings.groq_api_key, 'gsk_') else 'NOT_CONFIGURED'}")
print(f"[JARVIS] Gemini key:      {'ACTIVE' if _is_valid_key(settings.gemini_api_key, 'AIza') else 'NOT_CONFIGURED (placeholder or missing)'}")
print(f"[JARVIS] OpenRouter key:  {'ACTIVE' if _is_valid_key(settings.openrouter_api_key, 'sk-or-') else 'NOT_CONFIGURED'}")
print(f"[JARVIS] Sprag voice key: {'ACTIVE' if _is_valid_key(settings.sprag_api_key) else 'NOT_CONFIGURED'}")
