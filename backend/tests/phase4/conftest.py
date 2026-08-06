"""Phase 4 conftest — path bootstrap + shared fixtures."""
from __future__ import annotations
import sys
import os
import pytest

# ── Path bootstrap ────────────────────────────────────────────────────────────
_BACKEND = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..")
)
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

# Load .env so Angel One credentials are available
try:
    from dotenv import load_dotenv
    _ENV = os.path.join(_BACKEND, ".env")
    if os.path.exists(_ENV):
        load_dotenv(_ENV)
except ImportError:
    pass


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def backend_root() -> str:
    return _BACKEND


@pytest.fixture(scope="session")
def migrated_modules(backend_root: str) -> list:
    """All modules that must have zero fetch_chart call-sites."""
    api = os.path.join(backend_root, "app", "api")
    core = os.path.join(backend_root, "app", "core")
    return [
        os.path.join(api,  "forecaster.py"),
        os.path.join(api,  "mtf_analysis.py"),
        os.path.join(api,  "market_intelligence.py"),
        os.path.join(api,  "market_regime.py"),
        os.path.join(api,  "budget_advisor.py"),
        os.path.join(api,  "routes.py"),
        os.path.join(api,  "auto_trader.py"),
        os.path.join(api,  "backtesting.py"),
        os.path.join(api,  "paper_trading.py"),
        os.path.join(api,  "stock_data.py"),
        os.path.join(core, "orchestrator.py"),
    ]
