"""
test_settings_ai.py -- Task 7 validation
Tests for app/config/settings/ai.py and app/config/settings/provider.py
"""
from __future__ import annotations

import os
import pytest

from app.config.settings.provider import ProviderSettings
from app.config.settings.ai import (
    LLMBackend,
    AgentMode,
    LLMProfile,
    InferenceConfig,
    VoiceConfig,
    EmbeddingConfig,
    AISafetyConfig,
    AISettings,
    build_ai_settings,
)
from app.config.settings.broker import ProviderSettings as BrokerProviderSettings


# ── provider.py extraction ────────────────────────────────────

class TestProviderExtraction:
    """ProviderSettings now lives in provider.py; broker.py re-exports it."""

    def test_provider_module_importable(self):
        from app.config.settings.provider import ProviderSettings as PS
        assert PS is not None

    def test_broker_still_exports_provider_settings(self):
        """Backwards compatibility: broker.py must still export ProviderSettings."""
        assert BrokerProviderSettings is ProviderSettings

    def test_provider_defaults(self):
        p = ProviderSettings()
        assert p.enabled           is True
        assert p.priority          == 50
        assert p.timeout_s         == 30.0
        assert p.retry_policy_name == "default"
        assert p.credentials_key   == ""

    def test_provider_immutable(self):
        p = ProviderSettings()
        with pytest.raises(TypeError):
            p.enabled = False


# ── LLMProfile ────────────────────────────────────────────────

class TestLLMProfile:

    def _profile(self, **kwargs) -> LLMProfile:
        return LLMProfile(name="gemini", backend=LLMBackend.GEMINI,
                          model="gemini-2.0-flash", **kwargs)

    def test_name_required(self):
        with pytest.raises(Exception):
            LLMProfile(name="")

    def test_name_whitespace_stripped(self):
        p = LLMProfile(name="  gemini  ")
        assert p.name == "gemini"

    def test_priority_must_be_positive(self):
        with pytest.raises(Exception):
            LLMProfile(name="x", priority=0)

    def test_defaults(self):
        p = self._profile()
        assert p.enabled          is True
        assert p.priority         == 50
        assert p.timeout_s        == 30.0
        assert p.base_url         == ""
        assert p.plugin_class     == ""

    def test_immutable(self):
        p = self._profile()
        with pytest.raises(TypeError):
            p.model = "other-model"

    def test_to_safe_dict_redacts_credentials(self):
        p = self._profile(credentials_key="GEMINI_SECRET")
        d = p.to_safe_dict()
        assert d["credentials_key"] == "[REDACTED]"
        assert "GEMINI_SECRET" not in str(d)

    def test_to_safe_dict_empty_credentials_not_redacted(self):
        p = self._profile(credentials_key="")
        d = p.to_safe_dict()
        assert d["credentials_key"] == ""

    def test_backend_enum_values(self):
        for backend in LLMBackend:
            p = LLMProfile(name="x", backend=backend)
            assert p.backend == backend.value

    def test_extends_provider_settings(self):
        assert issubclass(LLMProfile, ProviderSettings)


# ── InferenceConfig ───────────────────────────────────────────

class TestInferenceConfig:

    def test_defaults(self):
        c = InferenceConfig()
        assert c.temperature       == 0.7
        assert c.max_tokens        == 1024
        assert c.context_window    == 8192
        assert c.top_p             == 0.95
        assert c.stream_by_default is True

    def test_temperature_lower_bound(self):
        c = InferenceConfig(temperature=0.0)
        assert c.temperature == 0.0

    def test_temperature_upper_bound(self):
        c = InferenceConfig(temperature=2.0)
        assert c.temperature == 2.0

    def test_temperature_out_of_range_low(self):
        with pytest.raises(Exception):
            InferenceConfig(temperature=-0.1)

    def test_temperature_out_of_range_high(self):
        with pytest.raises(Exception):
            InferenceConfig(temperature=2.1)

    def test_top_p_must_be_positive(self):
        with pytest.raises(Exception):
            InferenceConfig(top_p=0.0)

    def test_top_p_upper_bound(self):
        c = InferenceConfig(top_p=1.0)
        assert c.top_p == 1.0

    def test_max_tokens_must_be_positive(self):
        with pytest.raises(Exception):
            InferenceConfig(max_tokens=0)

    def test_context_window_must_be_positive(self):
        with pytest.raises(Exception):
            InferenceConfig(context_window=0)

    def test_immutable(self):
        c = InferenceConfig()
        with pytest.raises(TypeError):
            c.temperature = 0.5

    def test_to_dict(self):
        c = InferenceConfig()
        d = c.to_dict()
        assert d["temperature"] == 0.7
        assert d["max_tokens"]  == 1024


# ── VoiceConfig ───────────────────────────────────────────────

