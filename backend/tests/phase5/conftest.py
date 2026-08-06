"""Phase 5 conftest -- path bootstrap and environment isolation."""
from __future__ import annotations
import sys
import os

# ── Path bootstrap ────────────────────────────────────────────
_BACKEND = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..")
)
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

# ── Isolate from real .env during tests ───────────────────────
# Tests set JARVIS_ENV themselves per test case.
# Remove any inherited value so tests start clean.
os.environ.pop("JARVIS_ENV", None)
