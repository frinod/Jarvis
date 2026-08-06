"""
config/settings/logging.py
==========================
Logging configuration domain for JARVIS OS.

Covers every logging concern:
  Log levels       -- global and per-module overrides
  Formatters       -- JSON (production) vs human-readable (development)
  Handlers         -- console, rotating file, structured sink
  Sampling         -- reduce noise from high-frequency modules
  Sensitive fields -- fields to redact from log output

Design principles
-----------------
  JSON in production -- machine-parseable for log aggregators
  Human-readable in development -- coloured, concise
  Per-module overrides -- silence noisy third-party libraries
  Redaction list -- PII and secrets never reach log files
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


# ── Enums ─────────────────────────────────────────────────────

class LogLevel(str, Enum):
    DEBUG    = "DEBUG"
    INFO     = "INFO"
    WARNING  = "WARNING"
    ERROR    = "ERROR"
    CRITICAL = "CRITICAL"


class LogFormat(str, Enum):
    JSON        = "json"        # structured JSON -- production
    HUMAN       = "human"       # coloured text -- development
    PLAIN       = "plain"       # plain text -- CI / testing


class LogHandler(str, Enum):
    CONSOLE     = "console"
    FILE        = "file"
    BOTH        = "both"
    NONE        = "none"        # silence all output (testing)


# ── File handler config ───────────────────────────────────────

class FileHandlerConfig(BaseModel):
    """
    Rotating file handler configuration.
    log_dir:        directory for log files (relative to project root)
    max_bytes:      rotate when file exceeds this size
    backup_count:   number of rotated files to keep
    filename_pattern: strftime pattern for daily log files
    """
    log_dir:          str  = "logs"
    max_bytes:        int  = 10_485_760    # 10 MB
    backup_count:     int  = 7
    filename_pattern: str  = "%Y-%m-%d"   # one file per day
    encoding:         str  = "utf-8"

    class Config:
        allow_mutation = False
        extra          = "ignore"

    @validator("max_bytes")
    def max_bytes_positive(cls, v: int) -> int:
        if v < 1:
            raise ValueError("max_bytes must be >= 1")
        return v

    @validator("backup_count")
    def backup_count_non_negative(cls, v: int) -> int:
        if v < 0:
            raise ValueError("backup_count must be >= 0")
        return v

    def to_dict(self) -> dict:
        return self.dict()


# ── Module-level override ─────────────────────────────────────

class ModuleLogConfig(BaseModel):
    """
    Per-module log level override and optional sampling.
    sample_rate: 0.0-1.0 -- fraction of log records to emit (1.0 = all)
    """
    level:       LogLevel = LogLevel.INFO
    sample_rate: float    = 1.0

    class Config:
        allow_mutation  = False
        extra           = "ignore"
        use_enum_values = True

    @validator("sample_rate")
    def rate_in_range(cls, v: float) -> float:
        if not (0.0 <= v <= 1.0):
            raise ValueError("sample_rate must be 0.0-1.0")
        return v

    def to_dict(self) -> dict:
        return self.dict()


# ── Domain settings object ────────────────────────────────────

class LoggingSettings(BaseModel):
    """
    Unified logging configuration.

    module_overrides: per-module level and sampling.
    sensitive_fields: field names to redact from structured logs.
    Built-in noisy modules are silenced by default.
    """
    level:             LogLevel                    = LogLevel.INFO
    format:            LogFormat                   = LogFormat.HUMAN
    handler:           LogHandler                  = LogHandler.BOTH
    file_handler:      FileHandlerConfig           = FileHandlerConfig()
    module_overrides:  Dict[str, ModuleLogConfig]  = {}
    sensitive_fields:  List[str]                   = [
        "password", "secret_key", "api_key", "token",
        "credentials", "access_token", "refresh_token",
    ]
    include_timestamp: bool = True
    include_caller:    bool = False    # file:line -- expensive, off by default

    class Config:
        allow_mutation  = False
        extra           = "ignore"
        use_enum_values = True

    # ── Convenience queries ───────────────────────────────────

    def level_for(self, module: str) -> str:
        """Return effective log level for a module (override or global)."""
        override = self.module_overrides.get(module)
        return override.level if override else self.level

    def sample_rate_for(self, module: str) -> float:
        """Return sampling rate for a module (1.0 if no override)."""
        override = self.module_overrides.get(module)
        return override.sample_rate if override else 1.0

    def is_sensitive(self, field: str) -> bool:
        return field.lower() in [f.lower() for f in self.sensitive_fields]

    def to_dict(self) -> dict:
        return {
            "level":             self.level,
            "format":            self.format,
            "handler":           self.handler,
            "include_timestamp": self.include_timestamp,
            "include_caller":    self.include_caller,
            "sensitive_fields":  self.sensitive_fields,
            "file_handler":      self.file_handler.to_dict(),
            "module_overrides":  {k: v.to_dict() for k, v in self.module_overrides.items()},
        }


# ── Default module overrides ──────────────────────────────────

_DEFAULT_MODULE_OVERRIDES: Dict[str, ModuleLogConfig] = {
    # Silence noisy third-party libraries
    "httpx":              ModuleLogConfig(level=LogLevel.WARNING),
    "httpcore":           ModuleLogConfig(level=LogLevel.WARNING),
    "uvicorn.access":     ModuleLogConfig(level=LogLevel.WARNING),
    "asyncio":            ModuleLogConfig(level=LogLevel.WARNING),
    "pydantic":           ModuleLogConfig(level=LogLevel.WARNING),
    # JARVIS high-frequency modules -- sample to reduce noise
    "app.market_data":    ModuleLogConfig(level=LogLevel.INFO, sample_rate=0.1),
    "app.api":            ModuleLogConfig(level=LogLevel.INFO),
}


# ── Factory ───────────────────────────────────────────────────

def build_logging_settings(overrides: Optional[dict] = None) -> LoggingSettings:
    """
    Construct LoggingSettings from environment variables + optional overrides.

    Environment variables:
      LOG_LEVEL          -- DEBUG|INFO|WARNING|ERROR|CRITICAL (default: "INFO")
      LOG_FORMAT         -- json|human|plain (default: "human")
      LOG_HANDLER        -- console|file|both|none (default: "both")
      LOG_DIR            -- directory path (default: "logs")
      LOG_MAX_BYTES      -- int (default: 10485760)
      LOG_BACKUP_COUNT   -- int (default: 7)
      LOG_INCLUDE_CALLER -- true|false (default: "false")
    """
    level_raw = os.getenv("LOG_LEVEL", "INFO").strip().upper()
    try:
        level = LogLevel(level_raw)
    except ValueError:
        level = LogLevel.INFO

    format_raw = os.getenv("LOG_FORMAT", "human").strip().lower()
    try:
        log_format = LogFormat(format_raw)
    except ValueError:
        log_format = LogFormat.HUMAN

    handler_raw = os.getenv("LOG_HANDLER", "both").strip().lower()
    try:
        handler = LogHandler(handler_raw)
    except ValueError:
        handler = LogHandler.BOTH

    file_handler = FileHandlerConfig(
        log_dir      = os.getenv("LOG_DIR",          "logs"),
        max_bytes    = int(os.getenv("LOG_MAX_BYTES",    "10485760")),
        backup_count = int(os.getenv("LOG_BACKUP_COUNT", "7")),
    )

    include_caller = os.getenv("LOG_INCLUDE_CALLER", "false").strip().lower() == "true"

    values: dict = {
        "level":            level,
        "format":           log_format,
        "handler":          handler,
        "file_handler":     file_handler,
        "module_overrides": _DEFAULT_MODULE_OVERRIDES,
        "include_caller":   include_caller,
    }

    if overrides:
        values.update(overrides)

    return LoggingSettings(**values)
