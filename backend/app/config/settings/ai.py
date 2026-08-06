"""
config/settings/ai.py
=====================
AI engine configuration domain for JARVIS OS.

Covers every AI subsystem JARVIS uses:
  LLM providers    -- Gemini, Groq, DeepSeek, OpenAI, Ollama
  Active agent     -- which reasoning agent handles requests
  Inference params -- temperature, context window, token limits
  Voice settings   -- TTS/STT model selection and parameters
  Embedding config -- model name and dimensions for RAG
  Safety controls  -- content filtering, hallucination guards

Design principles
-----------------
  Provider-agnostic -- active_llm selects by name, not hardcoded class
  Safe serialisation -- API keys always redacted in to_dict()
  Multi-provider ready -- profiles dict supports N providers simultaneously
  Voice-optional -- voice settings default to disabled
  Embedding-ready -- embedding config exists even before RAG is wired
  Immutable after load -- allow_mutation = False

Internal pattern (standard for all settings modules)
  1. Domain models
  2. Validation
  3. Factory function
  4. Safe serialisation
  5. Convenience methods
  6. Future extension hooks
"""
from __future__ import annotations

import os
from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, validator

from app.config.settings.provider import ProviderSettings


# ── LLM provider enums ────────────────────────────────────────

class LLMBackend(str, Enum):
    GEMINI    = "gemini"
    GROQ      = "groq"
    DEEPSEEK  = "deepseek"
    OPENAI    = "openai"
    OLLAMA    = "ollama"
    OPENROUTER = "openrouter"
    CUSTOM    = "custom"


class AgentMode(str, Enum):
    COORDINATOR  = "coordinator"   # multi-agent orchestration
    SCIENTIFIC   = "scientific"    # quantitative / research mode
    CONVERSATIONAL = "conversational"  # chat / Q&A mode
    AUTONOMOUS   = "autonomous"    # self-directed task execution


# ── LLM provider profile ──────────────────────────────────────

class LLMProfile(ProviderSettings):
    """
    Configuration for one LLM provider instance.

    plugin_class: dotted import path to the LLMProvider implementation.
    base_url:     API endpoint -- required for Ollama and OpenRouter,
                  optional override for OpenAI-compatible providers.
    model:        model identifier string (e.g. "gemini-2.0-flash").
    credentials_key: env var prefix for API key lookup (e.g. "GEMINI"
                     resolves to GEMINI_API_KEY).
    """
    name:           str        = ""
    display_name:   str        = ""
    backend:        LLMBackend = LLMBackend.GEMINI
    model:          str        = ""
    base_url:       str        = ""
    plugin_class:   str        = ""

    class Config:
        allow_mutation  = False
        extra           = "ignore"
        use_enum_values = True

    @validator("name")
    def name_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("LLMProfile.name must not be empty")
        return v.strip()

    @validator("priority")
    def priority_positive(cls, v: int) -> int:
        if v < 1:
            raise ValueError("priority must be >= 1")
        return v

    def to_safe_dict(self) -> dict:
        """Serialise without exposing credentials_key value."""
        d = self.dict()
        d["credentials_key"] = "[REDACTED]" if self.credentials_key else ""
        return d


# ── Inference parameters ──────────────────────────────────────

class InferenceConfig(BaseModel):
    """
    Inference-time parameters shared across all LLM calls.
    Individual call sites may override these per-request.
    """
    temperature:        float = 0.7
    max_tokens:         int   = 1024
    context_window:     int   = 8192
    top_p:              float = 0.95
    frequency_penalty:  float = 0.0
    presence_penalty:   float = 0.0
    request_timeout_s:  float = 60.0
    stream_by_default:  bool  = True

    class Config:
        allow_mutation = False
        extra          = "ignore"

    @validator("temperature")
    def temperature_in_range(cls, v: float) -> float:
        if not (0.0 <= v <= 2.0):
            raise ValueError("temperature must be 0.0-2.0")
        return v

    @validator("top_p")
    def top_p_in_range(cls, v: float) -> float:
        if not (0.0 < v <= 1.0):
            raise ValueError("top_p must be (0.0, 1.0]")
        return v

    @validator("max_tokens", "context_window")
    def tokens_positive(cls, v: int) -> int:
        if v < 1:
            raise ValueError("token limits must be >= 1")
        return v

    def to_dict(self) -> dict:
        return self.dict()


# ── Voice settings ────────────────────────────────────────────

