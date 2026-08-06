"""
config/settings/risk.py
=======================
Risk management configuration domain for JARVIS OS.

Covers every risk control layer:
  Position sizing    -- max size per trade, per symbol, per sector
  Drawdown limits    -- daily, weekly, monthly halt thresholds
  Exposure controls  -- max capital deployed, concentration limits
  Circuit breakers   -- automatic halt conditions
  Slippage model     -- expected slippage for realistic backtesting

Design principles
-----------------
  Configuration only -- enforcement is in the trading layer
  Conservative defaults -- safe to deploy without tuning
  Layered controls -- position -> symbol -> sector -> portfolio
  Halt-first -- when in doubt, stop trading
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

class PositionSizingMethod(str, Enum):
    FIXED_AMOUNT   = "fixed_amount"    # fixed INR per trade
    FIXED_PERCENT  = "fixed_percent"   # % of portfolio per trade
    KELLY          = "kelly"           # Kelly criterion (Phase 7)
    VOLATILITY     = "volatility"      # vol-adjusted sizing (Phase 7)


class HaltReason(str, Enum):
    DAILY_LOSS     = "daily_loss"
    WEEKLY_LOSS    = "weekly_loss"
    MONTHLY_LOSS   = "monthly_loss"
    DRAWDOWN       = "drawdown"
    MANUAL         = "manual"
    CIRCUIT_BREAKER = "circuit_breaker"


# ── Position sizing ───────────────────────────────────────────

class PositionSizingConfig(BaseModel):
    """
    How JARVIS sizes individual positions.
    All monetary values are in INR.
    """
    method:              PositionSizingMethod = PositionSizingMethod.FIXED_AMOUNT
    fixed_amount:        float = 10000.0    # INR per trade (FIXED_AMOUNT mode)
    fixed_percent:       float = 2.0        # % of portfolio (FIXED_PERCENT mode)
    max_position_value:  float = 50000.0    # hard cap per position (INR)
    min_position_value:  float = 500.0      # minimum trade size (INR)
    round_to_lot_size:   bool  = True       # round qty to exchange lot size

    class Config:
        allow_mutation  = False
        extra           = "ignore"
        use_enum_values = True

    @validator("fixed_percent")
    def percent_in_range(cls, v: float) -> float:
        if not (0.0 < v <= 100.0):
            raise ValueError("fixed_percent must be (0, 100]")
        return v

    @validator("fixed_amount", "max_position_value", "min_position_value")
    def amount_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("position amounts must be positive")
        return v

    @validator("min_position_value")
    def min_less_than_max(cls, v: float, values: dict) -> float:
        max_val = values.get("max_position_value")
        if max_val is not None and v >= max_val:
            raise ValueError("min_position_value must be less than max_position_value")
        return v

    def to_dict(self) -> dict:
        return self.dict()


# ── Drawdown limits ───────────────────────────────────────────

class DrawdownConfig(BaseModel):
    """
    Drawdown and loss halt thresholds.
    When any threshold is breached, trading halts until reset.
    All monetary values are in INR.
    """
    max_daily_loss:      float = 5000.0     # halt if daily P&L < -this
    max_weekly_loss:     float = 15000.0    # halt if weekly P&L < -this
    max_monthly_loss:    float = 40000.0    # halt if monthly P&L < -this
    max_drawdown_pct:    float = 10.0       # halt if portfolio drawdown > this %
    trailing_stop_pct:   float = 5.0        # per-position trailing stop %
    auto_reset_daily:    bool  = True       # reset daily counter at market open

    class Config:
        allow_mutation = False
        extra          = "ignore"

    @validator("max_daily_loss", "max_weekly_loss", "max_monthly_loss")
    def loss_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("loss limits must be positive")
        return v

    @validator("max_drawdown_pct", "trailing_stop_pct")
    def pct_in_range(cls, v: float) -> float:
        if not (0.0 < v <= 100.0):
            raise ValueError("percentage must be (0, 100]")
        return v

    def to_dict(self) -> dict:
        return self.dict()


# ── Exposure controls ─────────────────────────────────────────

class ExposureConfig(BaseModel):
    """
    Portfolio-level exposure and concentration limits.
    max_open_positions:  total simultaneous open positions
    max_sector_exposure: max % of portfolio in one sector
    max_symbol_exposure: max % of portfolio in one symbol
    max_capital_deployed: max % of total capital in open positions
    """
    max_open_positions:    int   = 10
    max_sector_exposure:   float = 30.0    # % of portfolio
    max_symbol_exposure:   float = 15.0    # % of portfolio
    max_capital_deployed:  float = 80.0    # % of total capital
    allow_overnight:       bool  = False   # hold positions overnight
    allow_derivatives:     bool  = False   # trade F&O (Phase 7)
    allow_short_selling:   bool  = False   # short positions

    class Config:
        allow_mutation = False
        extra          = "ignore"

    @validator("max_open_positions")
    def positions_positive(cls, v: int) -> int:
        if v < 1:
            raise ValueError("max_open_positions must be >= 1")
        return v

    @validator("max_sector_exposure", "max_symbol_exposure", "max_capital_deployed")
    def exposure_in_range(cls, v: float) -> float:
        if not (0.0 < v <= 100.0):
            raise ValueError("exposure percentages must be (0, 100]")
        return v

    def to_dict(self) -> dict:
        return self.dict()


# ── Circuit breakers ──────────────────────────────────────────

class CircuitBreakerConfig(BaseModel):
    """
    Automatic halt conditions beyond simple loss limits.
    consecutive_losses:  halt after N consecutive losing trades
    loss_streak_reset:   reset streak counter after N winning trades
    rapid_loss_window_s: time window for rapid loss detection (seconds)
    rapid_loss_amount:   halt if this much lost within the window (INR)
    market_halt_on_gap:  halt if market opens with gap > this % (Phase 7)
    """
    enabled:              bool  = True
    consecutive_losses:   int   = 5
    loss_streak_reset:    int   = 2
    rapid_loss_window_s:  int   = 300      # 5 minutes
    rapid_loss_amount:    float = 2000.0   # INR
    market_halt_on_gap:   float = 3.0      # % gap

    class Config:
        allow_mutation = False
        extra          = "ignore"

    @validator("consecutive_losses", "loss_streak_reset")
    def count_positive(cls, v: int) -> int:
        if v < 1:
            raise ValueError("streak counts must be >= 1")
        return v

    @validator("rapid_loss_window_s")
    def window_positive(cls, v: int) -> int:
        if v < 1:
            raise ValueError("rapid_loss_window_s must be >= 1")
        return v

    @validator("rapid_loss_amount")
    def amount_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("rapid_loss_amount must be positive")
        return v

    @validator("market_halt_on_gap")
    def gap_in_range(cls, v: float) -> float:
        if not (0.0 < v <= 100.0):
            raise ValueError("market_halt_on_gap must be (0, 100]")
        return v

    def to_dict(self) -> dict:
        return self.dict()


# ── Slippage model ────────────────────────────────────────────

class SlippageConfig(BaseModel):
    """
    Expected slippage model for paper trading and backtesting.
    These are estimates -- actual slippage varies by liquidity.
    All values in basis points (1 bp = 0.01%).
    """
    enabled:              bool  = True
    default_slippage_bps: float = 5.0      # 5 bps default
    market_order_bps:     float = 10.0     # market orders slip more
    limit_order_bps:      float = 2.0      # limit orders slip less
    illiquid_multiplier:  float = 3.0      # multiply for illiquid stocks

    class Config:
        allow_mutation = False
        extra          = "ignore"

    @validator("default_slippage_bps", "market_order_bps", "limit_order_bps")
    def bps_non_negative(cls, v: float) -> float:
        if v < 0:
            raise ValueError("slippage bps must be >= 0")
        return v

    @validator("illiquid_multiplier")
    def multiplier_positive(cls, v: float) -> float:
        if v < 1.0:
            raise ValueError("illiquid_multiplier must be >= 1.0")
        return v

    def to_dict(self) -> dict:
        return self.dict()


# ── Domain settings object ────────────────────────────────────

class RiskSettings(BaseModel):
    """
    Unified risk management configuration.
    All sub-configs are immutable after load.
    The trading layer reads these; it never writes to them.
    """
    sizing:          PositionSizingConfig = PositionSizingConfig()
    drawdown:        DrawdownConfig       = DrawdownConfig()
    exposure:        ExposureConfig       = ExposureConfig()
    circuit_breaker: CircuitBreakerConfig = CircuitBreakerConfig()
    slippage:        SlippageConfig       = SlippageConfig()
    global_halt:     bool                 = False   # emergency stop all trading

    class Config:
        allow_mutation = False
        extra          = "ignore"

    # ── Convenience queries ───────────────────────────────────

    def is_trading_halted(self) -> bool:
        """True if global halt is active or circuit breaker is enabled and triggered."""
        return self.global_halt

    def max_single_trade_value(self) -> float:
        return self.sizing.max_position_value

    def to_dict(self) -> dict:
        return {
            "global_halt":     self.global_halt,
            "sizing":          self.sizing.to_dict(),
            "drawdown":        self.drawdown.to_dict(),
            "exposure":        self.exposure.to_dict(),
            "circuit_breaker": self.circuit_breaker.to_dict(),
            "slippage":        self.slippage.to_dict(),
        }


# ── Factory ───────────────────────────────────────────────────

def build_risk_settings(overrides: Optional[dict] = None) -> RiskSettings:
    """
    Construct RiskSettings from environment variables + optional overrides.

    Environment variables:
      GLOBAL_HALT              -- true|false (default: "false")
      MAX_DAILY_LOSS           -- float INR (default: 5000.0)
      MAX_POSITION_VALUE       -- float INR (default: 50000.0)
      MAX_OPEN_POSITIONS       -- int (default: 10)
      MAX_CAPITAL_DEPLOYED     -- float % (default: 80.0)
      ALLOW_OVERNIGHT          -- true|false (default: "false")
      ALLOW_DERIVATIVES        -- true|false (default: "false")
      CIRCUIT_BREAKER_ENABLED  -- true|false (default: "true")
      SIZING_METHOD            -- fixed_amount|fixed_percent (default: "fixed_amount")
    """
    global_halt = os.getenv("GLOBAL_HALT", "false").strip().lower() == "true"

    max_daily_loss = float(os.getenv("MAX_DAILY_LOSS", "5000.0"))
    drawdown = DrawdownConfig(max_daily_loss=max_daily_loss)

    max_pos_value = float(os.getenv("MAX_POSITION_VALUE", "50000.0"))
    sizing_method_raw = os.getenv("SIZING_METHOD", "fixed_amount").strip().lower()
    try:
        sizing_method = PositionSizingMethod(sizing_method_raw)
    except ValueError:
        sizing_method = PositionSizingMethod.FIXED_AMOUNT
    sizing = PositionSizingConfig(
        method=sizing_method,
        max_position_value=max_pos_value,
    )

    max_open = int(os.getenv("MAX_OPEN_POSITIONS", "10"))
    max_deployed = float(os.getenv("MAX_CAPITAL_DEPLOYED", "80.0"))
    allow_overnight    = os.getenv("ALLOW_OVERNIGHT",    "false").strip().lower() == "true"
    allow_derivatives  = os.getenv("ALLOW_DERIVATIVES",  "false").strip().lower() == "true"
    exposure = ExposureConfig(
        max_open_positions=max_open,
        max_capital_deployed=max_deployed,
        allow_overnight=allow_overnight,
        allow_derivatives=allow_derivatives,
    )

    cb_enabled = os.getenv("CIRCUIT_BREAKER_ENABLED", "true").strip().lower() == "true"
    circuit_breaker = CircuitBreakerConfig(enabled=cb_enabled)

    values: dict = {
        "global_halt":     global_halt,
        "sizing":          sizing,
        "drawdown":        drawdown,
        "exposure":        exposure,
        "circuit_breaker": circuit_breaker,
    }

    if overrides:
        values.update(overrides)

    return RiskSettings(**values)
