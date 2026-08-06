"""
config/settings/app.py
======================
Application identity and configuration system metadata.

This is the root domain settings object. It carries:
  - Application identity (name, version, environment)
  - Build information (build_id, commit, timestamp)
  - Configuration system metadata (version, source, loaded_at)
  - Core security primitives (secret_key, token expiry)
  - Server binding (host, port, debug)

Design principles
-----------------
  Immutable after load  -- Config class sets allow_mutation=False
  Type-safe             -- Pydantic field types enforced at construction
  Metadata-aware        -- ConfigMetadata records provenance for diagnostics
  Hot-reload ready      -- frozen model means swap is atomic (assembler concern)
  Version-stamped       -- config_version enables future migration paths

This module has NO side effects at import time.
It does NOT load .env itself -- the root assembler (settings/__init__.py)
owns .env loading and passes values in.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, validator


# ── Configuration metadata ────────────────────────────────────

@dataclass
class ConfigMetadata:
    """
    Provenance record for a loaded configuration object.
    Exposed on every Settings domain object for diagnostics.

    source          : where values came from (default / env / yaml / override)
    loaded_at       : UTC timestamp when this config was constructed
    config_version  : integer schema version -- increment on breaking changes
    validated       : True after startup validation chain passes
    environment     : active JARVIS_ENV profile name
    """
    source:         str      = "default"
    loaded_at:      datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    config_version: int      = 1
    validated:      bool     = False
    environment:    str      = "development"

    def mark_validated(self) -> "ConfigMetadata":
        """Return a new metadata instance with validated=True."""
        return ConfigMetadata(
            source         = self.source,
            loaded_at      = self.loaded_at,
            config_version = self.config_version,
            validated      = True,
            environment    = self.environment,
        )

    def to_dict(self) -> dict:
        return {
            "source":         self.source,
            "loaded_at":      self.loaded_at.isoformat(),
            "config_version": self.config_version,
            "validated":      self.validated,
            "environment":    self.environment,
        }


# ── App settings domain ───────────────────────────────────────

class AppSettings(BaseModel):
    """
    Application identity, server config, and security primitives.

    All fields have safe defaults so the application starts without
    a .env file (useful in tests and CI). Production deployments
    must override secret_key via environment variable.
    """

    # ── Identity ──────────────────────────────────────────────
    app_name:    str = "JARVIS OS"
    version:     str = "1.0.0"
    description: str = "Just A Rather Very Intelligent System"

    # ── Configuration versioning ──────────────────────────────
    # Increment when the settings schema has a breaking change.
    # Migration layer reads this to decide upgrade path.
    config_version: int = 1

    # ── Environment ───────────────────────────────────────────
    # Mirrors JARVIS_ENV -- stored here so it travels with the
    # settings object rather than requiring a separate env lookup.
    environment: str = "development"

    # ── Build information ─────────────────────────────────────
    # Populated by CI/CD pipeline via environment variables.
    # Safe defaults mean local dev works without setting these.
    build_id:        str = "local"
    commit_sha:      str = "unknown"
    build_timestamp: str = "unknown"

    # ── Server ────────────────────────────────────────────────
    host:  str  = "0.0.0.0"
    port:  int  = 8000
    debug: bool = False

    # ── Security primitives ───────────────────────────────────
    # secret_key is used for JWT signing and session tokens.
    # The startup validator rejects the default value in production.
    secret_key:                    str = "change-me-in-production"
    algorithm:                     str = "HS256"
    access_token_expire_minutes:   int = 1440   # 24 hours

    # ── Validators ────────────────────────────────────────────

    @validator("environment")
    def environment_must_be_known(cls, v: str) -> str:
        known = {"development", "testing", "staging", "production"}
        if v not in known:
            return "development"
        return v

    @validator("port")
    def port_in_range(cls, v: int) -> int:
        if not (1 <= v <= 65535):
            raise ValueError(f"port must be 1-65535, got {v}")
        return v

    @validator("access_token_expire_minutes")
    def token_expiry_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("access_token_expire_minutes must be positive")
        return v

    @validator("config_version")
    def config_version_positive(cls, v: int) -> int:
        if v < 1:
            raise ValueError("config_version must be >= 1")
        return v

    # ── Immutability ──────────────────────────────────────────

    class Config:
        # Pydantic v1: prevent mutation after construction
        allow_mutation = False
        # Allow extra fields to be ignored (forward compatibility)
        extra = "ignore"

    # ── Convenience ───────────────────────────────────────────

    @property
    def is_debug(self) -> bool:
        return self.debug

    @property
    def has_default_secret(self) -> bool:
        """True if secret_key has not been changed from the insecure default."""
        return self.secret_key == "change-me-in-production"

    def to_dict(self) -> dict:
        """Safe serialisation -- never includes secret_key value."""
        return {
            "app_name":       self.app_name,
            "version":        self.version,
            "config_version": self.config_version,
            "environment":    self.environment,
            "build_id":       self.build_id,
            "commit_sha":     self.commit_sha,
            "host":           self.host,
            "port":           self.port,
            "debug":          self.debug,
            "secret_key":     "[REDACTED]",
        }


# ── Factory ───────────────────────────────────────────────────

def build_app_settings(overrides: Optional[dict] = None) -> AppSettings:
    """
    Construct AppSettings from environment variables + optional overrides.

    Environment variables read (all optional):
      JARVIS_APP_NAME, JARVIS_VERSION, JARVIS_ENV,
      JARVIS_HOST, JARVIS_PORT, JARVIS_DEBUG,
      SECRET_KEY, JARVIS_BUILD_ID, JARVIS_COMMIT_SHA,
      JARVIS_BUILD_TIMESTAMP, JARVIS_CONFIG_VERSION

    overrides dict is applied last -- used by tests and profile overrides.
    """
    from app.config.environment import get_env

    values: dict = {
        "app_name":                  os.getenv("JARVIS_APP_NAME",        "JARVIS OS"),
        "version":                   os.getenv("JARVIS_VERSION",         "1.0.0"),
        "environment":               get_env().value,
        "build_id":                  os.getenv("JARVIS_BUILD_ID",        "local"),
        "commit_sha":                os.getenv("JARVIS_COMMIT_SHA",      "unknown"),
        "build_timestamp":           os.getenv("JARVIS_BUILD_TIMESTAMP", "unknown"),
        "host":                      os.getenv("JARVIS_HOST",            "0.0.0.0"),
        "port":              int(os.getenv("JARVIS_PORT",            "8000")),
        "debug":             os.getenv("JARVIS_DEBUG",           "false").lower() == "true",
        "secret_key":                os.getenv("SECRET_KEY",             "change-me-in-production"),
        "algorithm":                 os.getenv("JARVIS_ALGORITHM",       "HS256"),
        "access_token_expire_minutes": int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440")),
        "config_version":    int(os.getenv("JARVIS_CONFIG_VERSION",  "1")),
    }

    if overrides:
        values.update(overrides)

    return AppSettings(**values)