class VoiceConfig(BaseModel):
    """
    Voice interface configuration. Disabled by default until
    app/voice/ is wired to the settings layer.
    tts_model / stt_model: model identifiers for TTS and STT engines.
    wake_word: trigger phrase for always-on voice mode.
    """
    enabled:          bool  = False
    tts_model:        str   = "default"
    stt_model:        str   = "default"
    wake_word:        str   = "jarvis"
    voice_speed:      float = 1.0
    voice_pitch:      float = 1.0
    language:         str   = "en-IN"
    silence_timeout_s: float = 2.0

    class Config:
        allow_mutation = False
        extra          = "ignore"

    @validator("voice_speed", "voice_pitch")
    def speed_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("voice_speed and voice_pitch must be positive")
        return v

    def to_dict(self) -> dict:
        return self.dict()


# ── Embedding config ──────────────────────────────────────────

class EmbeddingConfig(BaseModel):
    """
    Embedding model configuration for RAG and semantic search.
    Not yet wired to the retrieval layer -- config exists for
    forward compatibility when Phase 6 RAG is implemented.
    """
    enabled:          bool  = False
    model:            str   = "text-embedding-3-small"
    dimensions:       int   = 1536
    batch_size:       int   = 100
    credentials_key:  str   = ""    # env var prefix for embedding API key

    class Config:
        allow_mutation = False
        extra          = "ignore"

    @validator("dimensions", "batch_size")
    def positive_int(cls, v: int) -> int:
        if v < 1:
            raise ValueError("dimensions and batch_size must be >= 1")
        return v

    def to_safe_dict(self) -> dict:
        d = self.dict()
        d["credentials_key"] = "[REDACTED]" if self.credentials_key else ""
        return d


# ── Safety controls ───────────────────────────────────────────

class AISafetyConfig(BaseModel):
    """
    AI safety and guardrail configuration.
    These are configuration values only -- enforcement is in the AI layer.
    max_retries_on_refusal: how many times to retry if LLM refuses a request.
    hallucination_guard:    enable post-processing checks on LLM output.
    """
    content_filter_enabled:    bool  = True
    hallucination_guard:       bool  = False   # Phase 6 feature
    max_retries_on_refusal:    int   = 2
    confidence_threshold:      float = 0.6
    log_all_prompts:           bool  = False   # PII risk -- off by default
    max_prompt_length:         int   = 4000

    class Config:
        allow_mutation = False
        extra          = "ignore"

    @validator("confidence_threshold")
    def threshold_in_range(cls, v: float) -> float:
        if not (0.0 <= v <= 1.0):
            raise ValueError("confidence_threshold must be 0.0-1.0")
        return v

    @validator("max_retries_on_refusal")
    def retries_non_negative(cls, v: int) -> int:
        if v < 0:
            raise ValueError("max_retries_on_refusal must be >= 0")
        return v

    def to_dict(self) -> dict:
        return self.dict()


# ── Domain settings object ────────────────────────────────────

class AISettings(BaseModel):
    """
    Registry of all AI provider profiles plus active selections
    and global inference/voice/embedding/safety configuration.

    profiles:     named dict of LLMProfile instances
    active_llm:   name of the profile currently handling LLM calls
    active_agent: AgentMode controlling reasoning behaviour
    """
    profiles:      Dict[str, LLMProfile] = {}
    active_llm:    str                   = "gemini"
    active_agent:  AgentMode             = AgentMode.COORDINATOR
    inference:     InferenceConfig       = InferenceConfig()
    voice:         VoiceConfig           = VoiceConfig()
    embedding:     EmbeddingConfig       = EmbeddingConfig()
    safety:        AISafetyConfig        = AISafetyConfig()

    class Config:
        allow_mutation  = False
        extra           = "ignore"
        use_enum_values = True

    # ── Convenience queries ───────────────────────────────────

    def get_active(self) -> Optional[LLMProfile]:
        return self.profiles.get(self.active_llm)

    def get_profile(self, name: str) -> Optional[LLMProfile]:
        return self.profiles.get(name)

    def enabled_profiles(self) -> List[LLMProfile]:
        return [p for p in self.profiles.values() if p.enabled]

    def has_profile(self, name: str) -> bool:
        return name in self.profiles

    def to_dict(self) -> dict:
        """Safe serialisation -- all credentials_key values redacted."""
        return {
            "active_llm":   self.active_llm,
            "active_agent": self.active_agent,
            "inference":    self.inference.to_dict(),
            "voice":        self.voice.to_dict(),
            "embedding":    self.embedding.to_safe_dict(),
            "safety":       self.safety.to_dict(),
            "profiles":     {k: v.to_safe_dict() for k, v in self.profiles.items()},
        }


