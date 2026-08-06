"""
config/settings/provider.py
============================
Shared provider base model for all JARVIS OS provider types.

Extracted from broker.py when ai.py became the second consumer
(Phase 5 ACP item). Both broker.py and ai.py import from here.

Every provider type in JARVIS shares these fields:
  enabled            -- whether this provider is active
  priority           -- lower number = tried first in fallback chains
  timeout_s          -- network/API timeout in seconds
  retry_policy_name  -- maps to a named RetryPolicy in app.resilience
  credentials_key    -- key prefix in the credentials registry

Future provider types that extend this:
  BrokerProfile, AIProviderProfile, MarketDataProfile,
  VoiceProfile, NotificationProfile, StorageProfile
"""
from __future__ import annotations

from pydantic import BaseModel


class ProviderSettings(BaseModel):
    """
    Reusable base for every provider type in JARVIS OS.

    Extend this for brokers, AI providers, market data providers,
    voice providers, notification providers, and storage providers.
    Shared fields here prevent duplication across provider settings files.
    """
    enabled:            bool  = True
    priority:           int   = 50      # lower = tried first
    timeout_s:          float = 30.0
    retry_policy_name:  str   = "default"   # maps to a RetryPolicy in resilience/
    credentials_key:    str   = ""          # key prefix in credentials registry

    class Config:
        allow_mutation = False
        extra          = "ignore"
