"""
app/ai/prediction/forecasting.py
==================================
ForecastingEngine -- ML model wrapper for inference.

Design
------
  - ForecastingEngine wraps existing XGBoost .pkl models in backend/models/.
  - No new ML training in Phase 6 -- inference only (architecture §15).
  - ForecastingEngine is an ABC. XGBoostForecastingEngine is the impl.
  - MockForecastingEngine is provided for testing (no model files needed).
  - PredictionResult carries direction, magnitude, and confidence.

Domain agnosticism at the interface level
------------------------------------------
  ForecastingEngine.predict() accepts a FeatureVector.
  PredictionResult.metadata carries domain-specific data.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from app.ai.prediction.feature_store import FeatureVector


# ── ForecastResult ────────────────────────────────────────────────────────────
# Thin wrapper around the dict returned by app.api.forecaster.forecast().
# Agents read from this instead of raw dicts so the contract is explicit.

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class ForecastResult:
    """
    Structured view of the dict returned by app.api.forecaster.forecast().

    All fields default to safe/unavailable values so agents never see None
    where they expect a string or float.
    """
    symbol:             str   = ""
    direction:          str   = "UNAVAILABLE"   # UP / DOWN / FLAT / UNAVAILABLE
    confidence:         float = 0.0             # 0-100
    prob_up:            float = 0.0
    prob_down:          float = 0.0
    prob_flat:          float = 0.0
    regime:             str   = "unknown"
    regime_label:       str   = ""
    regime_adjusted:    bool  = False
    regime_warning:     Optional[str] = None
    mtf_confluence:     Optional[str] = None
    mtf_score:          Optional[float] = None
    mtf_htf_signal:     Optional[str] = None
    ta_signal:          str   = "HOLD"
    ta_confidence:      float = 0.0
    ta_score:           float = 0.0
    trend:              str   = "neutral"
    entry_price:        float = 0.0
    stop_loss:          float = 0.0
    target1:            float = 0.0
    target2:            float = 0.0
    atr:                Optional[float] = None
    rsi:                Optional[float] = None
    supertrend:         Optional[str]   = None
    nearest_support:    Optional[float] = None
    nearest_resistance: Optional[float] = None
    wfv_accuracy:       Optional[float] = None
    wfv_useful:         Optional[bool]  = None
    model_name:         str   = "XGBoost"
    error:              Optional[str]   = None
    raw:                Dict[str, Any]  = field(default_factory=dict)

    @property
    def is_valid(self) -> bool:
        """True when the forecast produced a real prediction (not an error/unavailable)."""
        return self.error is None and self.direction in ("UP", "DOWN", "FLAT")

    @property
    def trade_signal(self) -> str:
        """Map model direction to BUY/SELL/HOLD for agent consumption."""
        if not self.is_valid:
            return "HOLD"
        if self.direction == "UP":
            return "BUY"
        if self.direction == "DOWN":
            return "SELL"
        return "HOLD"

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ForecastResult":
        """Build a ForecastResult from the dict returned by forecast()."""
        if not d or d.get("error"):
            return cls(error=d.get("error", "unknown_error") if d else "empty_response")

        fc  = d.get("forecast", {})
        reg = d.get("regime",   {})
        mtf = d.get("mtf",      {})
        ctx = d.get("context",  {})
        val = d.get("validation", {})

        price = fc.get("current_price") or ctx.get("entry_price") or 0.0

        return cls(
            symbol             = d.get("symbol", ""),
            direction          = fc.get("direction", "UNAVAILABLE"),
            confidence         = float(fc.get("confidence") or 0.0),
            prob_up            = float(fc.get("prob_up")    or 0.0),
            prob_down          = float(fc.get("prob_down")  or 0.0),
            prob_flat          = float(fc.get("prob_flat")  or 0.0),
            regime             = reg.get("regime",  "unknown"),
            regime_label       = reg.get("label",   ""),
            regime_adjusted    = bool(reg.get("adjusted")),
            regime_warning     = reg.get("warning"),
            mtf_confluence     = mtf.get("confluence"),
            mtf_score          = mtf.get("score"),
            mtf_htf_signal     = mtf.get("htf_signal"),
            ta_signal          = ctx.get("overall_signal", "HOLD"),
            ta_confidence      = float(ctx.get("ta_confidence") or 0.0),
            ta_score           = float(ctx.get("ta_score")      or 0.0),
            trend              = ctx.get("trend", "neutral"),
            entry_price        = float(price),
            stop_loss          = float(fc.get("estimated_low")    or 0.0),
            target1            = float(fc.get("estimated_target") or 0.0),
            target2            = float(fc.get("estimated_target") or 0.0),
            atr                = ctx.get("atr"),
            rsi                = ctx.get("rsi"),
            supertrend         = ctx.get("supertrend"),
            nearest_support    = ctx.get("nearest_support"),
            nearest_resistance = ctx.get("nearest_resistance"),
            wfv_accuracy       = val.get("wfv_accuracy"),
            wfv_useful         = val.get("wfv_useful"),
            model_name         = fc.get("model", "XGBoost"),
            error              = None,
            raw                = d,
        )

    @classmethod
    def unavailable(cls, reason: str = "model_unavailable") -> "ForecastResult":
        """Safe no-trade result for any failure path."""
        return cls(direction="UNAVAILABLE", error=reason)


# ── PredictionResult ──────────────────────────────────────────────────────────

class PredictionDirection(str, Enum):
    UP      = "up"
    DOWN    = "down"
    NEUTRAL = "neutral"


@dataclass
class PredictionResult:
    """Output of ForecastingEngine.predict()."""
    direction:     PredictionDirection
    magnitude:     float          # 0.0 to 1.0 (strength of the prediction)
    confidence:    float          # 0.0 to 1.0
    model_name:    str            = ""
    features_used: List[str]      = field(default_factory=list)
    metadata:      Dict[str, Any] = field(default_factory=dict)


# ── ForecastingEngine ABC ─────────────────────────────────────────────────────

class ForecastingEngine(ABC):
    """
    Interface for ML model inference.
    Phase 6: MockForecastingEngine.
    Phase 7+: XGBoostForecastingEngine wrapping backend/models/*.pkl.
    """

    @abstractmethod
    def predict(self, features: FeatureVector, model_name: str = "default") -> PredictionResult:
        """Run inference. Returns PredictionResult. Never raises."""

    @abstractmethod
    def is_model_available(self, model_name: str) -> bool:
        """Return True if the named model is loaded and ready."""


# ── XGBoostForecastingEngine ─────────────────────────────────────────────────

class XGBoostForecastingEngine(ForecastingEngine):
    """
    Production forecasting engine.

    Delegates to app.api.forecaster.forecast() which owns the full pipeline:
      StockForecaster → XGBoost .pkl → regime filter → MTF → calibration.

    predict() is synchronous (ForecastingEngine ABC contract) so it runs
    the async forecast() via asyncio.  Callers that are already in an async
    context should use predict_async() directly.

    is_model_available() checks whether a .pkl file exists for the symbol.
    """

    def predict(self, features: FeatureVector, model_name: str = "default") -> PredictionResult:
        """
        Synchronous wrapper — only use from non-async contexts.
        Agents running inside an async pipeline should call predict_async().
        """
        import asyncio
        symbol = features.metadata.get("symbol", model_name)
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Already inside an event loop — cannot block; return neutral
                return PredictionResult(
                    direction=PredictionDirection.NEUTRAL,
                    magnitude=0.0,
                    confidence=0.0,
                    model_name=model_name,
                    metadata={"error": "use_predict_async_in_async_context"},
                )
            result = loop.run_until_complete(self._run_forecast(symbol))
        except Exception as exc:
            return PredictionResult(
                direction=PredictionDirection.NEUTRAL,
                magnitude=0.0,
                confidence=0.0,
                model_name=model_name,
                metadata={"error": str(exc)},
            )
        return self._to_prediction_result(result, model_name)

    async def predict_async(self, symbol: str, horizon: int = 30) -> ForecastResult:
        """
        Async entry point for agents.  Returns a ForecastResult.
        Never raises — returns ForecastResult.unavailable() on any failure.
        """
        try:
            raw = await self._run_forecast(symbol, horizon)
            return ForecastResult.from_dict(raw)
        except Exception as exc:
            return ForecastResult.unavailable(reason=str(exc))

    async def _run_forecast(self, symbol: str, horizon: int = 30) -> dict:
        from app.api.forecaster import forecast as _forecast
        return await _forecast(symbol, horizon=horizon)

    def is_model_available(self, model_name: str) -> bool:
        import os
        from app.api.forecaster import MODEL_DIR
        safe = model_name.replace(".NS", "").replace(".", "_")
        return os.path.exists(os.path.join(MODEL_DIR, f"{safe}_xgb.pkl"))

    def _to_prediction_result(self, raw: dict, model_name: str) -> PredictionResult:
        fr = ForecastResult.from_dict(raw)
        if not fr.is_valid:
            return PredictionResult(
                direction=PredictionDirection.NEUTRAL,
                magnitude=0.0,
                confidence=0.0,
                model_name=model_name,
                metadata={"error": fr.error or "invalid_forecast"},
            )
        dir_map = {"UP": PredictionDirection.UP, "DOWN": PredictionDirection.DOWN}
        return PredictionResult(
            direction=dir_map.get(fr.direction, PredictionDirection.NEUTRAL),
            magnitude=fr.confidence / 100.0,
            confidence=fr.confidence / 100.0,
            model_name=fr.model_name,
            metadata={"forecast_result": fr},
        )


# ── MockForecastingEngine ─────────────────────────────────────────────────────

class MockForecastingEngine(ForecastingEngine):
    """
    Mock engine for Phase 6 testing.
    Returns configurable predictions without loading any model files.
    """

    def __init__(
        self,
        direction:  PredictionDirection = PredictionDirection.NEUTRAL,
        magnitude:  float               = 0.5,
        confidence: float               = 0.5,
    ):
        self._direction  = direction
        self._magnitude  = magnitude
        self._confidence = confidence

    def predict(self, features: FeatureVector, model_name: str = "default") -> PredictionResult:
        return PredictionResult(
            direction=self._direction,
            magnitude=self._magnitude,
            confidence=self._confidence,
            model_name=model_name,
            features_used=features.source_keys,
        )

    def is_model_available(self, model_name: str) -> bool:
        return True   # mock always available

    def set_prediction(
        self,
        direction:  PredictionDirection,
        magnitude:  float,
        confidence: float,
    ) -> None:
        self._direction  = direction
        self._magnitude  = magnitude
        self._confidence = confidence
