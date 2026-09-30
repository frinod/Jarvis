"""
jarvis_intent.py — Thin backend intent classifier

Mirrors the frontend intentRouter.ts logic server-side.
Used by the orchestrator to pre-classify requests before routing to agents,
avoiding an unnecessary LLM call for well-known market query patterns.

Design:
  - Pure regex + symbol extraction, no ML, no external calls
  - Returns IntentResult with intent, symbols, tool_plan, confidence
  - Orchestrator uses tool_plan to decide which tools to invoke in sequence
  - Falls back to GENERAL_AI for anything not matched

Financial safety: this module classifies only — it does NOT generate
financial output. All financial language rules are enforced in the
tool implementations and the LLM system prompt.
"""
from __future__ import annotations
import re
from dataclasses import dataclass, field
from typing import List, Dict, Optional

# ── Intent types ──────────────────────────────────────────────
INTENT_TYPES = {
    "MARKET_SESSION",
    "STOCK_ANALYSIS",
    "FORECAST",
    "INTRADAY",
    "MTF",
    "CONFLUENCE",
    "REGIME",
    "MOVERS",
    "NEWS",
    "PORTFOLIO",
    "PAPER_TRADE",
    "MODEL_ACCURACY",
    "PRICE_ALERT",
    "TOP_PICKS",
    "GENERAL_AI",
}

# ── Known NSE symbols ─────────────────────────────────────────
_KNOWN_SYMBOLS = {
    "RELIANCE", "TCS", "INFY", "HDFCBANK", "ICICIBANK", "SBIN", "AXISBANK",
    "KOTAKBANK", "HINDUNILVR", "ITC", "BAJFINANCE", "BAJAJFINSV", "MARUTI",
    "TATAMOTORS", "WIPRO", "HCLTECH", "SUNPHARMA", "ONGC", "NTPC", "POWERGRID",
    "COALINDIA", "ADANIENT", "ADANIPORTS", "ULTRACEMCO", "GRASIM", "ASIANPAINT",
    "TITAN", "NESTLEIND", "BRITANNIA", "DIVISLAB", "CIPLA", "DRREDDY",
    "APOLLOHOSP", "TECHM", "LTIM", "LT", "INDUSINDBK", "BPCL", "HEROMOTOCO",
    "EICHERMOT", "TATACONSUM", "JSWSTEEL", "TATASTEEL", "HINDALCO", "VEDL",
    "NIFTY", "SENSEX", "BANKNIFTY",
}

_SPOKEN_TO_SYMBOL: Dict[str, str] = {
    "reliance":             "RELIANCE",
    "tcs":                  "TCS",
    "tata consultancy":     "TCS",
    "infosys":              "INFY",
    "hdfc bank":            "HDFCBANK",
    "hdfc":                 "HDFCBANK",
    "icici bank":           "ICICIBANK",
    "icici":                "ICICIBANK",
    "state bank":           "SBIN",
    "sbi":                  "SBIN",
    "axis bank":            "AXISBANK",
    "kotak":                "KOTAKBANK",
    "kotak bank":           "KOTAKBANK",
    "hindustan unilever":   "HINDUNILVR",
    "hul":                  "HINDUNILVR",
    "bajaj finance":        "BAJFINANCE",
    "maruti":               "MARUTI",
    "tata motors":          "TATAMOTORS",
    "wipro":                "WIPRO",
    "hcl":                  "HCLTECH",
    "sun pharma":           "SUNPHARMA",
    "asian paints":         "ASIANPAINT",
    "titan":                "TITAN",
    "nestle":               "NESTLEIND",
    "dr reddy":             "DRREDDY",
    "dr. reddy":            "DRREDDY",
    "apollo":               "APOLLOHOSP",
    "l&t":                  "LT",
    "larsen":               "LT",
    "nifty":                "NIFTY",
    "sensex":               "SENSEX",
    "bank nifty":           "BANKNIFTY",
}

