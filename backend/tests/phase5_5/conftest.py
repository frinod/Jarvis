"""Phase 5.5 conftest -- path bootstrap and environment isolation."""
from __future__ import annotations
import sys
import os

_BACKEND = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..")
)
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

os.environ.pop("JARVIS_ENV", None)