class TestVoiceConfig:

    def test_disabled_by_default(self):
        v = VoiceConfig()
        assert v.enabled is False

    def test_defaults(self):
        v = VoiceConfig()
        assert v.tts_model         == "default"
        assert v.stt_model         == "default"
        assert v.wake_word         == "jarvis"
        assert v.voice_speed       == 1.0
        assert v.language          == "en-IN"

    def test_voice_speed_must_be_positive(self):
        with pytest.raises(Exception):
            VoiceConfig(voice_speed=0.0)

    def test_voice_pitch_must_be_positive(self):
        with pytest.raises(Exception):
            VoiceConfig(voice_pitch=-1.0)

    def test_immutable(self):
        v = VoiceConfig()
        with pytest.raises(TypeError):
            v.enabled = True

    def test_to_dict(self):
        v = VoiceConfig(enabled=True, wake_word="hey jarvis")
        d = v.to_dict()
        assert d["enabled"]   is True
        assert d["wake_word"] == "hey jarvis"


# ── EmbeddingConfig ───────────────────────────────────────────

class TestEmbeddingConfig:

    def test_disabled_by_default(self):
        e = EmbeddingConfig()
        assert e.enabled is False

    def test_defaults(self):
        e = EmbeddingConfig()
        assert e.model      == "text-embedding-3-small"
        assert e.dimensions == 1536
        assert e.batch_size == 100

    def test_dimensions_must_be_positive(self):
        with pytest.raises(Exception):
            EmbeddingConfig(dimensions=0)

    def test_batch_size_must_be_positive(self):
        with pytest.raises(Exception):
            EmbeddingConfig(batch_size=0)

    def test_immutable(self):
        e = EmbeddingConfig()
        with pytest.raises(TypeError):
            e.enabled = True

    def test_to_safe_dict_redacts_credentials(self):
        e = EmbeddingConfig(credentials_key="OPENAI_KEY")
        d = e.to_safe_dict()
        assert d["credentials_key"] == "[REDACTED]"

    def test_to_safe_dict_empty_credentials(self):
        e = EmbeddingConfig(credentials_key="")
        d = e.to_safe_dict()
        assert d["credentials_key"] == ""


# ── AISafetyConfig ────────────────────────────────────────────

class TestAISafetyConfig:

    def test_defaults(self):
        s = AISafetyConfig()
        assert s.content_filter_enabled is True
        assert s.hallucination_guard    is False
        assert s.max_retries_on_refusal == 2
        assert s.confidence_threshold   == 0.6
        assert s.log_all_prompts        is False

    def test_confidence_threshold_lower_bound(self):
        s = AISafetyConfig(confidence_threshold=0.0)
        assert s.confidence_threshold == 0.0

    def test_confidence_threshold_upper_bound(self):
        s = AISafetyConfig(confidence_threshold=1.0)
        assert s.confidence_threshold == 1.0

    def test_confidence_threshold_out_of_range(self):
        with pytest.raises(Exception):
            AISafetyConfig(confidence_threshold=1.1)

    def test_retries_non_negative(self):
        s = AISafetyConfig(max_retries_on_refusal=0)
        assert s.max_retries_on_refusal == 0

    def test_retries_negative_rejected(self):
        with pytest.raises(Exception):
            AISafetyConfig(max_retries_on_refusal=-1)

    def test_immutable(self):
        s = AISafetyConfig()
        with pytest.raises(TypeError):
            s.hallucination_guard = True

    def test_to_dict(self):
        s = AISafetyConfig()
        d = s.to_dict()
        assert d["content_filter_enabled"] is True


# ── AISettings ────────────────────────────────────────────────

class TestAISettings:

    def _settings(self, **kwargs) -> AISettings:
        gemini = LLMProfile(name="gemini", backend=LLMBackend.GEMINI,
                            model="gemini-2.0-flash")
        groq   = LLMProfile(name="groq",   backend=LLMBackend.GROQ,
                            model="llama-3.3-70b-versatile", enabled=False)
        return AISettings(
            profiles={"gemini": gemini, "groq": groq},
            active_llm="gemini",
            **kwargs,
        )

    def test_get_active_returns_correct_profile(self):
        s = self._settings()
        assert s.get_active().name == "gemini"

    def test_get_active_returns_none_for_unknown(self):
        s = AISettings(active_llm="nonexistent")
        assert s.get_active() is None

    def test_get_profile_by_name(self):
        s = self._settings()
        assert s.get_profile("groq").name == "groq"
        assert s.get_profile("missing")   is None

    def test_enabled_profiles_filters_disabled(self):
        s = self._settings()
        names = [p.name for p in s.enabled_profiles()]
        assert "gemini" in names
        assert "groq"   not in names

    def test_has_profile_true(self):
        s = self._settings()
        assert s.has_profile("gemini") is True

    def test_has_profile_false(self):
        s = self._settings()
        assert s.has_profile("missing") is False

    def test_immutable(self):
        s = self._settings()
        with pytest.raises(TypeError):
            s.active_llm = "groq"

    def test_to_dict_redacts_all_credentials(self):
        gemini = LLMProfile(name="gemini", backend=LLMBackend.GEMINI,
                            model="gemini-2.0-flash", credentials_key="GEMINI_KEY")
        s = AISettings(profiles={"gemini": gemini})
        d = s.to_dict()
        assert d["profiles"]["gemini"]["credentials_key"] == "[REDACTED]"
        assert "GEMINI_KEY" not in str(d)

    def test_to_dict_contains_all_sections(self):
        s = self._settings()
        d = s.to_dict()
        for key in ("active_llm", "active_agent", "inference",
                    "voice", "embedding", "safety", "profiles"):
            assert key in d

    def test_default_agent_mode(self):
        s = AISettings()
        assert s.active_agent == AgentMode.COORDINATOR.value

    def test_agent_mode_enum_values(self):
        for mode in AgentMode:
            s = AISettings(active_agent=mode)
            assert s.active_agent == mode.value


