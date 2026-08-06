"""
test_settings_cache.py -- Task 9 validation
Tests for app/config/settings/cache.py
"""
from __future__ import annotations

import os
import pytest

from app.config.settings.cache import (
    CacheBackend,
    EvictionPolicy,
    CacheDomainProfile,
    RedisConfig,
    CacheSettings,
    build_cache_settings,
)


# ── CacheDomainProfile ────────────────────────────────────────

class TestCacheDomainProfile:

    def test_defaults(self):
        p = CacheDomainProfile()
        assert p.ttl_s    == 300
        assert p.max_size == 1000
        assert p.enabled  is True

    def test_ttl_zero_allowed(self):
        p = CacheDomainProfile(ttl_s=0)
        assert p.ttl_s == 0

    def test_ttl_negative_rejected(self):
        with pytest.raises(Exception):
            CacheDomainProfile(ttl_s=-1)

    def test_max_size_zero_allowed(self):
        p = CacheDomainProfile(max_size=0)
        assert p.max_size == 0

    def test_max_size_negative_rejected(self):
        with pytest.raises(Exception):
            CacheDomainProfile(max_size=-1)

    def test_disabled_profile(self):
        p = CacheDomainProfile(enabled=False)
        assert p.enabled is False

    def test_immutable(self):
        p = CacheDomainProfile()
        with pytest.raises(TypeError):
            p.ttl_s = 60

    def test_to_dict(self):
        p = CacheDomainProfile(ttl_s=60)
        d = p.to_dict()
        assert d["ttl_s"] == 60


# ── RedisConfig ───────────────────────────────────────────────

class TestRedisConfig:

    def test_defaults(self):
        r = RedisConfig()
        assert r.host            == "localhost"
        assert r.port            == 6379
        assert r.db              == 0
        assert r.ssl             is False
        assert r.max_connections == 10

    def test_port_out_of_range_low(self):
        with pytest.raises(Exception):
            RedisConfig(port=0)

    def test_port_out_of_range_high(self):
        with pytest.raises(Exception):
            RedisConfig(port=65536)

    def test_port_boundary_values(self):
        r1 = RedisConfig(port=1)
        r2 = RedisConfig(port=65535)
        assert r1.port == 1
        assert r2.port == 65535

    def test_db_negative_rejected(self):
        with pytest.raises(Exception):
            RedisConfig(db=-1)

    def test_max_connections_must_be_positive(self):
        with pytest.raises(Exception):
            RedisConfig(max_connections=0)

    def test_immutable(self):
        r = RedisConfig()
        with pytest.raises(TypeError):
            r.host = "redis-server"

    def test_to_safe_dict_redacts_password(self):
        r = RedisConfig(password="secret123")
        d = r.to_safe_dict()
        assert d["password"] == "[REDACTED]"
        assert "secret123" not in str(d)

    def test_to_safe_dict_empty_password(self):
        r = RedisConfig(password="")
        d = r.to_safe_dict()
        assert d["password"] == ""

    def test_to_safe_dict_redacts_credentials_key(self):
        r = RedisConfig(credentials_key="REDIS_PASS")
        d = r.to_safe_dict()
        assert d["credentials_key"] == "[REDACTED]"


# ── CacheSettings ─────────────────────────────────────────────

class TestCacheSettings:

    def test_defaults(self):
        c = CacheSettings()
        assert c.backend         == CacheBackend.MEMORY.value
        assert c.eviction_policy == EvictionPolicy.LRU.value
        assert c.global_max_size == 10000
        assert c.warm_on_startup is False

    def test_global_max_size_zero_allowed(self):
        c = CacheSettings(global_max_size=0)
        assert c.global_max_size == 0

    def test_global_max_size_negative_rejected(self):
        with pytest.raises(Exception):
            CacheSettings(global_max_size=-1)

    def test_immutable(self):
        c = CacheSettings()
        with pytest.raises(TypeError):
            c.backend = "redis"

    def test_get_domain_existing(self):
        profile = CacheDomainProfile(ttl_s=60)
        c = CacheSettings(domains={"quotes": profile})
        assert c.get_domain("quotes").ttl_s == 60

    def test_get_domain_missing_returns_none(self):
        c = CacheSettings()
        assert c.get_domain("nonexistent") is None

    def test_ttl_for_existing_domain(self):
        profile = CacheDomainProfile(ttl_s=120)
        c = CacheSettings(domains={"quotes": profile})
        assert c.ttl_for("quotes") == 120

    def test_ttl_for_missing_domain_returns_default(self):
        c = CacheSettings()
        assert c.ttl_for("missing", default=999) == 999

    def test_ttl_for_disabled_domain_returns_default(self):
        profile = CacheDomainProfile(ttl_s=120, enabled=False)
        c = CacheSettings(domains={"quotes": profile})
        assert c.ttl_for("quotes", default=0) == 0

    def test_is_enabled_for_existing_enabled_domain(self):
        profile = CacheDomainProfile(enabled=True)
        c = CacheSettings(domains={"quotes": profile})
        assert c.is_enabled_for("quotes") is True

    def test_is_enabled_for_disabled_domain(self):
        profile = CacheDomainProfile(enabled=False)
        c = CacheSettings(domains={"quotes": profile})
        assert c.is_enabled_for("quotes") is False

    def test_is_enabled_for_none_backend_always_false(self):
        profile = CacheDomainProfile(enabled=True)
        c = CacheSettings(backend=CacheBackend.NONE, domains={"quotes": profile})
        assert c.is_enabled_for("quotes") is False

    def test_is_enabled_for_unknown_domain_returns_true(self):
        c = CacheSettings(backend=CacheBackend.MEMORY)
        assert c.is_enabled_for("unknown_domain") is True

    def test_to_dict_structure(self):
        c = CacheSettings()
        d = c.to_dict()
        for key in ("backend", "eviction_policy", "global_max_size",
                    "warm_on_startup", "redis", "domains"):
            assert key in d

    def test_to_dict_redis_redacted(self):
        r = RedisConfig(password="secret")
        c = CacheSettings(redis=r)
        d = c.to_dict()
        assert d["redis"]["password"] == "[REDACTED]"

    def test_all_backends_accepted(self):
        for backend in CacheBackend:
            c = CacheSettings(backend=backend)
            assert c.backend == backend.value

    def test_all_eviction_policies_accepted(self):
        for policy in EvictionPolicy:
            c = CacheSettings(eviction_policy=policy)
            assert c.eviction_policy == policy.value