# ── Default profiles ──────────────────────────────────────────

_GEMINI_PROFILE = LLMProfile(
    name            = "gemini",
    display_name    = "Google Gemini",
    backend         = LLMBackend.GEMINI,
    model           = "gemini-2.0-flash",
    priority        = 10,
    credentials_key = "GEMINI",
    plugin_class    = "app.core.llm.GeminiProvider",
)

_GROQ_PROFILE = LLMProfile(
    name            = "groq",
    display_name    = "Groq",
    backend         = LLMBackend.GROQ,
    model           = "llama-3.3-70b-versatile",
    priority        = 20,
    credentials_key = "GROQ",
    base_url        = "https://api.groq.com/openai/v1",
    plugin_class    = "app.core.llm.OpenAICompatibleProvider",
)

_OLLAMA_PROFILE = LLMProfile(
    name            = "ollama",
    display_name    = "Ollama (local)",
    backend         = LLMBackend.OLLAMA,
    model           = "llama3.1",
    priority        = 90,
    enabled         = False,   # disabled until local Ollama is confirmed
    base_url        = "http://localhost:11434",
    plugin_class    = "app.core.llm.OllamaProvider",
)


# ── Factory ───────────────────────────────────────────────────

def build_ai_settings(overrides: Optional[dict] = None) -> AISettings:
    """
    Construct AISettings from environment variables + optional overrides.

    Environment variables:
      ACTIVE_LLM            -- profile name (default: "gemini")
      ACTIVE_AGENT          -- agent mode (default: "coordinator")
      LLM_TEMPERATURE       -- float 0.0-2.0 (default: 0.7)
      LLM_MAX_TOKENS        -- int (default: 1024)
      LLM_STREAM            -- true|false (default: "true")
      VOICE_ENABLED         -- true|false (default: "false")
      EMBEDDING_ENABLED     -- true|false (default: "false")
      OLLAMA_ENABLED        -- true|false (default: "false")
      OLLAMA_MODEL          -- model name (default: "llama3.1")
      OLLAMA_BASE_URL       -- URL (default: "http://localhost:11434")
    """
    active_llm = os.getenv("ACTIVE_LLM", "gemini").strip()

    agent_raw = os.getenv("ACTIVE_AGENT", "coordinator").strip().lower()
    try:
        active_agent = AgentMode(agent_raw)
    except ValueError:
        active_agent = AgentMode.COORDINATOR

    temperature = float(os.getenv("LLM_TEMPERATURE", "0.7"))
    max_tokens  = int(os.getenv("LLM_MAX_TOKENS", "1024"))
    stream      = os.getenv("LLM_STREAM", "true").strip().lower() == "true"

    inference = InferenceConfig(
        temperature=temperature,
        max_tokens=max_tokens,
        stream_by_default=stream,
    )

    voice_enabled = os.getenv("VOICE_ENABLED", "false").strip().lower() == "true"
    voice = VoiceConfig(enabled=voice_enabled)

    embedding_enabled = os.getenv("EMBEDDING_ENABLED", "false").strip().lower() == "true"
    embedding = EmbeddingConfig(enabled=embedding_enabled)

    # Ollama profile -- enabled and configured from env
    ollama_enabled  = os.getenv("OLLAMA_ENABLED", "false").strip().lower() == "true"
    ollama_model    = os.getenv("OLLAMA_MODEL",    "llama3.1").strip()
    ollama_base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").strip()
    ollama_profile  = LLMProfile(**{
        **_OLLAMA_PROFILE.dict(),
        "enabled":  ollama_enabled,
        "model":    ollama_model,
        "base_url": ollama_base_url,
    })

    profiles: Dict[str, LLMProfile] = {
        "gemini": _GEMINI_PROFILE,
        "groq":   _GROQ_PROFILE,
        "ollama": ollama_profile,
    }

    values: dict = {
        "profiles":     profiles,
        "active_llm":   active_llm,
        "active_agent": active_agent,
        "inference":    inference,
        "voice":        voice,
        "embedding":    embedding,
    }

    if overrides:
        values.update(overrides)

    return AISettings(**values)
