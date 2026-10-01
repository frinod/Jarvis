"""JARVIS cognitive control plane.

This is a thin integration layer around the repository's existing intent,
market, forecasting, memory and paper-trading components. It decides what
read-only evidence is needed for a request, gathers that evidence, and keeps
trade execution behind the existing confirmation API.
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ControlPlaneDecision:
    request_id: str
    intent: str
    symbols: List[str] = field(default_factory=list)
    planned_tools: List[str] = field(default_factory=list)
    evidence: Dict[str, Any] = field(default_factory=dict)
    requires_human_confirmation: bool = False
    execution_mode: str = "read_only"
    started_at: float = field(default_factory=time.time)
    elapsed_ms: float = 0.0

    def prompt_context(self) -> str:
        """Compact evidence packet for the LLM; avoids dumping huge objects."""
        return _compact(self.evidence)


class JarvisControlPlane:
    """Autonomous read-only intelligence planner with human-gated actions."""

    async def prepare(
        self,
        user_input: str,
        user_id: str = "default",
        selected_stock: Optional[str] = None,
    ) -> ControlPlaneDecision:
        from app.api.jarvis_intent import classify_intent
        from app.market_data.session import session_payload
        import uuid

        intent = classify_intent(user_input)
        symbols = list(intent.symbols)
        if selected_stock and not symbols:
            symbols = [selected_stock.replace(".NS", "").upper()]

        decision = ControlPlaneDecision(
            request_id=str(uuid.uuid4()),
            intent=intent.intent,
            symbols=symbols,
            planned_tools=list(intent.tool_plan),
        )

        # Session awareness is always cheap and always useful.
        decision.evidence["market_session"] = session_payload()

        if intent.intent in {"STOCK_ANALYSIS", "FORECAST", "INTRADAY", "MTF", "CONFLUENCE", "TOP_PICKS"} and symbols:
            # Keep provider calls bounded and independent. Forecast itself owns
            # freshness, quality, regime, MTF and calibration gates.
            from app.api.forecaster import forecast
            from app.api.market_intelligence import get_intraday_assistant
            from app.api.mtf_analysis import get_mtf_analysis
            from app.api.market_regime import get_market_regime

            symbol = symbols[0]
            tasks = [forecast(symbol, horizon=30), get_market_regime(), get_mtf_analysis(symbol)]
            if intent.intent == "INTRADAY":
                tasks.append(get_intraday_assistant(symbol, timeframe="5m"))
            results = await asyncio.gather(*tasks, return_exceptions=True)

            names = ["forecast", "regime", "mtf"] + (["intraday"] if intent.intent == "INTRADAY" else [])
            for name, result in zip(names, results):
                if isinstance(result, Exception):
                    decision.evidence[name] = {"error": str(result)}
                else:
                    decision.evidence[name] = result

            decision.evidence["source_policy"] = {
                "forecast": "XGBoost + WFV + calibration + regime + MTF",
                "live_data_rule": "suppress intraday inference when provider data is stale",
            }

        elif intent.intent == "NEWS":
            from app.api.market_intelligence import get_market_news
            decision.evidence["news"] = await get_market_news(symbols[0] if symbols else None, limit=20)

        elif intent.intent == "MOVERS":
            from app.api.market_intelligence import get_market_movers
            decision.evidence["movers"] = await get_market_movers()

        elif intent.intent == "REGIME":
            from app.api.market_regime import get_market_regime
            decision.evidence["regime"] = await get_market_regime()
            from app.api.market_intelligence import get_market_movers
            decision.evidence["movers"] = await get_market_movers()

        elif intent.intent == "PORTFOLIO":
            # Portfolio read access is safe; order execution remains separate.
            try:
                from app.api.paper_trading import get_portfolio
                decision.evidence["portfolio"] = get_portfolio(user_id)
            except Exception as exc:
                decision.evidence["portfolio"] = {"error": str(exc)}

        elif intent.intent == "PAPER_TRADE":
            if not symbols:
                decision.evidence["trade"] = {"status": "needs_symbol"}
            else:
                from app.api.paper_trading import ai_auto_trade
                try:
                    # Proposal only. The existing function does not execute.
                    decision.evidence["trade"] = await ai_auto_trade(
                        portfolio_id=user_id,
                        symbol=symbols[0],
                    )
                    decision.requires_human_confirmation = True
                    decision.execution_mode = "human_confirmed_paper"
                except Exception as exc:
                    decision.evidence["trade"] = {"error": str(exc)}

        decision.elapsed_ms = round((time.time() - decision.started_at) * 1000, 2)
        return decision


def _compact(value: Any, limit: int = 14000) -> str:
    import json
    try:
        text = json.dumps(value, ensure_ascii=False, default=str)
    except Exception:
        text = str(value)
    return text if len(text) <= limit else text[:limit] + "…"