# ── Factory ───────────────────────────────────────────────────

class TestBuildCacheSettings:

    def setup_method(self):
        for key in ("CACHE_BACKEND", "CACHE_EVICTION_POLICY",
                    "CACHE_GLOBAL_MAX_SIZE", "CACHE_WARM_ON_STARTUP",
                    "REDIS_HOST", "REDIS_PORT", "REDIS_DB", "REDIS_SSL",
                    "CACHE_QUOTES_TTL", "CACHE_CANDLES_TTL", "CACHE_AI_TTL"):
            os.environ.pop(key, None)

    def test_factory_returns_cache_settings(self):
        c = build_cache_settings()
        assert isinstance(c, CacheSettings)

    def test_factory_default_backend(self):
        c = build_cache_settings()
        assert c.backend == CacheBackend.MEMORY.value

    def test_factory_backend_from_env(self):
        os.environ["CACHE_BACKEND"] = "redis"
        c = build_cache_settings()
        assert c.backend == CacheBackend.REDIS.value

    def test_factory_invalid_backend_defaults_to_memory(self):
        os.environ["CACHE_BACKEND"] = "banana"
        c = build_cache_settings()
        assert c.backend == CacheBackend.MEMORY.value

    def test_factory_eviction_policy_from_env(self):
        os.environ["CACHE_EVICTION_POLICY"] = "lfu"
        c = build_cache_settings()
        assert c.eviction_policy == EvictionPolicy.LFU.value

    def test_factory_invalid_eviction_defaults_to_lru(self):
        os.environ["CACHE_EVICTION_POLICY"] = "banana"
        c = build_cache_settings()
        assert c.eviction_policy == EvictionPolicy.LRU.value

    def test_factory_global_max_size_from_env(self):
        os.environ["CACHE_GLOBAL_MAX_SIZE"] = "5000"
        c = build_cache_settings()
        assert c.global_max_size == 5000

    def test_factory_warm_on_startup_from_env(self):
        os.environ["CACHE_WARM_ON_STARTUP"] = "true"
        c = build_cache_settings()
        assert c.warm_on_startup is True

    def test_factory_redis_host_from_env(self):
        os.environ["REDIS_HOST"] = "redis.internal"
        c = build_cache_settings()
        assert c.redis.host == "redis.internal"

    def test_factory_redis_port_from_env(self):
        os.environ["REDIS_PORT"] = "6380"
        c = build_cache_settings()
        assert c.redis.port == 6380

    def test_factory_redis_ssl_from_env(self):
        os.environ["REDIS_SSL"] = "true"
        c = build_cache_settings()
        assert c.redis.ssl is True

    def test_factory_quotes_ttl_from_env(self):
        os.environ["CACHE_QUOTES_TTL"] = "5"
        c = build_cache_settings()
        assert c.domains["market_quotes"].ttl_s == 5

    def test_factory_candles_ttl_from_env(self):
        os.environ["CACHE_CANDLES_TTL"] = "60"
        c = build_cache_settings()
        assert c.domains["market_candles"].ttl_s == 60

    def test_factory_ai_ttl_from_env(self):
        os.environ["CACHE_AI_TTL"] = "7200"
        c = build_cache_settings()
        assert c.domains["ai_responses"].ttl_s == 7200

    def test_factory_default_domains_present(self):
        c = build_cache_settings()
        for domain in ("market_quotes", "market_candles", "ai_responses",
                       "broker_data", "instruments", "user_sessions"):
            assert domain in c.domains

    def test_factory_overrides_take_precedence(self):
        c = build_cache_settings(overrides={"warm_on_startup": True})
        assert c.warm_on_startup is True