# ── Classification rules (order matters — specific before general) ──
_RULES: List[tuple] = [
    (re.compile(r'\b(market (open|closed|status|hours?)|is (the )?market open|nse (open|closed))\b', re.I), "MARKET_SESSION"),
    (re.compile(r'\b(top picks?|daily picks?|best stocks? today|ai picks?|what (should i|to) (buy|trade) today)\b', re.I), "TOP_PICKS"),
    (re.compile(r'\b(market regime|bull(ish)?|bear(ish)?|sideways|market (mood|trend|direction|condition))\b', re.I), "REGIME"),
    (re.compile(r'\b(top (gainers?|losers?|movers?)|biggest (gainers?|losers?|movers?)|market movers?|who(\'s| is) (up|down) (most|today))\b', re.I), "MOVERS"),
    (re.compile(r'\b(news|headlines?|latest (on|for|about)|what(\'s| is) happening (with|to))\b', re.I), "NEWS"),
    (re.compile(r'\b(portfolio|my (holdings?|positions?|trades?|p&l|pnl|profit|loss)|paper (trading|portfolio))\b', re.I), "PORTFOLIO"),
    (re.compile(r'\b(buy|sell|trade|paper trade|execute|place (a )?trade)\b.*\b(shares?|stocks?|qty|quantity)\b', re.I), "PAPER_TRADE"),
    (re.compile(r'\b(set (an? )?alert|alert me|notify me|price alert)\b', re.I), "PRICE_ALERT"),
    (re.compile(r'\b(model accuracy|prediction accuracy|how accurate|win rate|wfv|backtest accuracy)\b', re.I), "MODEL_ACCURACY"),
    (re.compile(r'\b(confluence|multi.?timeframe|all timeframes?|5m.*15m|15m.*1h)\b', re.I), "CONFLUENCE"),
    (re.compile(r'\b(mtf|multi.?tf|timeframe analysis|1h.*4h|4h.*1d)\b', re.I), "MTF"),
    (re.compile(r'\b(intraday|scalp|5 min(ute)?|15 min(ute)?|quick trade|day trade)\b', re.I), "INTRADAY"),
    (re.compile(r'\b(forecast|predict|direction|will (it|.*) (go|rise|fall|drop)|price target|xgboost)\b', re.I), "FORECAST"),
    (re.compile(r'\b(analys[ei]s?|analyse|analyze|signal|buy or sell|should i (buy|sell)|technical|ta |chart|candle|rsi|macd|ema|support|resistance)\b', re.I), "STOCK_ANALYSIS"),
]

# ── Tool plans ────────────────────────────────────────────────
_TOOL_PLANS: Dict[str, List[str]] = {
    "MARKET_SESSION":  ["MarketSessionTool"],
    "STOCK_ANALYSIS":  ["MarketSessionTool", "StockAnalysisTool", "ForecastTool", "MTFTool", "RegimeTool"],
    "FORECAST":        ["MarketSessionTool", "ForecastTool", "RegimeTool"],
    "INTRADAY":        ["MarketSessionTool", "IntradayTool", "ConfluenceTool"],
    "MTF":             ["MTFTool", "RegimeTool"],
    "CONFLUENCE":      ["ConfluenceTool", "RegimeTool"],
    "REGIME":          ["RegimeTool", "MoversTool"],
    "MOVERS":          ["MoversTool", "RegimeTool"],
    "NEWS":            ["NewsTool"],
    "PORTFOLIO":       ["PortfolioTool"],
    "PAPER_TRADE":     ["MarketSessionTool", "StockAnalysisTool", "ForecastTool", "PaperTradeTool"],
    "MODEL_ACCURACY":  ["ModelAccuracyTool"],
    "PRICE_ALERT":     ["PriceAlertTool"],
    "TOP_PICKS":       ["MarketSessionTool", "TopPicksTool", "RegimeTool"],
    "GENERAL_AI":      ["GeneralAITool"],
}


@dataclass
class IntentResult:
    intent: str
    symbols: List[str]
    params: Dict[str, str]
    confidence: float
    tool_plan: List[str]
    raw: str = ""


def _extract_symbols(text: str) -> List[str]:
    found: List[str] = []
    lower = text.lower()

    # Spoken names first (longest match first)
    for spoken, sym in sorted(_SPOKEN_TO_SYMBOL.items(), key=lambda x: -len(x[0])):
        if spoken in lower and sym not in found:
            found.append(sym)

    # Known symbols as whole words
    upper = text.upper()
    for sym in _KNOWN_SYMBOLS:
        if sym not in found and re.search(rf'\b{re.escape(sym)}\b', upper):
            found.append(sym)

    return found


def classify_intent(text: str) -> IntentResult:
    """Classify a user message into a structured IntentResult."""
    symbols = _extract_symbols(text)
    has_symbol = len(symbols) > 0

    for pattern, intent in _RULES:
        if pattern.search(text):
            plan = list(_TOOL_PLANS.get(intent, ["GeneralAITool"]))

            # Trim symbol-dependent tools if no symbol found
            symbol_tools = {"StockAnalysisTool", "ForecastTool", "MTFTool",
                            "IntradayTool", "ConfluenceTool", "PaperTradeTool",
                            "PriceAlertTool"}
            if not has_symbol:
                plan = [t for t in plan if t not in symbol_tools]
                if not plan:
                    plan = ["GeneralAITool"]

            return IntentResult(
                intent=intent,
                symbols=symbols,
                params={},
                confidence=0.85,
                tool_plan=plan,
                raw=text,
            )

    return IntentResult(
        intent="GENERAL_AI",
        symbols=symbols,
        params={},
        confidence=0.5,
        tool_plan=["GeneralAITool"],
        raw=text,
    )


def is_market_query(text: str) -> bool:
    """Quick check: is this a market/stock query (not general AI)?"""
    result = classify_intent(text)
    return result.intent != "GENERAL_AI"
