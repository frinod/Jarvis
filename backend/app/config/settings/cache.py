"""
config/settings/cache.py
========================
Cache configuration domain for JARVIS OS.

Covers every caching layer:
  In-memory cache   -- TTL-based dict cache (current implementation)
  Redis cache       -- distributed cache (Phase 5.5+)
  Per-domain TTLs   -- market data, AI responses, broker data, user sessions
  Eviction policy   -- LRU, LFU, TTL-only
  Warming strategy  -- pre-populate on startup

Design principles
-----------------
  Domain-specific TTLs -- market data expires faster than AI responses
  Backend-agnostic -- swap memory <-> Redis without changing consumers
  Testing overrides -- 1s TTLs in test environment (from environment.py)
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
from typing import Dict, Optional

from pydantic import BaseModel, validator


# ── Enums ─────────────────────────────────────────────────────

class CacheBackend(str, Enum):
    MEMORY = "memory"    # in-process dict (default)
    REDIS  = "redis"     # distributed (Phase 5.5)
    NONE   = "none"      # caching disabled (testing)


class EvictionPolicy(str, Enum):
    LRU  = "lru"    # least recently used
    LFU  = "lfu"    # least frequently used
    TTL  = "ttl"    # expire by time only, no size limit


# ── Per-domain TTL profile ────────────────────────────────────

class CacheDomainProfile(BaseModel):
    """
    TTL and size configuration for one cache domain.
    ttl_s:      time-to-live in seconds (0 = never expire)
    max_size:   maximum number of entries (0 = unlimited)
    enabled:    False disables caching for this domain entirely
    """
    ttl_s:    int  = 300
    max_size: int  = 1000
    enabled:  bool = True

    class Config:
        allow_mutation = False
        extra          = "ignore"

    @validator("ttl_s", "max_size")
    def non_negative(cls, v: int) -> int:
        if v < 0:
            raise ValueError("ttl_s and max_size must be >= 0")
        return v

    def to_dict(self) -> dict:
        return self.dict()


# ── Redis connection config ───────────────────────────────────

class RedisConfig(BaseModel):
    """
    Redis connection parameters. Only used when backend = REDIS.
    credentials_key: env var prefix for Redis password lookup.
    """
    host:            str   = "localhost"
    port:            int   = 6379
    db:              int   = 0
    password:        str   = ""
    ssl:             bool  = False
    connect_timeout: float = 5.0
    socket_timeout:  float = 2.0
    max_connections: int   = 10
    credentials_key: str   = "REDIS"

    class Config:
        allow_mutation = False
        extra          = "ignore"

    @validator("port")
    def port_in_range(cls, v: int) -> int:
        if not (1 <= v <= 65535):
            raise ValueError("port must be 1-65535")
        return v

    @validator("db")
    def db_non_negative(cls, v: int) -> int:
        if v < 0:
            raise ValueError("db must be >= 0")
        return v

    @validator("max_connections")
    def connections_positive(cls, v: int) -> int:
        if v < 1:
            raise ValueError("max_connections must be >= 1")
        return v

    def to_safe_dict(self) -> dict:
        d = self.dict()
        d["password"] = "[REDACTED]" if self.password else ""
        d["credentials_key"] = "[REDACTED]" if self.credentials_key else ""
        return d


# ── Domain settings object ────────────────────────────────────

class CacheSettings(BaseModel):
    """
    Unified cache configuration.

    domains: named TTL profiles for each cache domain.
    Built-in domain names:
      market_quotes   -- live quote data (short TTL)
      market_candles  -- OHLCV candle data (medium TTL)
      ai_responses    -- LLM response cache (long TTL)
      broker_data     -- broker account/portfolio data
      instruments     -- instrument master data (very long TTL)
      user_sessions   -- user auth sessions
    """
    backend:          CacheBackend                  = CacheBackend.MEMORY
    eviction_policy:  EvictionPolicy                = EvictionPolicy.LRU
    global_max_size:  int                           = 10000
    domains:          Dict[str, CacheDomainProfile] = {}
    redis:            RedisConfig                   = RedisConfig()
    warm_on_startup:  bool                          = False

    class Config:
        allow_mutation  = False
        extra           = "ignore"
        use_enum_values = True

    @validator("global_max_size")
    def max_size_non_negative(cls, v: int) -> int:
        if v < 0:
            raise ValueError("global_max_size must be >= 0")
        return v

    # ── Convenience queries ───────────────────────────────────

    def get_domain(self, name: str) -> Optional[CacheDomainProfile]:
        return self.domains.get(name)

    def ttl_for(self, domain: str, default: int = 300) -> int:
        """Return TTL for a domain, or default if domain not configured."""
        profile = self.domains.get(domain)
        if profile is None or not profile.enabled:
            return default
        return profile.ttl_s

    def is_enabled_for(self, domain: str) -> bool:
        """Return True if caching is enabled for this domain."""
        if self.backend == CacheBackend.NONE:
            return False
        profile = self.domains.get(domain)
        return profile.enabled if profile else True

    def to_dict(self) -> dict:
        return {
            "backend":         self.backend,
            "eviction_policy": self.eviction_policy,
            "global_max_size": self.global_max_size,
            "warm_on_startup": self.warm_on_startup,
            "redis":           self.redis.to_safe_dict(),
            "domains":         {k: v.to_dict() for k, v in self.domains.items()},
        }


# ── Default domain profiles ───────────────────────────────────

_DEFAULT_DOMAINS: Dict[str, CacheDomainProfile] = {
    "market_quotes":  CacheDomainProfile(ttl_s=15,    max_size=5000),
    "market_candles": CacheDomainProfile(ttl_s=300,   max_size=2000),
    "ai_responses":   CacheDomainProfile(ttl_s=3600,  max_size=500),
    "broker_data":    CacheDomainProfile(ttl_s=60,    max_size=200),
    "instruments":    CacheDomainProfile(ttl_s=86400, max_size=50000),
    "user_sessions":  CacheDomainProfile(ttl_s=1800,  max_size=1000),
}


# ── Factory ───────────────────────────────────────────────────

def build_cache_settings(overrides: Optional[dict] = None) -> CacheSettings:
    """
    Construct CacheSettings from environment variables + optional overrides.

    Environment variables:
      CACHE_BACKEND          -- memory|redis|none (default: "memory")
      CACHE_EVICTION_POLICY  -- lru|lfu|ttl (default: "lru")
      CACHE_GLOBAL_MAX_SIZE  -- int (default: 10000)
      CACHE_WARM_ON_STARTUP  -- true|false (default: "false")
      REDIS_HOST             -- str (default: "localhost")
      REDIS_PORT             -- int (default: 6379)
      REDIS_DB               -- int (default: 0)
      REDIS_SSL              -- true|false (default: "false")
      CACHE_QUOTES_TTL       -- int seconds (default: 15)
      CACHE_CANDLES_TTL      -- int seconds (default: 300)
      CACHE_AI_TTL           -- int seconds (default: 3600)
    """
    backend_raw = os.getenv("CACHE_BACKEND", "memory").strip().lower()
    try:
        backend = CacheBackend(backend_raw)
    except ValueError:
        backend = CacheBackend.MEMORY

    eviction_raw = os.getenv("CACHE_EVICTION_POLICY", "lru").strip().lower()
    try:
        eviction = EvictionPolicy(eviction_raw)
    except ValueError:
        eviction = EvictionPolicy.LRU

    global_max = int(os.getenv("CACHE_GLOBAL_MAX_SIZE", "10000"))
    warm       = os.getenv("CACHE_WARM_ON_STARTUP", "false").strip().lower() == "true"

    redis = RedisConfig(
        host = os.getenv("REDIS_HOST", "localhost"),
        port = int(os.getenv("REDIS_PORT", "6379")),
        db   = int(os.getenv("REDIS_DB",   "0")),
        ssl  = os.getenv("REDIS_SSL", "false").strip().lower() == "true",
    )

    # Allow per-domain TTL overrides from env
    quotes_ttl  = int(os.getenv("CACHE_QUOTES_TTL",  "15"))
    candles_ttl = int(os.getenv("CACHE_CANDLES_TTL", "300"))
    ai_ttl      = int(os.getenv("CACHE_AI_TTL",      "3600"))

    domains = {
        **_DEFAULT_DOMAINS,
        "market_quotes":  CacheDomainProfile(ttl_s=quotes_ttl,  max_size=5000),
        "market_candles": CacheDomainProfile(ttl_s=candles_ttl, max_size=2000),
        "ai_responses":   CacheDomainProfile(ttl_s=ai_ttl,      max_size=500),
    }

    values: dict = {
        "backend":         backend,
        "eviction_policy": eviction,
        "global_max_size": global_max,
        "warm_on_startup": warm,
        "redis":           redis,
        "domains":         domains,
    }

    if overrides:
        values.update(overrides)

    return CacheSettings(**values)