# ── Factory ───────────────────────────────────────────────────

class TestBuildAISettings:

    def setup_method(self):
        for key in ("ACTIVE_LLM", "ACTIVE_AGENT", "LLM_TEMPERATURE",
                    "LLM_MAX_TOKENS", "LLM_STREAM", "VOICE_ENABLED",
                    "EMBEDDING_ENABLED", "OLLAMA_ENABLED",
                    "OLLAMA_MODEL", "OLLAMA_BASE_URL"):
            os.environ.pop(key, None)

    def test_factory_returns_ai_settings(self):
        s = build_ai_settings()
        assert isinstance(s, AISettings)

    def test_factory_default_active_llm(self):
        s = build_ai_settings()
        assert s.active_llm == "gemini"

    def test_factory_active_llm_from_env(self):
        os.environ["ACTIVE_LLM"] = "groq"
        s = build_ai_settings()
        assert s.active_llm == "groq"

    def test_factory_active_agent_from_env(self):
        os.environ["ACTIVE_AGENT"] = "scientific"
        s = build_ai_settings()
        assert s.active_agent == AgentMode.SCIENTIFIC.value

    def test_factory_invalid_agent_defaults_to_coordinator(self):
        os.environ["ACTIVE_AGENT"] = "banana"
        s = build_ai_settings()
        assert s.active_agent == AgentMode.COORDINATOR.value

    def test_factory_temperature_from_env(self):
        os.environ["LLM_TEMPERATURE"] = "0.3"
        s = build_ai_settings()
        assert s.inference.temperature == 0.3

    def test_factory_max_tokens_from_env(self):
        os.environ["LLM_MAX_TOKENS"] = "2048"
        s = build_ai_settings()
        assert s.inference.max_tokens == 2048

    def test_factory_stream_false_from_env(self):
        os.environ["LLM_STREAM"] = "false"
        s = build_ai_settings()
        assert s.inference.stream_by_default is False

    def test_factory_voice_enabled_from_env(self):
        os.environ["VOICE_ENABLED"] = "true"
        s = build_ai_settings()
        assert s.voice.enabled is True

    def test_factory_voice_disabled_by_default(self):
        s = build_ai_settings()
        assert s.voice.enabled is False

    def test_factory_embedding_enabled_from_env(self):
        os.environ["EMBEDDING_ENABLED"] = "true"
        s = build_ai_settings()
        assert s.embedding.enabled is True

    def test_factory_ollama_disabled_by_default(self):
        s = build_ai_settings()
        assert s.profiles["ollama"].enabled is False

    def test_factory_ollama_enabled_from_env(self):
        os.environ["OLLAMA_ENABLED"] = "true"
        s = build_ai_settings()
        assert s.profiles["ollama"].enabled is True

    def test_factory_ollama_model_from_env(self):
        os.environ["OLLAMA_MODEL"] = "mistral"
        s = build_ai_settings()
        assert s.profiles["ollama"].model == "mistral"

    def test_factory_ollama_base_url_from_env(self):
        os.environ["OLLAMA_BASE_URL"] = "http://192.168.1.10:11434"
        s = build_ai_settings()
        assert s.profiles["ollama"].base_url == "http://192.168.1.10:11434"

    def test_factory_gemini_profile_always_present(self):
        s = build_ai_settings()
        assert "gemini" in s.profiles

    def test_factory_groq_profile_always_present(self):
        s = build_ai_settings()
        assert "groq" in s.profiles

    def test_factory_ollama_profile_always_present(self):
        s = build_ai_settings()
        assert "ollama" in s.profiles

    def test_factory_overrides_take_precedence(self):
        s = build_ai_settings(overrides={"active_llm": "groq"})
        assert s.active_llm == "groq"

    def test_gemini_profile_credentials_key(self):
        s = build_ai_settings()
        assert s.profiles["gemini"].credentials_key == "GEMINI"

    def test_groq_profile_base_url(self):
        s = build_ai_settings()
        assert "groq.com" in s.profiles["groq"].base_url
